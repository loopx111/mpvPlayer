import asyncio
import sys
from PySide6 import QtWidgets
from .config.loader import load_config
from .utils.logger import setup_logging
from .comm.mqtt_service import MqttService
from .file_dist.manager import DownloadManager
from .player.mpv_controller import MpvController
from .ui.main_window import MainWindow


def build_command_topics(device_path: str, client_id: str) -> list[str]:
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


def main() -> None:
    cfg = load_config()
    setup_logging(cfg.system.logLevel)

    mqtt_service = MqttService(cfg)
    downloader = DownloadManager(cfg.download)
    player = MpvController(cfg.player.videoPath, volume=cfg.player.volume, loop=cfg.player.loop, show_controls=cfg.player.showControls)

    topics = build_command_topics(cfg.mqtt.devicePath or cfg.system.devicePath, cfg.mqtt.clientId)
    mqtt_service.start(topics)

    # 启动 Qt UI
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(cfg, mqtt_service, downloader)
    window.show()

    loop = asyncio.get_event_loop()

    def run_asyncio():
        loop.run_forever()

    import threading
    t = threading.Thread(target=run_asyncio, daemon=True)
    t.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
