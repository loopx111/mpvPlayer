from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt, QTimer, QDateTime
from typing import Optional
from ..config.models import AppConfig
from ..comm.mqtt_service import MqttService
from ..file_dist.manager import DownloadManager
from ..player.mpv_controller import MpvController
from ..player.camera_controller import CameraController
from ..camera.embedded_mediapipe_controller import EmbeddedMediaPipeCameraController


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg: AppConfig, mqtt: Optional[MqttService], downloader: DownloadManager, player: MpvController):
        super().__init__()
        self.cfg = cfg
        self.mqtt = mqtt
        self.downloader = downloader
        self.player = player
        
        # 初始化嵌入式MediaPipe摄像头控制器
        self.camera_controller = EmbeddedMediaPipeCameraController()
        
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
        self.loop_status = QtWidgets.QLabel("关闭")
        self.loop_status.setStyleSheet("color: green; font-weight: bold;")
        
        play_layout.addRow("当前文件:", self.current_file)
        play_layout.addRow("播放状态:", self.play_status)
        play_layout.addRow("播放队列:", self.queue_count)
        play_layout.addRow("循环播放:", self.loop_status)
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
        
        # 摄像头显示区域（简化版本，仅保留显示画面）
        camera_group = QtWidgets.QGroupBox("摄像头监控")
        camera_layout = QtWidgets.QVBoxLayout()
        
        # 摄像头状态显示
        self.camera_status = QtWidgets.QLabel("摄像头自动运行中")
        self.camera_status.setStyleSheet("color: green; font-weight: bold;")
        
        # 摄像头画面显示
        camera_layout.addWidget(self.camera_status)
        
        # 创建摄像头显示区域（与测试脚本保持一致，640x480）
        self.camera_display_area = QtWidgets.QWidget()
        camera_display_layout = QtWidgets.QVBoxLayout()
        self.camera_display_area.setLayout(camera_display_layout)
        self.camera_display_area.setMinimumSize(640, 480)
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
        """创建控制面板"""
        panel = QtWidgets.QGroupBox("播放控制")
        layout = QtWidgets.QVBoxLayout()
        
        # 播放列表
        playlist_group = QtWidgets.QGroupBox("播放列表")
        playlist_layout = QtWidgets.QVBoxLayout()
        
        self.playlist_widget = QtWidgets.QListWidget()
        self.playlist_widget.setMaximumHeight(200)
        self.playlist_widget.itemDoubleClicked.connect(self._play_selected_file)
        playlist_layout.addWidget(self.playlist_widget)
        playlist_group.setLayout(playlist_layout)
        
        # 控制按钮已移除，简化界面
        
        layout.addWidget(playlist_group)
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

    def _update_playlist(self) -> None:
        """更新播放列表显示"""
        if not hasattr(self.player, 'queue'):
            return
            
        self.playlist_widget.clear()
        for i, file_path in enumerate(self.player.queue):
            item = QtWidgets.QListWidgetItem(f"{i+1}. {file_path.name}")
            self.playlist_widget.addItem(item)


    
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
            if hasattr(self.player, 'queue') and hasattr(self.player, 'current_file_index'):
                if 0 <= self.player.current_file_index < len(self.player.queue):
                    current_file = self.player.queue[self.player.current_file_index]
                    return current_file.name
                
            # 如果无法通过索引获取，尝试通过其他方式
            if hasattr(self.player, '_get_current_file'):
                current_file = self.player._get_current_file()
                if current_file:
                    return current_file.name
                    
        except Exception as e:
            print(f"获取当前播放文件时出错: {e}")
            
        return ""
    
    def get_current_file_info(self):
        """获取当前播放文件信息（用于MQTT状态报告）"""
        info = {
            "current_file": "",
            "current_index": 0,
            "total_files": 0,
            "playing": False
        }
        
        try:
            # 播放状态
            info["playing"] = bool(self.player.current_process)
            
            # 文件队列信息
            if hasattr(self.player, 'queue'):
                info["total_files"] = len(self.player.queue)
                
                if hasattr(self.player, 'current_file_index') and 0 <= self.player.current_file_index < len(self.player.queue):
                    current_file = self.player.queue[self.player.current_file_index]
                    info["current_file"] = current_file.name
                    info["current_index"] = self.player.current_file_index + 1
                    
        except Exception as e:
            print(f"获取播放文件信息时出错: {e}")
            
        return info

    def _setup_camera(self):
        """初始化摄像头设置"""
        try:
            # 初始化MediaPipe摄像头控制器（默认使用摄像头2并启用人脸检测）
            success = self.camera_controller.initialize(
                camera_index=2,  # 默认使用摄像头2
                resolution=(640, 480), 
                fps=15,
                enable_face_detection=True  # 启用人脸检测
            )
            
            if success:
                print("MediaPipe摄像头控制器初始化成功")
                
                # 添加摄像头控件到界面
                self._update_camera_display()
                
                # 自动启动摄像头（简化版本）
                success = self.camera_controller.start_camera()
                if success:
                    self.camera_status.setText("摄像头自动运行中")
                    self.camera_status.setStyleSheet("color: green; font-weight: bold;")
                    print("摄像头自动启动成功")
                else:
                    print("摄像头自动启动失败")
            else:
                print("摄像头控制器初始化失败")
                self.camera_status.setText("摄像头初始化失败")
                self.camera_status.setStyleSheet("color: red; font-weight: bold;")
                
        except Exception as e:
            print(f"摄像头设置错误: {e}")
            self.camera_status.setText(f"摄像头错误: {e}")
            self.camera_status.setStyleSheet("color: red; font-weight: bold;")
    

    
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
