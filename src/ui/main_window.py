from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, QTimer, QDateTime
from typing import Optional
from ..config.models import AppConfig
from ..comm.mqtt_service import MqttService
from ..file_dist.manager import DownloadManager
from ..player.mpv_controller import MpvController


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg: AppConfig, mqtt: Optional[MqttService], downloader: DownloadManager, player: MpvController):
        super().__init__()
        self.cfg = cfg
        self.mqtt = mqtt
        self.downloader = downloader
        self.player = player
        self.setWindowTitle("广告屏播放器控制台")
        self.resize(1200, 800)
        self.setMinimumSize(1000, 600)
        self._build_ui()
        self._setup_timer()

    def _build_ui(self) -> None:
        # 创建主布局
        central = QtWidgets.QWidget()
        main_layout = QtWidgets.QHBoxLayout()
        
        # 左侧：状态面板
        left_panel = self._create_status_panel()
        
        # 右侧：控制面板
        right_panel = self._create_control_panel()
        
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 2)
        
        central.setLayout(main_layout)
        self.setCentralWidget(central)

    def _create_status_panel(self) -> QtWidgets.QGroupBox:
        """创建状态监控面板"""
        panel = QtWidgets.QGroupBox("系统状态")
        layout = QtWidgets.QVBoxLayout()
        
        # 系统信息
        sys_group = QtWidgets.QGroupBox("系统信息")
        sys_layout = QtWidgets.QFormLayout()
        
        self.time_label = QtWidgets.QLabel("加载中...")
        self.uptime_label = QtWidgets.QLabel("0 小时 0 分钟")
        self.mqtt_status = QtWidgets.QLabel("未连接")
        self.mqtt_status.setStyleSheet("color: red; font-weight: bold;")
        
        sys_layout.addRow("当前时间:", self.time_label)
        sys_layout.addRow("运行时间:", self.uptime_label)
        sys_layout.addRow("MQTT状态:", self.mqtt_status)
        sys_group.setLayout(sys_layout)
        
        # 播放状态
        play_group = QtWidgets.QGroupBox("播放状态")
        play_layout = QtWidgets.QFormLayout()
        
        self.current_file = QtWidgets.QLabel("无")
        self.play_status = QtWidgets.QLabel("未播放")
        self.play_status.setStyleSheet("color: orange; font-weight: bold;")
        self.queue_count = QtWidgets.QLabel("0")
        
        play_layout.addRow("当前文件:", self.current_file)
        play_layout.addRow("播放状态:", self.play_status)
        play_layout.addRow("播放队列:", self.queue_count)
        play_group.setLayout(play_layout)
        
        # 下载状态
        download_group = QtWidgets.QGroupBox("下载状态")
        download_layout = QtWidgets.QFormLayout()
        
        self.download_queue = QtWidgets.QLabel("0")
        self.download_progress = QtWidgets.QLabel("0%")
        self.last_update = QtWidgets.QLabel("无")
        
        download_layout.addRow("下载队列:", self.download_queue)
        download_layout.addRow("下载进度:", self.download_progress)
        download_layout.addRow("最后更新:", self.last_update)
        download_group.setLayout(download_layout)
        
        layout.addWidget(sys_group)
        layout.addWidget(play_group)
        layout.addWidget(download_group)
        layout.addStretch(1)
        
        panel.setLayout(layout)
        return panel

    def _create_control_panel(self) -> QtWidgets.QGroupBox:
        """创建控制面板"""
        panel = QtWidgets.QGroupBox("播放控制")
        layout = QtWidgets.QVBoxLayout()
        
        # 播放列表
        playlist_group = QtWidgets.QGroupBox("播放列表")
        playlist_layout = QtWidgets.QVBoxLayout()
        
        self.playlist_widget = QtWidgets.QListWidget()
        self.playlist_widget.setMaximumHeight(200)
        playlist_layout.addWidget(self.playlist_widget)
        playlist_group.setLayout(playlist_layout)
        
        # 控制按钮
        control_group = QtWidgets.QGroupBox("控制操作")
        control_layout = QtWidgets.QGridLayout()
        
        self.play_btn = QtWidgets.QPushButton("播放/暂停")
        self.stop_btn = QtWidgets.QPushButton("停止")
        self.next_btn = QtWidgets.QPushButton("下一首")
        self.volume_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_label = QtWidgets.QLabel("音量: 70%")
        
        control_layout.addWidget(self.play_btn, 0, 0)
        control_layout.addWidget(self.stop_btn, 0, 1)
        control_layout.addWidget(self.next_btn, 1, 0)
        control_layout.addWidget(self.volume_slider, 2, 0, 1, 2)
        control_layout.addWidget(self.volume_label, 3, 0, 1, 2)
        control_group.setLayout(control_layout)
        
        # 连接信号
        self.play_btn.clicked.connect(self._toggle_play)
        self.stop_btn.clicked.connect(self._stop_play)
        self.next_btn.clicked.connect(self._next_file)
        self.volume_slider.valueChanged.connect(self._volume_changed)
        
        layout.addWidget(playlist_group)
        layout.addWidget(control_group)
        layout.addStretch(1)
        
        panel.setLayout(layout)
        return panel

    def _setup_timer(self) -> None:
        """设置定时刷新"""
        self.start_time = QDateTime.currentDateTime()
        
        timer = QTimer(self)
        timer.setInterval(1000)
        timer.timeout.connect(self.refresh)
        timer.start()

    def refresh(self) -> None:
        """刷新界面状态"""
        # 更新时间
        current_time = QDateTime.currentDateTime()
        self.time_label.setText(current_time.toString("yyyy-MM-dd hh:mm:ss"))
        
        # 计算运行时间
        uptime_secs = self.start_time.secsTo(current_time)
        hours = uptime_secs // 3600
        minutes = (uptime_secs % 3600) // 60
        self.uptime_label.setText(f"{hours} 小时 {minutes} 分钟")
        
        # 更新MQTT状态
        if self.mqtt and hasattr(self.mqtt, 'client'):
            mqtt_connected = self.mqtt.client.connected
            self.mqtt_status.setText("已连接" if mqtt_connected else "未连接")
            self.mqtt_status.setStyleSheet(f"color: {'green' if mqtt_connected else 'red'}; font-weight: bold;")
        else:
            self.mqtt_status.setText("未启用")
            self.mqtt_status.setStyleSheet("color: gray; font-weight: bold;")
        
        # 更新播放状态
        if self.player.current_process:
            self.play_status.setText("播放中")
            self.play_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.play_status.setText("未播放")
            self.play_status.setStyleSheet("color: orange; font-weight: bold;")
        
        # 更新播放队列
        queue_len = len(self.player.queue) if hasattr(self.player, 'queue') else 0
        self.queue_count.setText(str(queue_len))
        
        # 更新下载状态
        download_tasks = len(self.downloader.tasks) if hasattr(self.downloader, 'tasks') else 0
        self.download_queue.setText(str(download_tasks))
        
        # 更新播放列表
        self._update_playlist()

    def _update_playlist(self) -> None:
        """更新播放列表显示"""
        if not hasattr(self.player, 'queue'):
            return
            
        self.playlist_widget.clear()
        for i, file_path in enumerate(self.player.queue):
            item = QtWidgets.QListWidgetItem(f"{i+1}. {file_path.name}")
            self.playlist_widget.addItem(item)

    def _toggle_play(self) -> None:
        """播放/暂停"""
        print("播放/暂停按钮被点击")
        self.player.toggle_pause()

    def _stop_play(self) -> None:
        """停止播放"""
        print("停止按钮被点击")
        self.player.stop_play()

    def _next_file(self) -> None:
        """下一首"""
        print("下一首按钮被点击")
        self.player.next_file()

    def _volume_changed(self, value: int) -> None:
        """音量改变"""
        self.volume_label.setText(f"音量: {value}%")
        self.player.set_volume(value)
