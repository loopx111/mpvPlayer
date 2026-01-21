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
