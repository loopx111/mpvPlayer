import json
import time
import threading
from typing import Any, Dict, List
from ..config.models import AppConfig
from ..utils.logger import get_logger
from .mqtt_client import MqttClient


class MqttService:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.log = get_logger("mqtt.service")
        self.client = MqttClient(cfg.mqtt)
        self.last_status_ts = 0
        self.heartbeat_thread = None
        self._running = True

    def start(self, command_topics: List[str]) -> None:
        if not self.cfg.mqtt.enabled:
            self.log.info("MQTT 服务已禁用，跳过连接")
            return
            
        self.log.info("启动MQTT服务，订阅主题: %s", command_topics)
        
        # 设置连接成功回调
        self.client.on_connect_success = self._on_connect_success
        
        for t in command_topics:
            self.client.subscribe(t, self._handle_command)
        
        try:
            self.client.connect()
            self.log.info("MQTT服务启动成功")
        except Exception as e:
            self.log.error("MQTT 连接失败: %s，但应用将继续运行", e)

    def publish_status(self, status: Dict[str, Any]) -> None:
        topic = "ohos/status"
        status["ts"] = int(time.time() * 1000)
        self.client.publish(topic, status)

    def publish_download(self, payload: Dict[str, Any]) -> None:
        topic = "ohos/download"
        payload["ts"] = int(time.time() * 1000)
        self.client.publish(topic, payload)

    def _handle_command(self, topic: str, payload: str) -> None:
        """处理MQTT命令，打印订阅内容"""
        self.log.info(f"收到MQTT消息 - 主题: {topic}, 内容: {payload}")
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            self.log.warning("Invalid JSON on %s", topic)
            return
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
                    self.log.error("心跳线程异常: %s", e)
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
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)
        self.client.disconnect()
