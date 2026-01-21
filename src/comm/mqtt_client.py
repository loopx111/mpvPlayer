import json
import time
import threading
import queue
from typing import Callable, Dict, List, Optional, Union
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
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay_base = 1  # 初始重连延迟秒数
        self._message_queue = queue.Queue()  # 消息队列，用于重连时缓存消息
        self._running = True
        self._network_thread = None
        self._reconnect_thread = None
        self.on_connect_success: Optional[Callable] = None  # 连接成功回调

    def connect(self) -> None:
        """连接MQTT服务器，支持自动重连"""
        self._running = True
        self._start_network_thread()

    def disconnect(self) -> None:
        """断开连接"""
        self._running = False
        try:
            self.client.disconnect()
        except:
            pass
        if self._network_thread:
            self._network_thread.join(timeout=5)
        if self._reconnect_thread:
            self._reconnect_thread.join(timeout=5)

    def _start_network_thread(self) -> None:
        """启动网络线程"""
        if self._network_thread and self._network_thread.is_alive():
            return
            
        def network_loop():
            while self._running:
                try:
                    self.log.info(f"尝试连接MQTT服务器: {self.cfg.host}:{self.cfg.port}", "network_thread")
                    self.client.connect(self.cfg.host, self.cfg.port, keepalive=self.cfg.keepalive)
                    self.client.loop_forever()
                except ConnectionRefusedError:
                    self.log.error("MQTT连接被拒绝，请检查MQTT服务器是否运行", "network_thread")
                    time.sleep(5)  # 延长等待时间
                except Exception as e:
                    self.log.error("MQTT网络线程异常", "network_thread", e)
                    if self._running:
                        time.sleep(1)  # 短暂等待后重试

        self._network_thread = threading.Thread(target=network_loop, daemon=True)
        self._network_thread.start()

    def _schedule_reconnect(self) -> None:
        """调度重连"""
        if not self._running:
            return
            
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            self.log.error("MQTT重连尝试次数已达上限，停止重连", "reconnect")
            return

        delay = self._reconnect_delay_base * (2 ** self._reconnect_attempts)  # 指数退避
        delay = min(delay, 60)  # 最大延迟60秒
        
        self.log.info(f"MQTT将在{delay}秒后尝试重连（第{self._reconnect_attempts + 1}次）", "reconnect")
        
        def delayed_reconnect():
            time.sleep(delay)
            if self._running and not self.connected:
                self._start_network_thread()

        self._reconnect_thread = threading.Thread(target=delayed_reconnect, daemon=True)
        self._reconnect_thread.start()
        self._reconnect_attempts += 1

    def subscribe(self, topic: str, cb: Optional[MessageCallback] = None) -> None:
        with self._lock:
            if cb:
                self.callbacks.setdefault(topic, []).append(cb)
        if self.connected:
            try:
                self.client.subscribe(topic, qos=0)
            except Exception as e:
                self.log.error("订阅失败", "subscribe", e)
        else:
            self.log.warning("订阅时未连接，连接后将自动订阅", "subscribe")

    def publish(self, topic: str, payload: Union[dict, str]) -> None:
        """发布消息，支持重连时消息缓存"""
        if isinstance(payload, dict):
            payload = json.dumps(payload, ensure_ascii=False)
        
        if not self.connected:
            # 未连接时缓存消息
            try:
                self._message_queue.put((topic, payload), timeout=1)
                self.log.debug(f"消息已缓存（未连接）: {topic}", "publish")
            except queue.Full:
                self.log.warning(f"消息队列已满，丢弃消息: {topic}", "publish")
            return
            
        try:
            self.client.publish(topic, payload=payload, qos=0)
        except Exception as e:
            self.log.error("发布消息失败", "publish", e)

    def _flush_message_queue(self) -> None:
        """清空消息队列"""
        while not self._message_queue.empty():
            try:
                topic, payload = self._message_queue.get_nowait()
                try:
                    self.client.publish(topic, payload=payload, qos=0)
                    self.log.debug(f"已发送缓存消息: {topic}", "flush_queue")
                except Exception as e:
                    self.log.error("发送缓存消息失败", "flush_queue", e)
            except queue.Empty:
                break

    def _on_connect(self, client: mqtt.Client, userdata, flags, rc):
        # MQTT连接结果代码说明
        rc_messages = {
            0: "连接成功",
            1: "连接被拒绝 - 不支持的协议版本",
            2: "连接被拒绝 - 客户端标识符无效",
            3: "连接被拒绝 - 服务器不可用",
            4: "连接被拒绝 - 错误的用户名或密码",
            5: "连接被拒绝 - 未授权"
        }
        
        if rc == 0:
            self.connected = True
            self._reconnect_attempts = 0  # 重置重连计数
            self.log.info(f"MQTT连接成功 - {self.cfg.host}:{self.cfg.port}", "connect")
            
            # 重新订阅所有主题
            with self._lock:
                for topic in self.callbacks.keys():
                    try:
                        client.subscribe(topic, qos=0)
                        self.log.debug(f"已订阅主题: {topic}", "subscribe")
                    except Exception as e:
                        self.log.error("重新订阅失败", "subscribe", e)
            
            # 发送缓存的消息
            self._flush_message_queue()
            
            # 调用连接成功回调
            if self.on_connect_success:
                try:
                    self.on_connect_success()
                except Exception as e:
                    self.log.error("连接成功回调执行失败", "callback", e)
            
        else:
            self.connected = False
            error_msg = rc_messages.get(rc, f"未知错误代码: {rc}")
            self.log.error(f"MQTT连接失败 - {error_msg} (rc={rc})", "connect")
            self._schedule_reconnect()

    def _on_message(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
        payload = msg.payload.decode("utf-8", errors="ignore")
        topic = msg.topic
        self.log.debug(f"MQTT消息 {topic} {payload}", "message_received")
        with self._lock:
            cbs = list(self.callbacks.get(topic, []))
        
        # 在独立线程中处理消息回调，避免阻塞MQTT网络线程
        def handle_callbacks():
            for cb in cbs:
                try:
                    cb(topic, payload)
                except Exception as exc:
                    self.log.error("消息回调错误", "callback", exc)
        
        callback_thread = threading.Thread(target=handle_callbacks, daemon=True)
        callback_thread.start()

    def _on_disconnect(self, client: mqtt.Client, userdata, rc):
        self.connected = False
        if rc == 0:
            self.log.info("MQTT正常断开连接", "disconnect")
        else:
            self.log.warning(f"MQTT意外断开连接 rc={rc}", "disconnect")
            if self._running:
                self._schedule_reconnect()
