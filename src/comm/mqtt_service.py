import json
import time
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

    def start(self, command_topics: List[str]) -> None:
        if not self.cfg.mqtt.enabled:
            self.log.info("MQTT 服务已禁用，跳过连接")
            return
            
        for t in command_topics:
            self.client.subscribe(t, self._handle_command)
        
        try:
            self.client.connect()
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
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            self.log.warning("Invalid JSON on %s", topic)
            return
        command = data.get("command") or data.get("cmd")
        if not command:
            return
        if command == "restart":
            self.log.info("Received restart command")
            # Hook for restart handling
        elif command == "download":
            self.log.info("Received download command")
            # Hook: enqueue download
        elif command == "query":
            self.log.info("Received query command")
            self.publish_status({"status": "ready"})
        else:
            self.log.warning("Unknown command %s", command)
