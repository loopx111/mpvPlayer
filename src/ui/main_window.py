import time
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, QTimer, QDateTime
from typing import Optional
from ..config.models import AppConfig
from ..comm.mqtt_service import MqttService
from ..file_dist.manager import DownloadManager
from ..player.mpv_controller import MpvController
from ..player.camera_controller import CameraController
from ..camera.embedded_mediapipe_controller import EmbeddedMediaPipeCameraController
from ..ai.ad_attention_scorer import AdAttentionScorer


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg: AppConfig, mqtt: Optional[MqttService], downloader: DownloadManager, player: MpvController, face_detection_enabled: bool = True, detection_mode: str = "face", gesture_controller=None):
        super().__init__()
        self.cfg = cfg
        self.mqtt = mqtt
        self.downloader = downloader
        self.player = player
        self.face_detection_enabled = face_detection_enabled
        self.detection_mode = detection_mode  # "face" 或 "gesture"
        
        # 初始化嵌入式MediaPipe摄像头控制器，并传递MPV播放器实例和已存在的手势控制器
        self.camera_controller = EmbeddedMediaPipeCameraController(detection_mode=self.detection_mode, player=self.player, gesture_controller=gesture_controller)
        
        # 初始化广告关注度评分器（仅在face模式下使用）
        self.ad_scorer = AdAttentionScorer()
        self.current_ad_id = None
        self.current_ad_start_time = None
        
        print(f"MainWindow初始化 - 检测模式: {self.detection_mode}, 人脸检测: {self.face_detection_enabled}")
        
        self.setWindowTitle("广告屏播放器控制台")
        self.resize(1200, 800)
        self.setMinimumSize(1000, 600)
        self._build_ui()
        self._setup_timer()
        
        # 启动摄像头
        self._setup_camera()

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
        panel.setStyleSheet("font-size: 16px;")
        layout = QtWidgets.QVBoxLayout()
        
        # 系统信息
        sys_group = QtWidgets.QGroupBox("系统信息")
        sys_group.setStyleSheet("font-size: 14px;")
        sys_layout = QtWidgets.QFormLayout()
        
        self.time_label = QtWidgets.QLabel("加载中...")
        self.time_label.setStyleSheet("font-size: 14px;")
        self.uptime_label = QtWidgets.QLabel("0 小时 0 分钟")
        self.uptime_label.setStyleSheet("font-size: 14px;")
        self.mqtt_status = QtWidgets.QLabel("未连接")
        self.mqtt_status.setStyleSheet("color: red; font-size: 14px;")
        
        sys_layout.addRow("当前时间:", self.time_label)
        sys_layout.addRow("运行时间:", self.uptime_label)
        sys_layout.addRow("MQTT状态:", self.mqtt_status)
        sys_group.setLayout(sys_layout)
        
        # 播放状态
        play_group = QtWidgets.QGroupBox("播放状态")
        play_group.setStyleSheet("font-size: 14px;")
        play_layout = QtWidgets.QFormLayout()
        
        self.current_file = QtWidgets.QLabel("无")
        self.current_file.setStyleSheet("font-size: 14px;")
        self.play_status = QtWidgets.QLabel("未播放")
        self.play_status.setStyleSheet("color: orange; font-size: 14px;")
        self.queue_count = QtWidgets.QLabel("0")
        self.queue_count.setStyleSheet("font-size: 14px;")
        self.loop_status = QtWidgets.QLabel("关闭")
        self.loop_status.setStyleSheet("color: green; font-size: 14px;")
        
        play_layout.addRow("当前文件:", self.current_file)
        play_layout.addRow("播放状态:", self.play_status)
        play_layout.addRow("播放队列:", self.queue_count)
        play_layout.addRow("循环播放:", self.loop_status)
        play_group.setLayout(play_layout)
        
        # 下载状态
        download_group = QtWidgets.QGroupBox("下载状态")
        download_group.setStyleSheet("font-size: 14px;")
        download_layout = QtWidgets.QFormLayout()
        
        self.download_queue = QtWidgets.QLabel("0")
        self.download_queue.setStyleSheet("font-size: 14px;")
        self.download_progress = QtWidgets.QLabel("0%")
        self.download_progress.setStyleSheet("font-size: 14px;")
        self.last_update = QtWidgets.QLabel("无")
        self.last_update.setStyleSheet("font-size: 14px;")
        
        download_layout.addRow("下载队列:", self.download_queue)
        download_layout.addRow("下载进度:", self.download_progress)
        download_layout.addRow("最后更新:", self.last_update)
        download_group.setLayout(download_layout)
        
        # 摄像头显示区域（简化版本，仅保留显示画面）
        camera_group = QtWidgets.QGroupBox("摄像头监控")
        camera_group.setStyleSheet("font-size: 14px;")
        camera_layout = QtWidgets.QVBoxLayout()
        
        # 摄像头状态显示
        self.camera_status = QtWidgets.QLabel("摄像头自动运行中")
        self.camera_status.setStyleSheet("color: green; font-size: 14px;")
        
        # 摄像头画面显示
        camera_layout.addWidget(self.camera_status)
        
        # 创建摄像头显示区域 - 调整为竖屏尺寸(480x640)
        self.camera_display_area = QtWidgets.QWidget()
        camera_display_layout = QtWidgets.QVBoxLayout()
        self.camera_display_area.setLayout(camera_display_layout)
        self.camera_display_area.setMinimumSize(480, 640)  # 竖屏尺寸
        camera_layout.addWidget(self.camera_display_area)
        
        camera_group.setLayout(camera_layout)
        
        layout.addWidget(sys_group)
        layout.addWidget(play_group)
        layout.addWidget(download_group)
        layout.addWidget(camera_group)
        layout.addStretch(1)
        
        panel.setLayout(layout)
        return panel

    def _create_control_panel(self) -> QtWidgets.QGroupBox:
        """创建控制面板 - 替换为广告关注度显示"""
        panel = QtWidgets.QGroupBox("广告关注度统计")
        panel.setStyleSheet("font-size: 16px;")
        layout = QtWidgets.QVBoxLayout()
        
        # 当前广告关注度
        current_ad_group = QtWidgets.QGroupBox("当前广告")
        current_ad_group.setStyleSheet("font-size: 14px;")
        current_layout = QtWidgets.QFormLayout()
        
        self.current_ad_label = QtWidgets.QLabel("无广告播放")
        self.current_ad_label.setStyleSheet("font-size: 14px;")
        self.current_ad_score = QtWidgets.QLabel("0")
        self.current_ad_score.setStyleSheet("font-size: 28px; color: #2196F3;")
        
        current_layout.addRow("广告名称:", self.current_ad_label)
        current_layout.addRow("关注度得分:", self.current_ad_score)
        current_ad_group.setLayout(current_layout)
        
        # 历史广告排名
        history_group = QtWidgets.QGroupBox("广告排名")
        history_group.setStyleSheet("font-size: 14px;")
        history_layout = QtWidgets.QVBoxLayout()
        
        self.ad_ranking_widget = QtWidgets.QListWidget()
        self.ad_ranking_widget.setMaximumHeight(300)
        self.ad_ranking_widget.setStyleSheet("font-size: 14px;")
        history_layout.addWidget(self.ad_ranking_widget)
        
        history_group.setLayout(history_layout)
        
        # 详细统计信息
        stats_group = QtWidgets.QGroupBox("详细统计")
        stats_group.setStyleSheet("font-size: 28px;")
        stats_layout = QtWidgets.QFormLayout()
        
        self.attention_ratio_label = QtWidgets.QLabel("0%")
        self.attention_ratio_label.setStyleSheet("font-size: 28px;")
        self.absolute_attention_label = QtWidgets.QLabel("0")
        self.absolute_attention_label.setStyleSheet("font-size: 28px;")
        self.continuity_label = QtWidgets.QLabel("0%")
        self.continuity_label.setStyleSheet("font-size: 28px;")
        self.consistency_label = QtWidgets.QLabel("0%")
        self.consistency_label.setStyleSheet("font-size: 28px;")
        self.coverage_label = QtWidgets.QLabel("0%")
        self.coverage_label.setStyleSheet("font-size: 28px;")
        
        # 新增两个指标
        self.current_face_count_label = QtWidgets.QLabel("0")
        self.current_face_count_label.setStyleSheet("font-size: 28px;")
        self.current_gazing_count_label = QtWidgets.QLabel("0")
        self.current_gazing_count_label.setStyleSheet("font-size: 28px;")
        
        stats_layout.addRow("注意力比率:", self.attention_ratio_label)
        stats_layout.addRow("绝对关注规模:", self.absolute_attention_label)
        stats_layout.addRow("持续关注深度:", self.continuity_label)
        stats_layout.addRow("关注稳定性:", self.consistency_label)
        stats_layout.addRow("关注覆盖率:", self.coverage_label)
        stats_layout.addRow("当前人脸数:", self.current_face_count_label)
        stats_layout.addRow("关注数:", self.current_gazing_count_label)
        
        stats_group.setLayout(stats_layout)
        
        layout.addWidget(current_ad_group)
        layout.addWidget(history_group)
        layout.addWidget(stats_group)
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
        
        # MQTT 关注度快照定时器（每5秒推送一次）
        self._mqtt_snapshot_timer = QTimer(self)
        self._mqtt_snapshot_timer.setInterval(5000)
        self._mqtt_snapshot_timer.timeout.connect(self._push_attention_snapshot)
        self._mqtt_snapshot_timer.start()

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
            if mqtt_connected:
                self.mqtt_status.setText("已连接")
                self.mqtt_status.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.mqtt_status.setText("连接中...")
                self.mqtt_status.setStyleSheet("color: orange; font-weight: bold;")
        else:
            if self.cfg.mqtt.enabled:
                self.mqtt_status.setText("正在启动...")
                self.mqtt_status.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.mqtt_status.setText("未启用")
                self.mqtt_status.setStyleSheet("color: gray; font-weight: bold;")
        
        # 更新播放状态
        if self.player.current_process:
            self.play_status.setText("播放中")
            self.play_status.setStyleSheet("color: green; font-weight: bold;")
            
            # 更新当前播放文件
            current_file = self._get_current_playing_file()
            if current_file:
                self.current_file.setText(current_file)
            else:
                self.current_file.setText("播放中...")
        else:
            self.play_status.setText("未播放")
            self.play_status.setStyleSheet("color: orange; font-weight: bold;")
            self.current_file.setText("无")
        
        # 更新播放队列
        queue_len = len(self.player.queue) if hasattr(self.player, 'queue') else 0
        self.queue_count.setText(str(queue_len))
        
        # 更新循环播放状态
        if hasattr(self.player, 'loop'):
            loop_text = "开启" if self.player.loop else "关闭"
            loop_color = "green" if self.player.loop else "red"
            self.loop_status.setText(loop_text)
            self.loop_status.setStyleSheet(f"color: {loop_color}; font-weight: bold;")
        else:
            self.loop_status.setText("未知")
            self.loop_status.setStyleSheet("color: gray; font-weight: bold;")
        
        # 更新下载状态
        download_tasks = len(self.downloader.tasks) if hasattr(self.downloader, 'tasks') else 0
        self.download_queue.setText(str(download_tasks))
        
        # 更新播放列表
        self._update_playlist()
        
        # 更新广告关注度统计
        self._update_ad_attention_stats()

    def _update_playlist(self) -> None:
        """更新播放列表显示（已废弃，保留方法避免错误）"""
        # 播放列表功能已被广告关注度统计替代
        # 这个方法现在只做空操作以避免错误
        pass
    
    def _update_ad_attention_stats(self) -> None:
        """更新广告关注度统计 - face模式显示人脸关注度，gesture模式显示手势识别结果"""
        try:
            # 只在face模式下运行广告关注度统计
            if self.detection_mode != "face":
                # 在gesture模式下，显示手势识别结果
                if self.detection_mode == "gesture":
                    self.current_ad_label.setText("手势识别模式")
                    self.current_ad_score.setText("功能已禁用")
                    self.attention_ratio_label.setText("功能已禁用")
                    self.absolute_attention_label.setText("功能已禁用")
                    self.continuity_label.setText("功能已禁用")
                    self.consistency_label.setText("功能已禁用")
                    self.coverage_label.setText("功能已禁用")
                    self.current_face_count_label.setText("功能已禁用")
                    
                    # 获取手势识别结果
                    gesture_result = self._get_gesture_recognition_result()
                    self.current_gazing_count_label.setText(gesture_result)
                    
                    # 清空广告排名
                    self.ad_ranking_widget.clear()
                return
            
            print(f"=== 广告关注度统计更新开始 ===")
            
            # 获取当前帧的检测数据
            current_face_count = 0
            current_gazing_faces = 0
            
            # 方法：直接通过控制器获取检测器数据
            if hasattr(self.camera_controller, 'detector') and self.camera_controller.detector:
                detector = self.camera_controller.detector
                
                # 关键修复：添加线程安全的数据获取机制
                # 确保获取的是最新的检测结果
                current_frame_count_before = detector.frame_count
                detection_results = detector.detection_results
                current_frame_count_after = detector.frame_count
                
                # 检查是否在读取过程中帧计数发生了变化
                if current_frame_count_before != current_frame_count_after:
                    print("警告：检测器正在处理新帧，重新获取数据...")
                    detection_results = detector.detection_results
                
                current_face_count = detection_results.get('face_count', 0)
                current_gazing_faces = detection_results.get('gazing_faces', 0)
                
                # 精简调试信息：只显示关键状态
                print(f"检测器状态: frame_count={detector.frame_count}, face_count={current_face_count}, gazing_faces={current_gazing_faces}")
                
                # 显示IOU跟踪统计信息
                tracking_stats = detection_results.get('tracking_stats', {})
                if tracking_stats:
                    print(f"[IOU跟踪] 创建跟踪={tracking_stats.get('total_tracks_created', 0)}, "
                          f"匹配跟踪={tracking_stats.get('total_tracks_matched', 0)}, "
                          f"过滤重复={tracking_stats.get('duplicate_detections_filtered', 0)}")
            else:
                print("警告：检测器不存在或未初始化，无法获取检测数据")
                return
            
            # 初始化累计统计变量（如果不存在）
            if not hasattr(self, 'cumulative_stats'):
                self.cumulative_stats = {
                    'total_face_count': 0,
                    'total_gazing_faces': 0,
                    'total_frames': 0,
                    'frames_with_gaze': 0,
                    'gazing_values': [],  # 存储每帧的注视人数用于方差计算
                    'gazing_variance': 0.0,
                    'last_update_time': time.time()
                }
            
            # 累加统计（符合你的方案）
            self.cumulative_stats['total_face_count'] += current_face_count
            self.cumulative_stats['total_gazing_faces'] += current_gazing_faces
            self.cumulative_stats['total_frames'] += 1
            if current_gazing_faces > 0:
                self.cumulative_stats['frames_with_gaze'] += 1
            
            # 记录每帧的注视人数用于方差计算
            self.cumulative_stats['gazing_values'].append(current_gazing_faces)
            
            # 计算注视人数的方差（用于稳定性指标）
            if len(self.cumulative_stats['gazing_values']) > 1:
                import numpy as np
                self.cumulative_stats['gazing_variance'] = np.var(self.cumulative_stats['gazing_values'])
            else:
                self.cumulative_stats['gazing_variance'] = 0.0
            
            print(f"累计统计: 总人脸数={self.cumulative_stats['total_face_count']}, "
                  f"总注视数={self.cumulative_stats['total_gazing_faces']}, "
                  f"总帧数={self.cumulative_stats['total_frames']}")
            
            # 如果有广告正在播放，处理广告跟踪
            if self.player.current_process:
                current_file_info = self.get_current_file_info()
                current_ad_id = self._get_current_ad_id()
                
                print(f"播放信息: 播放中={current_file_info['playing']}, 文件={current_file_info['current_file']}")
                print(f"当前广告ID: {current_ad_id}, 上一个广告ID: {self.current_ad_id}")
                
                if current_file_info['playing']:
                    # 增强广告切换检测
                    should_start_new_ad = self._should_start_new_ad_tracking(current_ad_id)
                    
                    if should_start_new_ad:
                        if self.current_ad_id:
                            # 结束上一个广告的跟踪
                            result = self.ad_scorer.end_ad_tracking()
                            print(f"广告 {self.current_ad_id} 跟踪结束，得分: {result.get('total_score', 0)}")
                            
                            # 上报广告完成消息到MQTT
                            if self.mqtt and result.get('total_score', 0) > 0:
                                self.mqtt.publish_ad_completed(
                                    ad_id=self.current_ad_id,
                                    final_score=result.get('total_score', 0),
                                    score_breakdown=result.get('breakdown', {}),
                                    play_statistics=result.get('statistics', {})
                                )
                            
                            # 广告结束后显示5维度计算详情
                            self._print_five_dimension_calculation(result)
                        
                        # 开始新广告跟踪（假设广告时长30秒）
                        self.current_ad_id = current_ad_id
                        self.current_ad_start_time = time.time()
                        self.ad_scorer.start_ad_tracking(current_ad_id, 30.0)  # 默认30秒广告时长
                        print(f"开始跟踪新广告: {current_ad_id}")
                        
                        # 重置累计统计（新广告开始）
                        self.cumulative_stats = {
                            'total_face_count': 0,
                            'total_gazing_faces': 0,
                            'total_frames': 0,
                            'frames_with_gaze': 0,
                            'gazing_values': [],  # 存储每帧的注视人数用于方差计算
                            'gazing_variance': 0.0,
                            'last_update_time': time.time()
                        }
                    
                    # 添加当前帧数据到评分器（基于累加统计）
                    self.ad_scorer.add_frame_data(current_face_count, current_gazing_faces)
                    
                    # 更新当前广告显示
                    self.current_ad_label.setText(current_ad_id)
                    
                    # 获取最新得分（如果广告已结束）
                    latest_score = self.ad_scorer.get_ad_score(current_ad_id)
                    if latest_score:
                        score = latest_score['total_score']
                        self.current_ad_score.setText(f"{score}/100")
                        
                        # 更新详细统计
                        breakdown = latest_score['breakdown']
                        self.attention_ratio_label.setText(f"{breakdown['attention_score']:.1f}")
                        self.absolute_attention_label.setText(f"{breakdown['absolute_score']:.1f}")
                        self.continuity_label.setText(f"{breakdown['duration_score']:.1f}")
                        self.consistency_label.setText(f"{breakdown['consistency_score']:.1f}")
                        self.coverage_label.setText(f"{breakdown['efficiency_score']:.1f}")
                        
                        # 更新新指标：当前人脸数和关注数（显示当前帧的实际数值）
                        # 使用当前帧的实时数据而不是平均值
                        self.current_face_count_label.setText(f"{current_face_count}")
                        self.current_gazing_count_label.setText(f"{current_gazing_faces}")
                        
                        # 显示5个维度的计算参数和结果
                        self._print_five_dimension_calculation(latest_score)
                    else:
                        # 广告仍在播放中，显示实时统计信息（基于累加数据）
                        self.current_ad_score.setText("计算中...")
                        
                        # 计算实时统计（基于累计数据）
                        if self.cumulative_stats['total_frames'] > 0:
                            attention_ratio = self.cumulative_stats['total_gazing_faces'] / self.cumulative_stats['total_face_count'] if self.cumulative_stats['total_face_count'] > 0 else 0.0
                            efficiency_ratio = self.cumulative_stats['frames_with_gaze'] / self.cumulative_stats['total_frames']
                            
                            # 计算实时持续关注深度（基于连续注视帧数）
                            continuity_ratio = self.cumulative_stats['frames_with_gaze'] / self.cumulative_stats['total_frames'] if self.cumulative_stats['total_frames'] > 0 else 0.0
                            
                            # 计算实时关注稳定性（基于注视人数的稳定性）
                            if self.cumulative_stats['total_frames'] > 1:
                                # 使用注视人数的变化率作为稳定性指标
                                consistency_ratio = 1.0 - (self.cumulative_stats['gazing_variance'] / max(1, self.cumulative_stats['total_gazing_faces'])) if self.cumulative_stats['total_gazing_faces'] > 0 else 0.0
                            else:
                                consistency_ratio = 0.0
                            
                            self.attention_ratio_label.setText(f"{attention_ratio*100:.1f}%")
                            self.absolute_attention_label.setText(f"{self.cumulative_stats['total_gazing_faces']}")
                            self.continuity_label.setText(f"{continuity_ratio*100:.1f}% (估算)")
                            self.consistency_label.setText(f"{consistency_ratio*100:.1f}% (估算)")
                            self.coverage_label.setText(f"{efficiency_ratio*100:.1f}% (估算)")
                            
                            # 更新新指标：当前人脸数和关注数（显示当前帧的实际数值）
                            # 使用当前帧的实时数据而不是平均值
                            self.current_face_count_label.setText(f"{current_face_count}")
                            self.current_gazing_count_label.setText(f"{current_gazing_faces}")
                        
                        print(f"广告进行中: {current_ad_id}, 等待结束计算...")
                else:
                    # 没有广告播放
                    self.current_ad_label.setText("无广告播放")
                    self.current_ad_score.setText("0")
            else:
                # 没有广告播放
                self.current_ad_label.setText("无广告播放")
                self.current_ad_score.setText("0")
            
            # 更新广告排名
            self._update_ad_ranking()
            
            print(f"=== 广告关注度统计更新结束 ===\n")
            
        except Exception as e:
            print(f"更新广告关注度统计时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _should_start_new_ad_tracking(self, current_ad_id: str) -> bool:
        """判断是否应该开始新的广告跟踪"""
        try:
            # 情况1：当前没有广告在跟踪
            if not self.current_ad_id:
                print("没有当前广告跟踪，开始新跟踪")
                return True
            
            # 情况2：广告ID发生变化
            if self.current_ad_id != current_ad_id:
                print(f"广告ID发生变化: {self.current_ad_id} -> {current_ad_id}")
                return True
            
            # 情况3：当前广告已播放超过30秒（可能已经切换到新广告但ID相同）
            if hasattr(self, 'current_ad_start_time'):
                current_time = time.time()
                ad_duration = current_time - self.current_ad_start_time
                if ad_duration > 35:  # 比默认30秒长5秒作为缓冲
                    print(f"当前广告已播放{ad_duration:.1f}秒，可能已切换到新广告")
                    return True
            
            # 情况4：检查播放器索引是否发生变化
            if hasattr(self.player, 'current_file_index'):
                current_index = self.player.current_file_index
                # 这里可以添加索引变化的检测逻辑
                
            print("继续跟踪当前广告")
            return False
            
        except Exception as e:
            print(f"判断是否开始新广告跟踪时出错: {e}")
            return True
    
    def _display_real_time_stats(self, face_count: int, gazing_faces: int):
        """显示实时统计数据（广告播放期间）"""
        try:
            # 计算实时关注比率
            attention_ratio = gazing_faces / face_count if face_count > 0 else 0.0
            
            # 显示实时统计数据
            self.attention_ratio_label.setText(f"{attention_ratio*100:.1f}%")
            self.absolute_attention_label.setText(str(gazing_faces))
            
            # 其他维度显示实时估算值（带估算标签）
            efficiency_ratio = gazing_faces / max(1, face_count) if face_count > 0 else 0.0
            self.continuity_label.setText(f"{efficiency_ratio*100:.1f}% (估算)")
            self.consistency_label.setText("计算中...")
            self.coverage_label.setText(f"{efficiency_ratio*100:.1f}% (估算)")
            
        except Exception as e:
            print(f"显示实时统计数据时出错: {e}")
    
    def _update_ad_ranking(self) -> None:
        """更新广告排名显示"""
        try:
            self.ad_ranking_widget.clear()
            
            # 获取排名
            ranking = self.ad_scorer.get_score_ranking()
            
            for i, ad_info in enumerate(ranking):
                ad_id = ad_info['ad_id']
                score = ad_info['score']
                play_count = ad_info.get('play_count', 1)
                
                # 设置显示颜色
                if score >= 80:
                    color = "#4CAF50"  # 绿色
                elif score >= 60:
                    color = "#2196F3"  # 蓝色
                elif score >= 40:
                    color = "#FF9800"  # 橙色
                else:
                    color = "#F44336"  # 红色
                
                # 显示播放次数信息
                if play_count > 1:
                    display_text = f"{i+1}. {ad_id} - {score:.1f}/100 (播放{play_count}次)"
                else:
                    display_text = f"{i+1}. {ad_id} - {score:.1f}/100 (首次播放)"
                
                item = QtWidgets.QListWidgetItem(display_text)
                item.setForeground(QtGui.QColor(color))
                self.ad_ranking_widget.addItem(item)
                
        except Exception as e:
            print(f"更新广告排名时出错: {e}")
    
    def _print_five_dimension_calculation(self, score_result: dict) -> None:
        """显示5个维度的计算参数和结果"""
        try:
            stats = score_result.get('statistics', {})
            breakdown = score_result.get('breakdown', {})
            
            print("=== 广告关注度5维度计算详情 ===")
            print(f"广告ID: {stats.get('ad_id', 'N/A')}")
            print(f"广告时长: {stats.get('ad_duration', 'N/A')}秒")
            print(f"总帧数: {stats.get('total_frames', 'N/A')}")
            print(f"平均人脸数: {stats.get('avg_face_count', 'N/A')}")
            print(f"平均注视人数: {stats.get('avg_gazing_faces', 'N/A')}")
            print()
            
            # 1. 注意力比率（25分）- 观看质量
            attention_ratio = stats.get('attention_ratio', 0)
            attention_score = breakdown.get('attention_score', 0)
            print(f"1. 注意力比率: {attention_ratio:.3f} * 25 = {attention_score:.1f}分")
            print(f"   公式: 注视人数 ÷ 总人数 = 观看质量")
            
            # 2. 绝对关注规模（20分）- 观看规模  
            avg_face = stats.get('avg_face_count', 0)
            avg_gaze = stats.get('avg_gazing_faces', 0)
            absolute_score = breakdown.get('absolute_score', 0)
            print(f"2. 绝对关注规模: log2(1+{avg_gaze:.1f})/log2(1+{avg_face:.1f}) * 20 = {absolute_score:.1f}分")
            print(f"   公式: 总注视人数 = 观看规模")
            
            # 3. 持续关注深度（25分）- 观看深度
            continuity_ratio = stats.get('continuity_ratio', 0)
            duration_score = breakdown.get('duration_score', 0)
            print(f"3. 持续关注深度: {continuity_ratio:.3f} * 25 = {duration_score:.1f}分")
            print(f"   公式: 总注视时长 ÷ 总注视人数 = 平均观看时长")
            
            # 4. 关注稳定性（15分）- 稳定性
            consistency = stats.get('consistency', 0)
            consistency_score = breakdown.get('consistency_score', 0)
            print(f"4. 关注稳定性: {consistency:.3f} * 15 = {consistency_score:.1f}分")
            print(f"   公式: 稳定注视时长 ÷ 总注视时长 = 观看稳定性")
            
            # 5. 关注覆盖率（15分）- 覆盖率
            efficiency_ratio = stats.get('efficiency_ratio', 0)
            efficiency_score = breakdown.get('efficiency_score', 0)
            print(f"5. 关注覆盖率: {efficiency_ratio:.3f} * 15 = {efficiency_score:.1f}分")
            print(f"   公式: 实际观看人数 ÷ 潜在观看人数 = 覆盖范围")
            
            # 最终总分
            total_score = score_result.get('total_score', 0)
            print(f"最终总分: {total_score:.1f}/100")
            print("==================================")
            
        except Exception as e:
            print(f"显示维度计算详情时出错: {e}")


    
    def _push_attention_snapshot(self) -> None:
        """定时推送关注度快照到MQTT（每5秒调用一次）"""
        if not self.mqtt:
            return
        
        try:
            # 获取当前检测数据
            face_count = 0
            gazing_faces = 0
            fps = 0.0
            ad_id = "无广告"
            ad_position_sec = 0.0
            
            if hasattr(self.camera_controller, 'detector') and self.camera_controller.detector:
                detection_results = self.camera_controller.detector.detection_results
                face_count = detection_results.get('face_count', 0)
                gazing_faces = detection_results.get('gazing_faces', 0)
                fps = detection_results.get('fps', 0.0)
                window_face_count = detection_results.get('window_face_count', 0)
                window_gazing_faces = detection_results.get('window_gazing_faces', 0)
            
            # 获取当前广告ID和播放进度
            if self.player and self.player.current_process:
                ad_id = self._get_current_ad_id()
                if ad_id == "未知广告":
                    ad_id = "无广告"
                # 获取播放进度（轻量方法，只查 time-pos）
                if hasattr(self.player, 'get_playback_time'):
                    ad_position_sec = self.player.get_playback_time()
            
            # 更新 MQTT 服务的当前检测数据（使用5秒窗口累计值）
            self.mqtt.update_detection_data(
                face_count=window_face_count,
                gazing_faces=window_gazing_faces,
                ad_id=ad_id,
                ad_position_sec=ad_position_sec,
                fps=fps
            )
            
            # 手动触发一次快照上报
            self.mqtt.publish_attention_snapshot()
            
        except Exception as e:
            print(f"推送关注度快照失败: {e}")

    def _play_selected_file(self, item) -> None:
        """播放选中的文件"""
        try:
            # 获取选中项的索引
            index = self.playlist_widget.row(item)
            if 0 <= index < len(self.player.queue):
                selected_file = self.player.queue[index]
                print(f"播放选中的文件: {selected_file.name}")
                
                # 设置当前文件索引并播放
                self.player.current_file_index = index
                self.player.play(selected_file)
            else:
                print("无效的播放列表索引")
        except Exception as e:
            print(f"播放选中文件时出错: {e}")
    
    def _get_current_playing_file(self) -> str:
        """获取当前播放的文件名"""
        try:
            # 方式0：优先使用IPC查询（最新最准确）
            if hasattr(self.player, 'current_playing_file') and self.player.current_playing_file:
                current_file = self.player.current_playing_file
                # 提取文件名（如果包含路径）
                if '/' in current_file or '\\' in current_file:
                    import os
                    current_file = os.path.basename(current_file)
                print(f"通过IPC查询获取到文件: {current_file}")
                return current_file
            
            # 方式1：通过播放器内部方法获取
            if hasattr(self.player, '_get_current_file'):
                current_file = self.player._get_current_file()
                if current_file:
                    print(f"通过_get_current_file获取到文件: {current_file.name}")
                    return current_file.name
            
            # 方式2：通过索引获取
            if hasattr(self.player, 'queue') and hasattr(self.player, 'current_file_index'):
                if 0 <= self.player.current_file_index < len(self.player.queue):
                    current_file = self.player.queue[self.player.current_file_index]
                    print(f"通过索引获取到文件: {current_file.name} (索引={self.player.current_file_index})")
                    return current_file.name
            
            # 方式3：检查播放列表文件
            if hasattr(self.player, 'playlist_file') and self.player.playlist_file:
                print(f"尝试读取播放列表文件: {self.player.playlist_file}")
                try:
                    with open(self.player.playlist_file, 'r', encoding='utf-8') as f:
                        playlist = f.readlines()
                    if playlist and hasattr(self.player, 'current_file_index'):
                        if 0 <= self.player.current_file_index < len(playlist):
                            current_file_path = playlist[self.player.current_file_index].strip()
                            current_file = Path(current_file_path)
                            print(f"通过播放列表文件获取到文件: {current_file.name}")
                            return current_file.name
                except Exception as e:
                    print(f"读取播放列表文件失败: {e}")
            
            # 方式4：如果有播放进程但无法确定文件，显示通用信息
            if self.player.current_process:
                print("检测到播放进程运行中，但无法确定具体文件")
                return "播放中..."
                    
        except Exception as e:
            print(f"获取当前播放文件时出错: {e}")
            import traceback
            traceback.print_exc()
            
        return ""
    
    def _get_current_ad_id(self) -> str:
        """获取当前广告ID（优化版本）"""
        try:
            # 获取当前播放的文件名
            current_file = self._get_current_playing_file()
            
            # 如果文件名为空，说明没有广告正在播放
            if not current_file or current_file == "播放中...":
                print("无法确定当前广告ID，使用默认值")
                return "未知广告"
            
            # 返回文件名作为广告ID
            print(f"当前广告ID: {current_file}")
            return current_file
            
        except Exception as e:
            print(f"获取当前广告ID时出错: {e}")
            return "未知广告"
    
    def _get_gesture_recognition_result(self) -> str:
        """获取手势识别结果"""
        try:
            # 检查摄像头控制器是否存在且有手势检测器
            if not hasattr(self.camera_controller, 'gesture_controller'):
                return "未初始化"
            
            gesture_controller = self.camera_controller.gesture_controller
            if not gesture_controller or not gesture_controller.running:
                return "未运行"
            
            # 直接通过手势控制器获取当前手势
            if hasattr(gesture_controller, 'last_stable_gesture'):
                current_gesture = gesture_controller.last_stable_gesture
                if current_gesture and current_gesture != "unknown":
                    # 获取手势的显示名称
                    if hasattr(gesture_controller, '_get_gesture_display_name'):
                        gesture_name = gesture_controller._get_gesture_display_name(current_gesture)
                        return f"手势: {gesture_name}"
                    else:
                        return f"手势: {current_gesture}"
                else:
                    return "未检测到手势"
            else:
                return "检测中..."
                
        except Exception as e:
            print(f"获取手势识别结果时出错: {e}")
            return "错误"
    
    def get_current_file_info(self):
        """获取当前播放文件信息（优化版本）"""
        info = {
            "current_file": "",
            "current_index": 0,
            "total_files": 0,
            "playing": False
        }
        
        try:
            # 播放状态
            info["playing"] = bool(self.player.current_process)
            
            # 使用新的文件获取方法
            current_file_name = self._get_current_playing_file()
            info["current_file"] = current_file_name
            
            # 文件队列信息
            if hasattr(self.player, 'queue'):
                info["total_files"] = len(self.player.queue)
                
            # 尝试获取当前索引
            if hasattr(self.player, 'current_file_index'):
                info["current_index"] = self.player.current_file_index + 1
                    
        except Exception as e:
            print(f"获取播放文件信息时出错: {e}")
            
        return info

    def _setup_camera(self):
        """初始化摄像头设置"""
        try:
            print("=== 摄像头设置开始 ===")
            print(f"摄像头控制器对象: {type(self.camera_controller)}")
            print(f"摄像头控制器ID: {id(self.camera_controller)}")
            
            # 初始化MediaPipe摄像头控制器（根据检测模式决定是否启用人脸检测）
            print("开始初始化摄像头控制器...")
            print(f"调用initialize方法前，检查控制器状态...")
            print(f"人脸检测模式: {'启用' if self.face_detection_enabled else '禁用'}")
            
            success = self.camera_controller.initialize(
                camera_index=None,  # 设置为None，让控制器自动选择可用摄像头
                resolution=(480, 640), 
                fps=15,
                enable_face_detection=self.face_detection_enabled  # 根据检测模式决定是否启用人脸检测
            )
            
            print(f"摄像头控制器initialize方法返回结果: {success}")
            
            if success:
                print("MediaPipe摄像头控制器初始化成功")
                
                # 检查摄像头线程状态
                if hasattr(self.camera_controller, 'camera_thread'):
                    print(f"摄像头线程存在: {self.camera_controller.camera_thread}")
                    if self.camera_controller.camera_thread:
                        print(f"摄像头线程运行状态: {self.camera_controller.camera_thread.isRunning()}")
                
                # 添加摄像头控件到界面
                print("开始更新摄像头显示...")
                self._update_camera_display()
                
                # 检查是否已经通过初始化自动启动了摄像头
                if hasattr(self.camera_controller, 'camera_thread') and self.camera_controller.camera_thread:
                    if self.camera_controller.camera_thread.isRunning():
                        print("摄像头已通过初始化自动启动，无需再次启动")
                        if self.detection_mode == "face":
                            self.camera_status.setText("人脸检测模式 - 摄像头运行中")
                        else:
                            self.camera_status.setText("手势识别模式 - 摄像头运行中")
                        self.camera_status.setStyleSheet("color: green; font-weight: bold;")
                        print("=== 摄像头设置结束 ===")
                        return
                
                # 自动启动摄像头（带重试机制）
                print("开始自动启动摄像头（带重试机制）...")
                success = self._start_camera_with_retry(max_retries=3, delay=2.0)
                if success:
                    if self.detection_mode == "face":
                        self.camera_status.setText("人脸检测模式 - 摄像头运行中")
                    else:
                        self.camera_status.setText("手势识别模式 - 摄像头运行中")
                    self.camera_status.setStyleSheet("color: green; font-weight: bold;")
                    print("摄像头自动启动成功")
                else:
                    print("摄像头自动启动失败")
                    self.camera_status.setText("摄像头启动失败")
                    self.camera_status.setStyleSheet("color: red; font-weight: bold;")
            else:
                print("摄像头控制器初始化失败")
                self.camera_status.setText("摄像头初始化失败")
                self.camera_status.setStyleSheet("color: red; font-weight: bold;")
                
            print("=== 摄像头设置结束 ===")
                
        except Exception as e:
            print(f"摄像头设置错误: {e}")
            import traceback
            traceback.print_exc()
            self.camera_status.setText(f"摄像头错误: {e}")
            self.camera_status.setStyleSheet("color: red; font-weight: bold;")
    
    def _start_camera_with_retry(self, max_retries: int = 3, delay: float = 2.0) -> bool:
        """带重试的摄像头启动，专门处理设备重启后第一次启动问题"""
        for attempt in range(max_retries):
            print(f"摄像头启动尝试 {attempt + 1}/{max_retries}...")
            
            try:
                success = self.camera_controller.start_camera()
                if success:
                    print(f"摄像头启动成功，尝试 {attempt + 1} 次")
                    return True
                else:
                    if attempt < max_retries - 1:
                        print(f"摄像头启动失败，等待 {delay} 秒后重试...")
                        import time
                        time.sleep(delay)
                    else:
                        print("摄像头启动多次重试后仍失败")
                        return False
            except Exception as e:
                print(f"摄像头启动异常: {e}")
                if attempt < max_retries - 1:
                    print(f"等待 {delay} 秒后重试...")
                    import time
                    time.sleep(delay)
                else:
                    print("摄像头启动多次重试后仍异常")
                    return False
        
        return False
    

    
    def _update_camera_display(self):
        """更新摄像头显示控件"""
        try:
            # 清空现有显示区域
            layout = self.camera_display_area.layout()
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # 添加摄像头控件
            camera_widget = self.camera_controller.get_widget()
            if camera_widget:
                layout.addWidget(camera_widget)
                print("摄像头显示控件已添加到界面")
            else:
                # 如果没有摄像头控件，显示提示信息
                placeholder = QtWidgets.QLabel("摄像头控件未初始化")
                placeholder.setAlignment(QtCore.Qt.AlignCenter)
                placeholder.setStyleSheet("color: gray; font-size: 14px;")
                layout.addWidget(placeholder)
                
        except Exception as e:
            print(f"更新摄像头显示错误: {e}")
    

    
    def _start_camera(self):
        """启动摄像头"""
        try:
            success = self.camera_controller.start_camera()
            if success:
                self.camera_status.setText("摄像头运行中")
                self.camera_status.setStyleSheet("color: green; font-weight: bold;")
                self.camera_start_btn.setEnabled(False)
                self.camera_stop_btn.setEnabled(True)
                self.camera_capture_btn.setEnabled(True)
                self.camera_rotate_btn.setEnabled(True)
                self.ai_analysis_btn.setEnabled(True)
                
                # 如果AI功能已启用，更新按钮状态
                if hasattr(self.camera_controller, 'ai_enabled') and self.camera_controller.ai_enabled:
                    self.ai_analysis_btn.setText("AI分析: 开启")
                    self.ai_analysis_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
                else:
                    self.ai_analysis_btn.setText("AI分析: 关闭")
                    self.ai_analysis_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; }")
                
                print("摄像头启动成功")
            else:
                self.camera_status.setText("摄像头启动失败")
                self.camera_status.setStyleSheet("color: red; font-weight: bold;")
                print("摄像头启动失败")
        except Exception as e:
            print(f"启动摄像头错误: {e}")
    
    def _stop_camera(self):
        """停止摄像头"""
        try:
            self.camera_controller.stop_camera()
            self.camera_status.setText("摄像头已停止")
            self.camera_status.setStyleSheet("color: gray; font-weight: bold;")
            self.camera_start_btn.setEnabled(True)
            self.camera_stop_btn.setEnabled(False)
            self.camera_capture_btn.setEnabled(False)
            self.camera_rotate_btn.setEnabled(False)
            self.ai_analysis_btn.setEnabled(False)
            print("摄像头已停止")
        except Exception as e:
            print(f"停止摄像头错误: {e}")
    
    def _rotate_camera(self):
        """旋转摄像头画面"""
        try:
            # 每次点击向右旋转90度
            self.camera_controller.rotate_camera(90)
            
            # 更新按钮文本显示当前角度
            rotation_angle = 0
            if hasattr(self.camera_controller.camera_widget, 'get_rotation_angle'):
                rotation_angle = self.camera_controller.camera_widget.get_rotation_angle()
            
            self.camera_rotate_btn.setText(f"旋转{rotation_angle}°")
            self.camera_status.setText(f"画面已旋转至{rotation_angle}度")
            
            # 3秒后恢复状态显示
            QtCore.QTimer.singleShot(3000, lambda: self.camera_status.setText("摄像头运行中"))
            
        except Exception as e:
            print(f"旋转摄像头错误: {e}")
    
    def _capture_image(self):
        """拍照保存"""
        try:
            import os
            from datetime import datetime
            
            # 创建captures目录
            captures_dir = "data/captures"
            os.makedirs(captures_dir, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"capture_{timestamp}.jpg"
            file_path = os.path.join(captures_dir, filename)
            
            # 拍照保存
            success = self.camera_controller.capture_image(file_path)
            
            if success:
                self.camera_status.setText(f"照片已保存: {filename}")
                print(f"照片已保存: {file_path}")
                
                # 3秒后恢复状态显示
                QtCore.QTimer.singleShot(3000, lambda: self.camera_status.setText("摄像头运行中"))
            else:
                self.camera_status.setText("拍照失败")
                print("拍照失败")
                
        except Exception as e:
            print(f"拍照错误: {e}")
    
    def _on_camera_frame(self, frame):
        """摄像头帧回调函数（用于WebSocket发送等）"""
        # 这里可以添加WebSocket发送逻辑
        # 例如：self._send_frame_via_websocket(frame)
        pass
    
    def _toggle_ai_analysis(self):
        """切换AI分析功能"""
        try:
            if not hasattr(self.camera_controller, 'ai_enabled'):
                print("当前摄像头控制器不支持AI分析功能")
                return
            
            if self.camera_controller.ai_enabled:
                # 关闭AI分析
                self.camera_controller.disable_ai_analysis()
                self.ai_analysis_btn.setText("AI分析: 关闭")
                self.ai_analysis_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; }")
                self.camera_status.setText("AI分析已关闭")
                
                # 更新分析结果状态
                self.ai_status_label.setText("AI分析已关闭")
                self.ai_status_label.setStyleSheet("color: gray; font-weight: bold;")
                self.ai_results_text.setPlainText("AI分析功能已关闭")
                
                print("AI分析功能已关闭")
            else:
                # 启用AI分析
                self.camera_controller.enable_ai_analysis()
                self.ai_analysis_btn.setText("AI分析: 开启")
                self.ai_analysis_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
                self.camera_status.setText("AI分析已开启")
                
                # 更新分析结果状态
                self.ai_status_label.setText("AI分析运行中...")
                self.ai_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.ai_results_text.setPlainText("等待AI分析结果...")
                
                print("AI分析功能已开启")
            
            # 3秒后恢复状态显示
            QtCore.QTimer.singleShot(3000, lambda: self.camera_status.setText("摄像头运行中"))
            
        except Exception as e:
            print(f"切换AI分析功能错误: {e}")
            self.camera_status.setText(f"AI分析错误: {e}")
    
    def _on_analysis_result(self, analysis_result):
        """AI分析结果回调函数"""
        try:
            # 更新分析结果状态
            self.ai_status_label.setText("AI分析运行中")
            self.ai_status_label.setStyleSheet("color: green; font-weight: bold;")
            
            # 提取分析结果
            detection_result = analysis_result.get('detection_result', None)
            statistics = analysis_result.get('statistics', {})
            performance = analysis_result.get('performance', {})
            
            # 构建结果文本
            result_text = []
            result_text.append("=== AI分析结果 ===")
            
            if detection_result:
                result_text.append(f"👥 检测人数: {detection_result.person_count}")
                result_text.append(f"📏 检测框数: {len(detection_result.detections)}")
                if detection_result.detections:
                    confidences = [f"{d[4]:.2f}" for d in detection_result.detections]
                    result_text.append(f"🎯 置信度: {', '.join(confidences)}")
            
            if statistics:
                result_text.append(f"📊 当前人数: {getattr(statistics, 'current_count', 0)}")
                result_text.append(f"📈 平均人数: {getattr(statistics, 'avg_count', 0):.1f}")
                result_text.append(f"📈 趋势: {getattr(statistics, 'trend', '未知')}")
            
            if performance:
                result_text.append(f"⚡ 分析FPS: {performance.get('analysis_fps', 0):.1f}")
                result_text.append(f"⏱️ 延迟: {performance.get('avg_analysis_time_ms', 0):.1f}ms")
                result_text.append(f"🔄 总分析次数: {performance.get('total_analyses', 0)}")
            
            # 更新分析结果文本框
            self.ai_results_text.setPlainText('\n'.join(result_text))
            
            # 更新性能统计标签
            self.fps_label.setText(f"FPS: {performance.get('analysis_fps', 0):.1f}")
            self.latency_label.setText(f"延迟: {performance.get('avg_analysis_time_ms', 0):.1f}ms")
            self.analysis_count_label.setText(f"分析次数: {performance.get('total_analyses', 0)}")
            
        except Exception as e:
            print(f"更新AI分析结果时出错: {e}")
            self.ai_results_text.setPlainText(f"更新结果时出错: {e}")
    
    def update_ai_analysis_result(self, analysis_info):
        """更新AI分析结果显示（兼容性方法，实际使用_on_analysis_result）"""
        try:
            # 直接调用新的回调方法
            self._on_analysis_result(analysis_info)
        except Exception as e:
            print(f"更新AI分析结果显示错误: {e}")
            self.ai_results_text.setPlainText(f"更新显示错误: {e}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止摄像头
        try:
            if hasattr(self, 'camera_controller'):
                self.camera_controller.stop_camera()
        except Exception as e:
            print(f"关闭摄像头错误: {e}")
        
        # 停止MPV广告
        try:
            if hasattr(self, 'player'):
                self.player.stop_ad_overlay()
        except Exception as e:
            print(f"停止MPV广告错误: {e}")
        
        event.accept()
