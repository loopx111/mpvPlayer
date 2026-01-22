import json
import time
import threading
import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path
from ..config.models import AppConfig
from ..utils.logger import get_logger
from .mqtt_client import MqttClient
from ..file_dist.manager import DownloadManager as FileDistManager
from ..file_dist.manager import DownloadTask as FileDistTask


class MqttService:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.log = get_logger("mqtt.service")
        self.client = MqttClient(cfg.mqtt)
        
        # 初始化更强大的异步下载管理器
        self.download_manager: Optional[FileDistManager] = None
        if cfg.download:
            self.download_manager = FileDistManager(cfg.download)
        
        # 异步事件循环
        self._loop = asyncio.new_event_loop()
        self._download_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._download_thread.start()
        
        self.last_status_ts = 0
        self.heartbeat_thread = None
        self._running = True
    
    def _run_async_loop(self):
        """运行异步事件循环"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def start(self, command_topics: List[str]) -> None:
        if not self.cfg.mqtt.enabled:
            self.log.info("MQTT 服务已禁用，跳过连接")
            return
            
        self.log.info(f"启动MQTT服务，订阅主题: {command_topics}", "start")
        
        # 设置连接成功回调
        self.client.on_connect_success = self._on_connect_success
        
        for t in command_topics:
            self.client.subscribe(t, self._handle_command)
        
        try:
            self.client.connect()
            self.log.info("MQTT服务启动成功")
        except Exception as e:
            self.log.error(f"MQTT 连接失败: {e}，但应用将继续运行", "start")

    def publish_status(self, status: Dict[str, Any]) -> None:
        topic = "ohos/status"
        status["ts"] = int(time.time() * 1000)
        self.client.publish(topic, status)

    def publish_download(self, payload: Dict[str, Any]) -> None:
        topic = "ohos/download"
        payload["ts"] = int(time.time() * 1000)
        self.client.publish(topic, payload)

    def _handle_file_distribution(self, data: Dict) -> bool:
        """处理文件分发消息 - 使用异步下载管理器"""
        # 检查是否为文件分发消息
        if data.get("type") == "file_distribution" and data.get("operation") == "file-distribution":
            files = data.get("files", [])
            mode = data.get("mode", "immediate")
            
            self.log.info(f"收到文件分发消息，模式: {mode}, 文件数量: {len(files)}")
            
            if not files:
                self.log.warning("文件分发消息中没有文件列表")
                return True
            
            if not self.download_manager:
                self.log.error("下载管理器未初始化，无法处理文件分发")
                return True
            
            # 使用异步方式添加下载任务
            for file_info in files:
                self._add_async_download_task(file_info)
            
            # 发布下载开始状态
            self.publish_download({
                "type": "file_distribution",
                "status": "started",
                "file_count": len(files),
                "mode": mode
            })
            
            return True
        return False
    
    def _handle_playlist_distribution(self, data: Dict) -> bool:
        """处理播放列表分发消息"""
        # 检查是否为播放列表分发消息
        if data.get("type") == "playlist" and data.get("operation") == "playlist-distribution":
            files = data.get("files", [])
            mode = data.get("mode", "immediate")
            schedule_time = data.get("scheduleTime")
            
            self.log.info(f"收到播放列表分发消息，模式: {mode}, 文件数量: {len(files)}")
            
            if not files:
                self.log.warning("播放列表消息中没有文件列表")
                return True
            
            # 在后台线程中处理播放列表分发
            threading.Thread(target=self._process_playlist_distribution, 
                           args=(files, mode, schedule_time), daemon=True).start()
            
            # 发布播放列表更新状态
            self.publish_status({
                "type": "playlist_distribution",
                "status": "processing",
                "file_count": len(files),
                "mode": mode
            })
            
            return True
        return False
    
    def _process_playlist_distribution(self, files: List[Dict], mode: str, schedule_time: Optional[str]) -> None:
        """处理播放列表分发"""
        try:
            # 获取播放器实例（通过回调或全局变量）
            player = self._get_player_instance()
            if not player:
                self.log.error("无法获取播放器实例，无法处理播放列表分发")
                return
            
            # 获取播放目录和下载目录
            video_path = self.cfg.player.videoPath
            download_path = self.cfg.download.path
            
            self.log.info(f"开始处理播放列表分发，播放目录: {video_path}, 下载目录: {download_path}")
            
            # 1. 查询当前播放目录中的所有文件
            current_files = self._get_current_playlist_files(video_path)
            self.log.info(f"当前播放目录中有 {len(current_files)} 个文件")
            
            # 2. 根据消息中的文件列表，删除不需要的文件
            self._cleanup_playlist_files(current_files, files, video_path)
            
            # 3. 拷贝缺失的文件到播放目录
            self._copy_missing_files(files, video_path, download_path)
            
            # 4. 更新播放列表并重新开始播放
            self._update_playlist_and_restart(player, video_path, mode)
            
            # 发布完成状态
            self.publish_status({
                "type": "playlist_distribution",
                "status": "completed",
                "file_count": len(files),
                "mode": mode
            })
            
        except Exception as e:
            self.log.error(f"处理播放列表分发时出错: {e}")
            # 发布错误状态
            self.publish_status({
                "type": "playlist_distribution",
                "status": "error",
                "error": str(e)
            })
    
    def set_player_instance(self, player):
        """设置播放器实例"""
        self.player_instance = player
        self.log.info("播放器实例已设置到MQTT服务")
    
    def _get_player_instance(self):
        """获取播放器实例"""
        return getattr(self, 'player_instance', None)
    
    def _get_current_playlist_files(self, video_path: str) -> List[str]:
        """获取当前播放目录中的所有文件"""
        try:
            from pathlib import Path
            video_dir = Path(video_path)
            
            if not video_dir.exists():
                self.log.warning(f"播放目录不存在: {video_path}")
                return []
            
            # 支持的视频格式
            supported_formats = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
            
            # 查找所有视频文件
            video_files = []
            for file_path in video_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in supported_formats:
                    video_files.append(file_path.name)
            
            return video_files
            
        except Exception as e:
            self.log.error(f"获取当前播放列表文件时出错: {e}")
            return []
    
    def _cleanup_playlist_files(self, current_files: List[str], target_files: List[Dict], video_path: str) -> None:
        """清理播放列表文件，删除不需要的文件"""
        try:
            from pathlib import Path
            video_dir = Path(video_path)
            
            if not video_dir.exists():
                return
            
            # 提取目标文件名列表
            target_file_names = [file_info.get("name") for file_info in target_files]
            
            # 删除不需要的文件
            for current_file in current_files:
                if current_file not in target_file_names:
                    file_to_delete = video_dir / current_file
                    if file_to_delete.exists():
                        file_to_delete.unlink()
                        self.log.info(f"删除不需要的文件: {current_file}")
            
            self.log.info("播放列表文件清理完成")
            
        except Exception as e:
            self.log.error(f"清理播放列表文件时出错: {e}")
    
    def _copy_missing_files(self, target_files: List[Dict], video_path: str, download_path: str) -> None:
        """拷贝缺失的文件到播放目录"""
        try:
            from pathlib import Path
            import shutil
            
            video_dir = Path(video_path)
            download_dir = Path(download_path)
            
            # 确保播放目录存在
            video_dir.mkdir(parents=True, exist_ok=True)
            
            if not download_dir.exists():
                self.log.warning(f"下载目录不存在: {download_path}")
                return
            
            # 拷贝缺失的文件
            for file_info in target_files:
                file_name = file_info.get("name")
                if not file_name:
                    continue
                
                # 检查播放目录中是否已存在该文件
                target_file = video_dir / file_name
                if target_file.exists():
                    self.log.info(f"文件已存在，跳过拷贝: {file_name}")
                    continue
                
                # 在下载目录中查找文件
                source_file = download_dir / file_name
                if source_file.exists():
                    # 拷贝文件到播放目录
                    shutil.copy2(source_file, target_file)
                    self.log.info(f"拷贝文件到播放目录: {file_name}")
                else:
                    self.log.warning(f"文件在下载目录中不存在: {file_name}")
            
            self.log.info("文件拷贝完成")
            
        except Exception as e:
            self.log.error(f"拷贝文件时出错: {e}")
    
    def _update_playlist_and_restart(self, player, video_path: str, mode: str) -> None:
        """更新播放列表并重新开始播放"""
        try:
            # 如果模式是immediate，停止当前播放
            if mode == "immediate":
                if hasattr(player, 'stop_play'):
                    player.stop_play()
            
            # 重新设置播放目录（这会自动重新开始播放）
            if hasattr(player, 'set_playlist_dir'):
                player.set_playlist_dir(video_path, use_playlist_mode=True)
                self.log.info("播放列表已更新")
                
            # 移除多余的播放重启逻辑，因为set_playlist_dir已经包含了播放逻辑
            
        except Exception as e:
            self.log.error(f"更新播放列表时出错: {e}")
    
    def _add_async_download_task(self, file_info: Dict) -> None:
        """异步添加下载任务"""
        try:
            file_id = file_info.get("id", "unknown")
            file_name = file_info.get("name", "unknown")
            download_url = file_info.get("downloadUrl")
            
            if not download_url:
                self.log.warning(f"文件 {file_name} 缺少下载URL，跳过")
                return
            
            # 构建本地文件路径
            download_path = Path(self.cfg.download.path) / file_name
            
            # 检查文件是否已存在
            if download_path.exists():
                self.log.info(f"文件已存在，跳过下载: {file_name}")
                return
            
            # 创建异步下载任务
            task_id = f"{file_info.get('uuid', '')}_{file_id}"
            task = FileDistTask(
                task_id=task_id,
                url=download_url,
                dest=download_path,
                checksum=None,  # 文件分发消息中没有校验和信息
                checksum_type="md5",
                extract=False   # 暂时不支持自动解压
            )
            
            # 在异步事件循环中执行
            asyncio.run_coroutine_threadsafe(
                self._execute_download_task(task), 
                self._loop
            )
            
            self.log.info(f"已添加异步下载任务: {file_name} (ID: {task_id})")
            
        except Exception as e:
            self.log.error(f"添加下载任务失败: {file_info}", "add_download_task", e)
    
    async def _execute_download_task(self, task: FileDistTask) -> None:
        """执行下载任务"""
        try:
            # 将任务加入下载管理器
            self.download_manager.enqueue(task)
            
            # 等待任务完成（这里可以添加更复杂的监控逻辑）
            # 目前依赖下载管理器自身的状态跟踪
            
        except Exception as e:
            self.log.error(f"执行下载任务失败: {task.task_id}", "execute_download", e)

    def _handle_command(self, topic: str, payload: str) -> None:
        """处理MQTT命令，包括文件分发消息"""
        self.log.info(f"收到MQTT消息 - 主题: {topic}, 内容: {payload}")
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            self.log.warning("Invalid JSON on %s", topic)
            return
            
        # 检查是否为文件分发消息
        if self._handle_file_distribution(data):
            return
            
        # 检查是否为播放列表分发消息
        if self._handle_playlist_distribution(data):
            return
            
        # 处理普通命令
        command = data.get("command") or data.get("cmd")
        if not command:
            return
        if command == "restart":
            self.log.info("收到重启命令")
            # Hook for restart handling
        elif command == "download":
            self.log.info("收到下载命令")
            # Hook: enqueue download
        elif command == "query":
            self.log.info("收到查询命令")
            self.publish_status({"status": "ready"})
        else:
            self.log.warning("未知命令: %s", command)

    def _on_connect_success(self) -> None:
        """MQTT连接成功回调，启动心跳线程"""
        self.log.info("MQTT连接成功，启动心跳消息")
        self._start_heartbeat()

    def _start_heartbeat(self) -> None:
        """启动心跳线程"""
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            return
            
        def heartbeat_loop():
            while self._running:
                try:
                    # 发送心跳消息
                    self._send_heartbeat()
                    # 等待5秒
                    time.sleep(5)
                except Exception as e:
                    self.log.error(f"心跳线程异常: {e}", "heartbeat_loop")
                    time.sleep(5)
        
        self.heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def _send_heartbeat(self) -> None:
        """发送心跳消息"""
        client_id = self.cfg.mqtt.clientId
        device_path = self.cfg.mqtt.devicePath or self.cfg.system.devicePath
        
        heartbeat_topic = f"设备/{client_id}/心跳"
        heartbeat_data = {
            "id": client_id,
            "path": device_path,
            "type": "heartbeat",
            "value": "alive"
        }
        
        self.client.publish(heartbeat_topic, heartbeat_data)
        self.log.debug(f"发送心跳消息 - 主题: {heartbeat_topic}, 数据: {heartbeat_data}")

    def stop(self) -> None:
        """停止MQTT服务"""
        self._running = False
        
        # 停止异步事件循环
        if hasattr(self, '_loop') and self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        # 停止下载线程
        if hasattr(self, '_download_thread') and self._download_thread:
            self._download_thread.join(timeout=5)
        
        # 停止下载管理器（如果有stop方法）
        if self.download_manager and hasattr(self.download_manager, 'stop'):
            self.download_manager.stop()
        
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
        self.client.disconnect()
