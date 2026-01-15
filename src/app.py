import asyncio
import sys
import threading
import queue
import time
from typing import Any, Dict, Optional, Callable, List
from PySide6 import QtWidgets, QtCore
from .config.loader import load_config
from .utils.logger import setup_logging
from .utils.health_check import HealthCheck
from .comm.mqtt_service import MqttService
from .file_dist.manager import DownloadManager
from .player.mpv_controller import MpvController
from .ui.main_window import MainWindow


class MessageBus:
    """异步消息总线，用于组件间通信"""
    
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._message_queue = queue.Queue()
        self._running = True
        self._worker_thread = threading.Thread(target=self._process_messages, daemon=True)
        self._worker_thread.start()
    
    def subscribe(self, message_type: str, callback: Callable) -> None:
        """订阅消息"""
        self._subscribers.setdefault(message_type, []).append(callback)
    
    def publish(self, message_type: str, data: Any = None) -> None:
        """发布消息"""
        try:
            self._message_queue.put((message_type, data), timeout=1)
        except queue.Full:
            print("消息队列已满，丢弃消息:", message_type)
    
    def _process_messages(self) -> None:
        """处理消息"""
        while self._running:
            try:
                message_type, data = self._message_queue.get(timeout=1)
                callbacks = self._subscribers.get(message_type, [])
                
                # 在独立线程中执行回调，避免阻塞消息总线
                for callback in callbacks:
                    def execute_callback():
                        try:
                            callback(data)
                        except Exception as e:
                            print(f"消息回调错误 {message_type}: {e}")
                    
                    threading.Thread(target=execute_callback, daemon=True).start()
                
                self._message_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"消息处理错误: {e}")
                time.sleep(0.1)
    
    def cleanup(self) -> None:
        """清理资源"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)


def build_command_topics(device_path: str, client_id: str) -> List[str]:
    # 分层订阅：设备 ID、设备路径逐级、顶层
    segments = device_path.strip("/").split("/") if device_path else []
    topics = [f"设备/{client_id}/命令"]
    if segments:
        topics.append(f"{device_path}/命令")
        # 逐级向上
        for i in range(len(segments) - 1, 0, -1):
            prefix = "/".join(segments[:i])
            topics.append(f"{prefix}/命令")
    topics.append("设备/命令")
    # 去重保序
    seen = set()
    unique = []
    for t in topics:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


class ApplicationManager:
    """应用管理器，负责组件协调和健康监控"""
    
    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.log = setup_logging(cfg.system.logLevel)
        self.message_bus = MessageBus()
        self.health_check = HealthCheck(check_interval=30)
        self.mqtt_service: Optional[MqttService] = None
        self.downloader: Optional[DownloadManager] = None
        self.player: Optional[MpvController] = None
        self.ui_window: Optional[MainWindow] = None
        
        # 设置消息订阅
        self._setup_message_subscriptions()
    
    def _setup_message_subscriptions(self) -> None:
        """设置消息订阅"""
        # 组件状态变化消息
        self.message_bus.subscribe("component.status", self._handle_component_status)
        
        # MQTT命令消息
        self.message_bus.subscribe("mqtt.command", self._handle_mqtt_command)
        
        # 播放控制消息
        self.message_bus.subscribe("player.control", self._handle_player_control)
    
    def _handle_component_status(self, data: Dict) -> None:
        """处理组件状态变化"""
        component = data.get('component')
        status = data.get('status')
        if component and status is not None:
            self.log.info(f"组件 {component} 状态: {'健康' if status else '异常'}", "component_status")
    
    def _handle_mqtt_command(self, data: Dict) -> None:
        """处理MQTT命令"""
        command = data.get('command')
        if command == "restart":
            self.log.info("收到重启命令", "mqtt_command")
            self.message_bus.publish("system.restart")
        elif command == "download":
            self.log.info("收到下载命令", "mqtt_command")
            # 处理下载逻辑
        elif command == "query":
            self.log.info("收到查询命令", "mqtt_command")
            # 发布状态信息
    
    def _handle_player_control(self, data: Dict) -> None:
        """处理播放控制"""
        action = data.get('action')
        if self.player:
            if action == "play_pause":
                self.player.toggle_pause()
            elif action == "stop":
                self.player.stop_play()
            elif action == "next":
                self.player.next_file()
    
    def start_components(self) -> None:
        """启动所有组件"""
        # 启动MQTT服务
        if self.cfg.mqtt.enabled:
            self.mqtt_service = MqttService(self.cfg)
            topics = build_command_topics(self.cfg.mqtt.devicePath or self.cfg.system.devicePath, self.cfg.mqtt.clientId)
            self.mqtt_service.start(topics)
            
            # 注册MQTT健康检查
            def check_mqtt() -> bool:
                return self.mqtt_service.client.connected if self.mqtt_service else False
            
            def recover_mqtt() -> None:
                if self.mqtt_service:
                    self.log.info("尝试重新连接MQTT", "mqtt_recovery")
                    self.mqtt_service.client.disconnect()
                    time.sleep(2)
                    self.mqtt_service.start(topics)
            
            self.health_check.register_component(
                "mqtt", 
                check_mqtt, 
                recover_mqtt,
                max_failures=2
            )
        
        # 启动下载管理器
        self.downloader = DownloadManager(self.cfg.download)
        
        # 注册下载器健康检查
        def check_downloader() -> bool:
            # 下载器通常总是健康的，除非有特定错误
            return True
        
        self.health_check.register_component("downloader", check_downloader)
        
        # 启动播放器
        self.player = MpvController(
            self.cfg.player.videoPath, 
            volume=self.cfg.player.volume, 
            loop=self.cfg.player.loop, 
            show_controls=self.cfg.player.showControls
        )
        
        # 注册播放器健康检查
        def check_player() -> bool:
            # 播放器健康检查：如果队列为空或正在播放，则认为健康
            if not hasattr(self.player, 'queue'):
                return False
            return len(self.player.queue) > 0 or self.player.current_process is not None
        
        def recover_player() -> None:
            if self.player and hasattr(self.player, 'queue') and self.player.queue:
                self.log.info("尝试重新启动播放器")
                self.player.stop_play()
                time.sleep(1)
                self.player.play(self.player.queue[0])
        
        self.health_check.register_component(
            "player", 
            check_player, 
            recover_player,
            max_failures=3
        )
        
        # 启动UI（在主线程中）
        app = QtWidgets.QApplication(sys.argv)
        self.ui_window = MainWindow(self.cfg, self.mqtt_service, self.downloader, self.player)
        self.ui_window.show()
        
        # 注册UI健康检查
        def check_ui() -> bool:
            # UI通常总是健康的，除非有特定错误
            return self.ui_window is not None and self.ui_window.isVisible()
        
        self.health_check.register_component("ui", check_ui)
        
        # 启动健康检查
        self.health_check.start()
        
        # 运行Qt主循环
        sys.exit(app.exec())
    
    def _start_health_check(self) -> None:
        """启动健康检查"""
        def health_check():
            while True:
                time.sleep(30)  # 每30秒检查一次
                
                # 检查MQTT连接状态
                if self.mqtt_service and self.cfg.mqtt.enabled:
                    mqtt_healthy = self.mqtt_service.client.connected
                    self.message_bus.publish("component.status", {
                        "component": "mqtt", 
                        "status": mqtt_healthy
                    })
                
                # 检查播放器状态
                if self.player:
                    player_healthy = self.player.current_process is not None or len(self.player.queue) == 0
                    self.message_bus.publish("component.status", {
                        "component": "player", 
                        "status": player_healthy
                    })
        
        health_thread = threading.Thread(target=health_check, daemon=True)
        health_thread.start()
    
    def cleanup(self) -> None:
        """清理资源"""
        self.health_check.stop()
        self.message_bus.cleanup()
        if self.player:
            self.player.cleanup()
        if self.mqtt_service:
            self.mqtt_service.stop()


def main() -> None:
    import argparse
    from pathlib import Path
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='MPV Player Application')
    parser.add_argument('-c', '--config', help='指定配置文件路径', default=None)
    args = parser.parse_args()
    
    # 加载配置
    if args.config:
        config_path = Path(args.config)
        cfg = load_config(config_path)
    else:
        cfg = load_config()
    
    app_manager = ApplicationManager(cfg)
    
    try:
        app_manager.start_components()
    except KeyboardInterrupt:
        print("收到中断信号，正在关闭...")
    except Exception as e:
        print(f"应用启动失败: {e}")
    finally:
        app_manager.cleanup()


if __name__ == "__main__":
    main()
