from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt, QTimer
from ..config.models import AppConfig
from ..comm.mqtt_service import MqttService
from ..file_dist.manager import DownloadManager


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg: AppConfig, mqtt: MqttService, downloader: DownloadManager):
        super().__init__()
        self.cfg = cfg
        self.mqtt = mqtt
        self.downloader = downloader
        self.setWindowTitle("mpvPlayer 控制台")
        self.resize(960, 640)
        self._build_ui()
        self._setup_timer()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()

        self.status_label = QtWidgets.QLabel("MQTT: 未连接")
        self.download_label = QtWidgets.QLabel("下载队列：0")
        self.play_label = QtWidgets.QLabel("播放：未开始")

        font = QtGui.QFont()
        font.setPointSize(11)
        for lbl in [self.status_label, self.download_label, self.play_label]:
            lbl.setFont(font)

        layout.addWidget(self.status_label)
        layout.addWidget(self.download_label)
        layout.addWidget(self.play_label)
        layout.addStretch(1)

        central.setLayout(layout)
        self.setCentralWidget(central)

    def _setup_timer(self) -> None:
        timer = QTimer(self)
        timer.setInterval(1000)
        timer.timeout.connect(self.refresh)
        timer.start()

    def refresh(self) -> None:
        self.status_label.setText(f"MQTT: {'已连接' if self.mqtt.client.connected else '未连接'}")
        self.download_label.setText(f"下载队列：{len(self.downloader.tasks)}")
