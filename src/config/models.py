from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class MqttConfig:
    host: str = "127.0.0.1"
    port: int = 1883
    clientId: str = "mpv-player"
    username: str = ""
    password: str = ""
    keepalive: int = 60
    cleanSession: bool = True
    enabled: bool = False
    devicePath: str = "设备/默认"
    statusReportInterval: int = 30000
    heartbeatInterval: int = 15000


@dataclass
class DownloadConfig:
    path: str = ""
    maxConcurrent: int = 3
    retryLimit: int = 3
    retryBackoff: List[int] = field(default_factory=lambda: [1, 2, 4, 8, 16, 30])
    extractDefault: bool = False


@dataclass
class PlayerConfig:
    videoPath: str = ""
    autoPlay: bool = True
    loop: bool = True
    showControls: bool = True
    volume: int = 70
    preloadNext: bool = False


@dataclass
class SystemConfig:
    devicePath: str = "设备/默认"
    enableAutoRestart: bool = False
    logLevel: str = "INFO"
    logPath: str = ""
    autostart: bool = False


@dataclass
class AppConfig:
    mqtt: MqttConfig = field(default_factory=MqttConfig)
    download: DownloadConfig = field(default_factory=DownloadConfig)
    player: PlayerConfig = field(default_factory=PlayerConfig)
    system: SystemConfig = field(default_factory=SystemConfig)

    def clamp(self) -> None:
        self.mqtt.keepalive = max(10, min(self.mqtt.keepalive, 300))
        self.mqtt.statusReportInterval = max(5000, min(self.mqtt.statusReportInterval, 300000))
        self.mqtt.heartbeatInterval = max(5000, min(self.mqtt.heartbeatInterval, 120000))
        self.download.maxConcurrent = max(1, min(self.download.maxConcurrent, 10))
        self.player.volume = max(0, min(self.player.volume, 100))
