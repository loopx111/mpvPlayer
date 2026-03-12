import asyncio
import sys
import threading
import queue
import time
import signal
import atexit
from typing import Any, Dict, Optional, Callable, List
from PySide6 import QtWidgets, QtCore
from .config.loader import load_config
from .utils.logger import setup_logging
from .utils.health_check import HealthCheck
from .comm.mqtt_service import MqttService
from .file_dist.manager import DownloadManager
from .player.mpv_controller import MpvController
from .ui.main_window import MainWindow
from .ai.gesture_controller import GestureController
from .camera.embedded_mediapipe_controller import EmbeddedMediaPipeCameraController


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
        self.face_detector: Optional[EmbeddedMediaPipeCameraController] = None
        self.gesture_controller: Optional[GestureController] = None
        self.detection_mode: str = "face"  # "face" 或 "gesture"
        self.face_detection_enabled: bool = True  # 控制MainWindow是否启用人脸检测
        
        # 设置消息订阅
        self._setup_message_subscriptions()
        
        # 注册信号处理器
        self._setup_signal_handlers()
        
        # 注册退出处理器
        atexit.register(self.cleanup)
    
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
    
    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else f'信号 {signum}'
            self.log.info(f"收到信号 {signal_name} ({signum})，准备退出...")
            self.cleanup()
            sys.exit(0)
        
        # 注册信号处理器
        try:
            # SIGHUP：终端关闭时发送
            signal.signal(signal.SIGHUP, signal_handler)
            # SIGINT：Ctrl+C
            signal.signal(signal.SIGINT, signal_handler)
            # SIGTERM：终止信号
            signal.signal(signal.SIGTERM, signal_handler)
            self.log.info("已注册信号处理器: SIGHUP, SIGINT, SIGTERM")
        except Exception as e:
            self.log.warning(f"注册信号处理器失败: {e}")
    
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
        
        # 将播放器实例设置到MQTT服务中（用于播放列表分发）
        if self.mqtt_service:
            self.mqtt_service.set_player_instance(self.player)
        
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
        print("=== 开始创建Qt应用 ===")
        app = QtWidgets.QApplication(sys.argv)
        print("Qt应用实例创建成功")
        
        # 启动检测模块（根据模式选择）
        self._start_detection_module()
        
        print("=== 开始创建主窗口 ===")
        # 传递已创建的手势控制器实例，避免重复创建
        self.ui_window = MainWindow(self.cfg, self.mqtt_service, self.downloader, self.player, self.face_detection_enabled, self.detection_mode, self.gesture_controller)
        print(f"主窗口创建成功，窗口对象: {self.ui_window}")
        
        print("=== 显示主窗口 ===")
        self.ui_window.show()
        print(f"窗口显示状态: {self.ui_window.isVisible()}")
        print(f"窗口几何信息: {self.ui_window.geometry()}")
        print(f"窗口标题: {self.ui_window.windowTitle()}")
        
        # 注册UI健康检查
        def check_ui() -> bool:
            # UI通常总是健康的，除非有特定错误
            ui_visible = self.ui_window is not None and self.ui_window.isVisible()
            print(f"UI健康检查: 窗口存在={self.ui_window is not None}, 可见={ui_visible}")
            return ui_visible
        
        self.health_check.register_component("ui", check_ui)
        
        # 启动健康检查
        self.health_check.start()
        print("健康检查已启动")
        
        # 设置Qt应用关闭时的清理
        def handle_quit():
            self.log.info("Qt应用收到关闭信号，执行清理")
            self.cleanup()
        
        # 连接Qt的退出信号
        app.aboutToQuit.connect(handle_quit)
        
        # 设置窗口关闭事件处理
        def handle_close_event(event):
            self.log.info("窗口收到关闭事件，执行清理")
            self.cleanup()
            event.accept()
        
        self.ui_window.closeEvent = handle_close_event
        
        # 运行Qt主循环
        try:
            print("=== 开始Qt事件循环 ===")
            sys.exit(app.exec())
        except KeyboardInterrupt:
            self.log.info("收到键盘中断信号，执行清理")
            self.cleanup()
        except Exception as e:
            self.log.error(f"应用执行异常: {e}")
            self.cleanup()
    
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
    
    def _start_detection_module(self) -> None:
        """启动检测模块（根据模式选择）"""
        if self.detection_mode == "face":
            self._start_face_detection()
        elif self.detection_mode == "gesture":
            self._start_gesture_recognition()
        else:
            print(f"未知检测模式: {self.detection_mode}")
    
    def _start_face_detection(self) -> None:
        """启动人脸检测"""
        try:
            # 设置MainWindow中人脸检测的启用状态
            # 在MainWindow初始化时会检查这个状态
            self.face_detection_enabled = True
            print("人脸检测模式已设置")
        except Exception as e:
            print(f"设置人脸检测模式失败: {e}")
    
    def _start_gesture_recognition(self) -> None:
        """启动手势识别"""
        try:
            # 设置MainWindow中人脸检测的禁用状态
            self.face_detection_enabled = False
            
            self.gesture_controller = GestureController(config=self.cfg.to_dict(), player=self.player)
            
            # 手势回调函数
            def gesture_callback(data: Dict):
                action = data.get('action')
                gesture = data.get('gesture')
                print(f"检测到手势: {gesture} -> 执行动作: {action}")
                
                # 根据手势执行播放器控制
                if action == "play" and self.player:
                    self.player.play_pause()
                elif action == "pause" and self.player:
                    self.player.play_pause()
                elif action == "next" and self.player:
                    self.player.next_file()
                elif action == "volume_up" and self.player:
                    self.player.set_volume(self.player.volume + 10)
                elif action == "volume_down" and self.player:
                    self.player.set_volume(self.player.volume - 10)
            
            # 启动手势识别（自动选择摄像头）
            if self.gesture_controller.start(callback=gesture_callback):
                print("手势识别模块已启动")
            else:
                print("手势识别模块启动失败")
                
        except Exception as e:
            print(f"启动手势识别失败: {e}")
    
    def switch_detection_mode(self, mode: str) -> bool:
        """
        切换检测模式
        
        Args:
            mode: 检测模式 ("face" 或 "gesture")
            
        Returns:
            切换是否成功
        """
        if mode not in ["face", "gesture"]:
            print(f"无效的检测模式: {mode}")
            return False
        
        # 停止当前模式
        if self.detection_mode == "face" and self.face_detector:
            # 停止人脸检测
            pass
        elif self.detection_mode == "gesture" and self.gesture_controller:
            self.gesture_controller.stop()
        
        # 切换模式
        self.detection_mode = mode
        
        # 启动新模式
        self._start_detection_module()
        
        print(f"检测模式已切换到: {mode}")
        return True
    
    def cleanup(self) -> None:
        """清理资源"""
        self.health_check.stop()
        self.message_bus.cleanup()
        if self.player:
            self.player.cleanup()
        if self.mqtt_service:
            self.mqtt_service.stop()
        if self.gesture_controller:
            self.gesture_controller.stop()
        if self.face_detector:
            # 停止人脸检测
            if hasattr(self.face_detector, 'stop_camera'):
                self.face_detector.stop_camera()
        # 清理摄像头控制器（如果存在）
        if hasattr(self, 'ui_window') and self.ui_window:
            if hasattr(self.ui_window, 'camera_controller') and self.ui_window.camera_controller:
                try:
                    print("开始清理摄像头控制器...")
                    self.ui_window.camera_controller.stop_camera()
                    print("摄像头控制器清理完成")
                except Exception as e:
                    print(f"清理摄像头控制器时出错: {e}")


def main() -> None:
    import argparse
    from pathlib import Path
    import os
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='MPV Player Application')
    parser.add_argument('-c', '--config', help='指定配置文件路径', default=None)
    parser.add_argument('--remote-mode', action='store_true', help='远程模式优化，避免连接断开')
    parser.add_argument('--detection-mode', choices=['face', 'gesture'], default='face', 
                       help='检测模式: face=人脸检测, gesture=手势识别')
    args = parser.parse_args()
    
    # 设置远程模式环境变量
    if args.remote_mode:
        os.environ['MPV_REMOTE_MODE'] = 'true'
        print("启用远程模式优化")
    
    # 加载配置
    if args.config:
        config_path = Path(args.config)
        cfg = load_config(config_path)
    else:
        cfg = load_config()
    
    app_manager = ApplicationManager(cfg)
    
    # 设置检测模式
    app_manager.detection_mode = args.detection_mode
    
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
