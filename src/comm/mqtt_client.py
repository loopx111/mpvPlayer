import json
import time
import threading
from typing import Callable, Dict, List, Optional
import paho.mqtt.client as mqtt
from ..config.models import MqttConfig
from ..utils.logger import get_logger

MessageCallback = Callable[[str, str], None]


class MqttClient:
    def __init__(self, cfg: MqttConfig) -> None:
        self.cfg = cfg
        self.log = get_logger("mqtt")
        self.client = mqtt.Client(client_id=cfg.clientId, clean_session=cfg.cleanSession)
        if cfg.username:
            self.client.username_pw_set(cfg.username, cfg.password)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.callbacks: Dict[str, List[MessageCallback]] = {}
        self.connected = False
        self._lock = threading.Lock()

    def connect(self) -> None:
        self.client.connect(self.cfg.host, self.cfg.port, keepalive=self.cfg.keepalive)
        thread = threading.Thread(target=self.client.loop_forever, daemon=True)
        thread.start()

    def disconnect(self) -> None:
        self.client.disconnect()

    def subscribe(self, topic: str, cb: Optional[MessageCallback] = None) -> None:
        with self._lock:
            if cb:
                self.callbacks.setdefault(topic, []).append(cb)
        if self.connected:
            self.client.subscribe(topic, qos=0)
        else:
            self.log.warning("Subscribe called while disconnected, will retry after connect")

    def publish(self, topic: str, payload: dict | str) -> None:
        if isinstance(payload, dict):
            payload = json.dumps(payload, ensure_ascii=False)
        self.client.publish(topic, payload=payload, qos=0)

    def _on_connect(self, client: mqtt.Client, userdata, flags, rc):
        self.connected = True
        if rc == 0:
            self.log.info("MQTT connected")
        else:
            self.log.error("MQTT connect failed rc=%s", rc)
        with self._lock:
            for t in self.callbacks.keys():
                client.subscribe(t, qos=0)

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
        payload = msg.payload.decode("utf-8", errors="ignore")
        topic = msg.topic
        self.log.debug("MQTT msg %s %s", topic, payload)
        with self._lock:
            cbs = list(self.callbacks.get(topic, []))
        for cb in cbs:
            try:
                cb(topic, payload)
            except Exception as exc:
                self.log.exception("callback error: %s", exc)

    def _on_disconnect(self, client: mqtt.Client, userdata, rc):
        self.connected = False
        self.log.warning("MQTT disconnected rc=%s", rc)
