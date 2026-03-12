#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手势识别控制器
独立的手势识别模块，支持与面部检测的切换
"""

import cv2
import numpy as np
import time
import threading
import os
from typing import Optional, Callable
from .mediapipe_hand_gesture_detector import MediaPipeHandGestureDetector


class GestureController:
    """手势识别控制器"""
    
    def __init__(self, config: dict = None, player=None):
        """
        初始化手势控制器
        
        Args:
            config: 配置参数
            player: MPV播放器控制器实例
        """
        self.config = config or {}
        self.detector: Optional[MediaPipeHandGestureDetector] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.camera: Optional[cv2.VideoCapture] = None
        self.callback: Optional[Callable] = None
        self.player = player  # MPV播放器控制器
        
        # 手势控制映射
        self.gesture_actions = {
            "fist": "play",           # 拳头：继续播放
            "open_palm": "pause",      # 张开手掌：暂停播放
            "thumb_up": "volume_up",
            "victory": "next",
            "ok": "ok",
            "counting_1": "volume_down",
            "counting_2": "toggle_fullscreen",
            "counting_3": "seek_forward",
            "counting_4": "seek_backward",
            "counting_5": "restart"
        }
            
        # 性能统计
        self.frame_count = 0
        self.start_time = time.time()
        self.last_action_time = 0
        self.action_cooldown = 2.0  # 动作冷却时间(秒)
        
        # 性能优化参数
        self.max_fps = 10  # 最大处理帧率
        self.last_process_time = 0
        self.skip_frames = 0  # 跳帧计数器
        self.skip_frame_interval = 2  # 每2帧处理1帧

        # 手势状态跟踪
        self.last_stable_gesture = None  # 上一个稳定的手势
        self.normal_gesture_buffer = []  # 普通手势缓冲区，用于连续检测
        self.emergency_gesture_buffer = []  # 紧急手势缓冲区，用于连续检测
        self.required_confirmations = 0  # 需要连续确认的次数（紧急呼叫手势需要更多确认）
        self.gesture_threshold = 5  # 普通手势连续确认阈值
        self.emergency_threshold = 8  # 紧急呼叫手势连续确认阈值（更高要求）
        
        # 紧急呼叫功能相关状态
        self.emergency_state = "idle"  # 紧急呼叫状态：idle(空闲态), asking(询问态), confirmed(确认态)
        self.emergency_help_played_count = 0  # help.mp4播放次数
        self.original_playlist = []  # 原始播放列表
        self.emergency_help_file = None  # help.mp4文件路径
        self.emergency_call_file = None  # call.mp4文件路径
        
        # 紧急呼叫检测标记
        self.emergency_gesture_detected = False  # 是否检测到确认手势
        self.emergency_gesture_time = 0  # 检测到确认手势的时间
        
        # 检查紧急呼叫文件是否存在
        self._check_emergency_files()

        print("手势控制器初始化完成（性能优化版 + 稳定检测 + 紧急呼叫功能）")
    
    def _check_emergency_files(self) -> None:
        """检查紧急呼叫相关文件是否存在"""
        # 获取下载目录路径（视频下载目录）
        download_dir = self.config.get('download', {}).get('path', '.')
        
        # 打印详细的配置信息用于调试
        print(f"=== 紧急呼叫文件检测调试信息 ===")
        print(f"完整配置: {self.config}")
        print(f"download配置: {self.config.get('download', {})}")
        print(f"下载目录路径: {download_dir}")
        print(f"下载目录是否存在: {os.path.exists(download_dir)}")
        
        # 检查help.mp4和call.mp4文件
        help_file = os.path.join(download_dir, 'help.mp4')
        call_file = os.path.join(download_dir, 'call.mp4')
        
        help_exists = os.path.exists(help_file)
        call_exists = os.path.exists(call_file)
        
        # 打印文件路径详细信息
        print(f"help.mp4完整路径: {help_file}")
        print(f"call.mp4完整路径: {call_file}")
        print(f"help.mp4是否存在: {help_exists}")
        print(f"call.mp4是否存在: {call_exists}")
        
        # 列出下载目录中的所有文件
        if os.path.exists(download_dir):
            files = os.listdir(download_dir)
            print(f"下载目录中的文件列表: {files}")
        else:
            print("下载目录不存在，无法列出文件")
        
        print("================================")
        
        if help_exists and call_exists:
            self.emergency_help_file = help_file
            self.emergency_call_file = call_file
            print(f"检测到紧急呼叫文件: help.mp4={help_exists}, call.mp4={call_exists}")
            print("紧急呼叫功能已启用：拳头和张开手掌将用于紧急呼叫操作")
        else:
            print(f"紧急呼叫文件不存在: help.mp4={help_exists}, call.mp4={call_exists}")
            print("紧急呼叫功能未启用：拳头和张开手掌保持原有播放控制功能")
    
    def _find_available_camera(self, preferred_index: int = 2) -> int:
        """
        查找可用的摄像头索引 - 智能选择未被摄像头控制器占用的摄像头
        
        Args:
            preferred_index: 首选摄像头索引
            
        Returns:
            可用的摄像头索引，如果都不可用返回-1
        """
        # 参考camera_controller.py的智能后端选择策略
        backends = [
            cv2.CAP_V4L2,   # 优先使用V4L2（针对Linux设备）
            cv2.CAP_ANY,    # 次选自动选择
            cv2.CAP_FFMPEG  # 最后尝试FFMPEG
        ]
        
        # 智能检测策略：优先尝试非摄像头2的索引，避免与摄像头控制器冲突
        # 如果摄像头控制器正在运行，它通常会占用摄像头2
        camera_order = [
            0,  # 优先尝试摄像头0
            1, 3, 4,  # 然后尝试其他摄像头
            preferred_index  # 最后尝试首选索引（通常是2）
        ]
        
        for index in camera_order:
            for backend in backends:
                try:
                    camera = cv2.VideoCapture(index, backend)
                    if camera.isOpened():
                        # 验证摄像头可用性
                        ret, frame = camera.read()
                        camera.release()
                        if ret and frame is not None:
                            print(f"使用后端 {backend} 成功打开摄像头 {index}")
                            return index
                except Exception as e:
                    print(f"后端 {backend} 打开摄像头 {index} 失败: {e}")
        
        return -1
    
    def start(self, callback: Callable = None) -> bool:
        """
        启动手势识别
        
        Args:
            callback: 手势动作回调函数
            
        Returns:
            启动是否成功
        """
        if self.running:
            print("手势识别已在运行中")
            return True
        
        try:
            # 初始化手势检测器
            self.detector = MediaPipeHandGestureDetector(
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            
            # 设置回调函数
            self.callback = callback
            
            # 手势控制器不自己打开摄像头，而是等待外部提供帧数据
            self.camera = None  # 不使用独立摄像头
            
            # 启动识别线程
            self.running = True
            self.thread = threading.Thread(target=self._gesture_loop, daemon=True)
            self.thread.start()
            
            print("手势识别模块已启动（等待外部帧数据）")
            return True
            
        except Exception as e:
            print(f"启动手势识别失败: {e}")
            self.stop()
            return False
    
    def stop(self) -> None:
        """停止手势识别"""
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        if self.detector:
            self.detector.release()
            self.detector = None
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        print("手势识别已停止")
    
    def _gesture_loop(self) -> None:
        """手势识别主循环"""
        print("手势识别循环启动，等待外部帧数据")
        while self.running:
            try:
                # 手势控制器通过process_frame方法接收外部帧数据
                # 这里只需保持线程活跃，不进行主动检测
                time.sleep(2)
                
                # 性能统计
                self.frame_count += 1
                if self.frame_count % 15 == 0:  # 每15次循环打印一次状态
                    elapsed = time.time() - self.start_time
                    fps = self.frame_count / elapsed if elapsed > 0 else 0
                    print(f"手势识别循环活跃中: {fps:.1f} FPS (等待外部帧数据)")
                
            except Exception as e:
                print(f"手势识别循环异常: {e}")
                time.sleep(1)
    
    def process_frame(self, frame: np.ndarray) -> Optional[dict]:
        """
        处理摄像头帧数据 - 增强版本，支持详细统计信息
        
        Args:
            frame: 输入图像帧 (BGR格式，480x640竖屏)
            
        Returns:
            手势检测结果字典，包含手势信息和旋转后的图像
        """
        if not self.running or not self.detector:
            return None
            
        try:
            # 恢复跳帧机制：每2帧处理1帧
            self.skip_frames += 1
            if self.skip_frames % self.skip_frame_interval != 0:
                return None
            
            # 性能优化：帧率控制
            current_time = time.time()
            time_interval = current_time - self.last_process_time
            
            # 如果时间间隔太短，跳过处理以控制帧率
            if time_interval < 1.0 / self.max_fps:
                return None
            
            self.last_process_time = current_time
            
            # 检测手势
            detection_results = self.detector.detect_hands(frame)
            
            # 获取当前检测到的手势
            gestures = detection_results.get('gestures', [])
            current_gesture = gestures[0] if gestures else "unknown"
            
            # 性能优化：只在检测到手部时才绘制
            if detection_results['hands_count'] > 0:
                # 在原始图像上绘制手势信息
                display_frame = frame.copy()
                display_frame = self.detector.draw_hand_landmarks(display_frame, detection_results)
                
                # 处理当前检测到的手势（实时处理，不使用缓冲区）
                if current_gesture != "unknown":
                    # 打印详细的统计信息
                    gesture_display_name = self._get_gesture_display_name(current_gesture)
                    fps = detection_results.get('fps', 0)
                    hands_count = detection_results.get('hands_count', 0)
                    
                    # 显示详细统计信息（每10帧显示一次，避免过于频繁）
                    if self.frame_count % 10 == 0:
                        print(f"=== 手势识别统计 ===")
                        print(f"手势: {gesture_display_name}")
                        print(f"手部数量: {hands_count}")
                        print(f"处理帧率: {fps:.1f} FPS")
                        print(f"累计帧数: {self.frame_count}")
                        print("======================")
                    else:
                        # 普通模式只显示手势名称
                        print(f"手势：{gesture_display_name}")
                    
                    # 处理手势动作（应用冷却时间机制）
                    self._process_gestures([current_gesture])
                    
                    # 更新最后稳定手势
                    self.last_stable_gesture = current_gesture
                
                # 返回结果 - 注意：返回未旋转的帧，旋转由控制器统一处理
                result = {
                    'gestures': gestures,
                    'current_gesture': current_gesture,  # 改为当前手势而非稳定手势
                    'hands_count': detection_results.get('hands_count', 0),
                    'display_frame': display_frame,  # 未旋转的帧
                    'original_frame': frame,
                    'rotated': False,  # 标记为未旋转，由控制器统一旋转
                    'fps': detection_results.get('fps', 0)
                }
            else:
                # 没有检测到手部，直接返回原始帧
                # 重置手势状态
                self.last_stable_gesture = "unknown"
                
                # 每20帧显示一次无手部检测的信息
                if self.frame_count % 20 == 0:
                    print("未检测到手部")
                
                result = {
                    'gestures': [],
                    'current_gesture': "unknown",
                    'hands_count': 0,
                    'display_frame': frame,  # 未旋转的帧
                    'original_frame': frame,
                    'rotated': False,
                    'fps': detection_results.get('fps', 0)
                }
            
            return result
            
        except Exception as e:
            return None
    
    def _check_gesture_consistency(self, current_gesture: str) -> bool:
        """检查手势是否连续确认达到阈值"""
        # 如果是unknown手势，清空缓冲区
        if current_gesture == "unknown":
            self.normal_gesture_buffer = []
            return False
        
        # 将当前手势添加到缓冲区
        self.normal_gesture_buffer.append(current_gesture)
        
        # 保持缓冲区大小不超过阈值
        if len(self.normal_gesture_buffer) > self.gesture_threshold:
            self.normal_gesture_buffer.pop(0)
        
        # 检查缓冲区中是否连续出现相同手势
        if len(self.normal_gesture_buffer) >= self.gesture_threshold:
            # 检查是否所有手势都相同
            if all(gesture == current_gesture for gesture in self.normal_gesture_buffer):
                print(f"手势连续确认成功: {current_gesture} (连续{len(self.normal_gesture_buffer)}次)")
                self.normal_gesture_buffer = []  # 清空缓冲区
                return True
        
        return False
    
    def _check_emergency_gesture_consistency(self, current_gesture: str) -> bool:
        """检查紧急呼叫手势是否连续确认达到更高阈值"""
        # 紧急呼叫手势需要更高的确认要求
        if current_gesture not in ["open_palm", "fist"]:
            return False
        
        # 将当前手势添加到缓冲区
        self.emergency_gesture_buffer.append(current_gesture)
        
        # 保持缓冲区大小不超过紧急阈值
        if len(self.emergency_gesture_buffer) > self.emergency_threshold:
            self.emergency_gesture_buffer.pop(0)
        
        # 检查缓冲区中是否连续出现相同手势
        if len(self.emergency_gesture_buffer) >= self.emergency_threshold:
            # 检查是否所有手势都相同
            if all(gesture == current_gesture for gesture in self.emergency_gesture_buffer):
                print(f"紧急手势连续确认成功: {current_gesture} (连续{len(self.emergency_gesture_buffer)}次)")
                self.emergency_gesture_buffer = []  # 清空缓冲区
                return True
        
        return False
    
    def _get_gesture_display_name(self, gesture: str) -> str:
        """获取手势的显示名称"""
        gesture_names = {
            "fist": "拳头",
            "open_palm": "张开手掌",
            "thumb_up": "大拇指向上", 
            "victory": "剪刀手(V)",
            "ok": "OK手势",
            "pointing": "食指指向",
            "counting_1": "手指计数1",
            "counting_2": "手指计数2", 
            "counting_3": "手指计数3",
            "counting_4": "手指计数4",
            "counting_5": "手指计数5"
        }
        return gesture_names.get(gesture, gesture)
    
    def _process_gestures(self, gestures: list) -> None:
        """
        处理识别到的手势 - 支持紧急呼叫模式
        
        Args:
            gestures: 手势列表
        """
        current_time = time.time()
        
        # 检查冷却时间
        if current_time - self.last_action_time < self.action_cooldown:
            return
        
        # 处理每个手势
        for gesture in gestures:
            # 根据紧急呼叫状态处理手势
            if self.emergency_state == "idle":
                # 空闲态：根据紧急呼叫文件是否存在决定手势行为
                if self.emergency_help_file and self.emergency_call_file:
                    # 存在紧急呼叫文件：拳头和张开手掌用于紧急呼叫
                    if gesture == "open_palm":
                        # 张开手掌：需要连续确认达到紧急阈值
                        if self._check_emergency_gesture_consistency(gesture):
                            # 启动紧急呼叫帮助流程
                            self._start_emergency_help()
                            self.last_action_time = current_time
                            print("手势控制: 张开手掌 -> 启动紧急呼叫（已连续确认）")
                        else:
                            print(f"手势检测: 张开手掌（还需{self.emergency_threshold - len(self.emergency_gesture_buffer)}次确认）")
                    elif gesture == "fist":
                        # 拳头：在正常模式下保持继续播放功能，需要普通连续确认
                        if self._check_gesture_consistency(gesture):
                            if self.player and hasattr(self.player, 'toggle_pause'):
                                if not self._is_mpv_playing():
                                    self.player.toggle_pause()
                                    print(f"手势控制: 拳头 -> 继续播放（已连续确认）")
                            self.last_action_time = current_time
                        else:
                            print(f"手势检测: 拳头（还需{self.gesture_threshold - len(self.normal_gesture_buffer)}次确认）")
                    else:
                        # 其他手势保持原有功能，需要普通连续确认
                        if self._check_gesture_consistency(gesture):
                            self._process_normal_gesture(gesture, current_time)
                        else:
                            print(f"手势检测: {gesture}（还需{self.gesture_threshold - len(self.normal_gesture_buffer)}次确认）")
                else:
                    # 不存在紧急呼叫文件：保持原有手势功能，需要普通连续确认
                    if self._check_gesture_consistency(gesture):
                        self._process_normal_gesture(gesture, current_time)
                    else:
                        print(f"手势检测: {gesture}（还需{self.gesture_threshold - len(self.normal_gesture_buffer)}次确认）")
            
            elif self.emergency_state == "asking":
                # 询问态：只处理拳头手势（确认紧急呼叫），需要连续确认
                if gesture == "fist":
                    if self._check_emergency_gesture_consistency(gesture):
                        # 检测到拳头手势：确认紧急呼叫
                        self._confirm_emergency_call()
                        self.last_action_time = current_time
                    else:
                        print(f"紧急确认: 拳头（还需{self.emergency_threshold - len(self.emergency_gesture_buffer)}次确认）")
                # 询问态下检测到其他手势（包括手掌）不处理
                
            elif self.emergency_state == "confirmed":
                # 确认态：不处理任何手势，等待call视频播放结束
                pass
    
    def _confirm_emergency_call(self) -> None:
        """确认紧急呼叫，从询问态切换到确认态"""
        print("紧急呼叫确认：检测到拳头手势，确认需要救援")
        
        # 停止当前正在播放的help视频
        if self.player and hasattr(self.player, '_stop_current_playback'):
            self.player._stop_current_playback()
            print("已停止help视频播放")
        
        # 切换到确认态
        self.emergency_state = "confirmed"
        
        # 播放紧急呼叫确认视频
        self._play_emergency_call()
    
    def _process_normal_gesture(self, gesture: str, current_time: float) -> None:
        """处理正常模式下的手势"""
        action = self.gesture_actions.get(gesture)
        if action:
            try:
                # 优先使用MPV播放器直接控制
                if self.player and hasattr(self.player, 'toggle_pause'):
                    if gesture == "open_palm":
                        # 张开手掌：暂停播放
                        if self._is_mpv_playing():
                            self.player.toggle_pause()
                            print(f"手势控制: 张开手掌 -> 暂停播放")
                    elif gesture == "fist":
                        # 拳头：继续播放
                        if not self._is_mpv_playing():
                            self.player.toggle_pause()
                            print(f"手势控制: 拳头 -> 继续播放")
                
                # 如果有回调函数，也执行回调
                if self.callback:
                    self.callback({
                        'action': action,
                        'gesture': gesture,
                        'timestamp': current_time
                    })
                
                # 更新最后动作时间
                self.last_action_time = current_time
                print(f"手势动作: {gesture} -> {action}")
                
            except Exception as e:
                print(f"手势回调执行失败: {e}")
    
    def _start_emergency_help(self) -> None:
        """开始紧急呼叫帮助流程"""
        if not self.emergency_help_file or not self.player:
            print("无法启动紧急呼叫：缺少必要文件或播放器")
            return
        
        # 保存当前播放列表
        if hasattr(self.player, 'queue') and self.player.queue:
            self.original_playlist = self.player.queue.copy()
            print(f"DEBUG: 保存原始播放列表，长度: {len(self.original_playlist)}")
            if self.original_playlist:
                print(f"DEBUG: 第一个文件: {self.original_playlist[0]}")
        else:
            print("DEBUG: 无法保存播放列表，queue为空或不存在")
        
        # 设置紧急呼叫状态为询问态
        self.emergency_state = "asking"
        self.emergency_help_played_count = 0
        self.emergency_gesture_detected = False
        self.emergency_gesture_time = 0
        
        # 播放help.mp4
        self._play_emergency_help()
        
        print("紧急呼叫流程已启动：进入询问态，正在播放帮助视频")
    
    def _play_emergency_help(self) -> None:
        """播放紧急呼叫帮助视频"""
        if not self.emergency_help_file or not self.player:
            return
        
        # 检查是否已经播放3次或状态已改变
        if self.emergency_help_played_count >= 3 or self.emergency_state != "asking":
            print(f"帮助视频已播放{self.emergency_help_played_count}次，状态{self.emergency_state}，停止播放")
            return
        
        # 播放help.mp4，启用循环播放
        if hasattr(self.player, 'play_single_file'):
            # 第一次播放时，设置循环播放，并设置超时定时器
            if self.emergency_help_played_count == 0:
                self.player.play_single_file(self.emergency_help_file, loop=True)
                # 设置超时定时器：视频时长（约11秒）× 3次播放 + 缓冲时间 = 约40秒
                print("帮助视频开始循环播放，设置40秒超时")
                threading.Timer(40.0, self._handle_emergency_timeout).start()
            
        self.emergency_help_played_count += 1
        print(f"第 {self.emergency_help_played_count} 次播放帮助视频（循环播放）")
        
        # 第3次播放后，记录日志（超时已经在第一次播放时设置）
        if self.emergency_help_played_count >= 3:
            print("帮助视频已播放3次，等待用户确认或超时")
    
    def _play_emergency_call(self) -> None:
        """播放紧急呼叫确认视频"""
        if not self.emergency_call_file or not self.player:
            return
        
        # 确保当前状态是confirmed才播放call视频
        if self.emergency_state != "confirmed":
            print(f"警告：尝试在状态{self.emergency_state}下播放call视频，跳过")
            return
        
        # 播放call.mp4，播放完整视频
        if hasattr(self.player, 'play_single_file'):
            self.player.play_single_file(self.emergency_call_file)
        
        print("播放紧急呼叫确认视频（完整播放）")
        
        # 设置定时器，等待视频自然结束（根据视频时长设置，call视频约17秒）
        threading.Timer(20.0, self._check_call_video_end).start()
    
    def _check_call_video_end(self) -> None:
        """检查call视频是否播放结束"""
        if self.emergency_state == "confirmed":
            print("call视频播放结束，恢复原始播放列表")
            # 添加调试信息
            print(f"DEBUG: 原始播放列表长度: {len(self.original_playlist)}")
            if self.original_playlist:
                print(f"DEBUG: 第一个文件: {self.original_playlist[0]}")
            else:
                print("DEBUG: 原始播放列表为空")
            self._end_emergency_mode()
    
    def _handle_emergency_timeout(self) -> None:
        """处理紧急呼叫超时"""
        if self.emergency_state == "asking" and not self.emergency_gesture_detected:
            # 询问态超时：播放3次help视频后仍未检测到确认手势
            print("紧急呼叫超时：3次播放后未检测到确认手势，恢复正常播放")
            self._end_emergency_mode()
    
    def _end_emergency_mode(self) -> None:
        """结束紧急呼叫模式，恢复原始播放列表"""
        # 重置状态
        self.emergency_state = "idle"
        self.emergency_help_played_count = 0
        self.emergency_gesture_detected = False
        
        # 添加调试信息
        print(f"DEBUG: _end_emergency_mode调用，原始播放列表长度: {len(self.original_playlist)}")
        
        # 恢复原始播放列表（注意：不要停止当前播放，让MPV自然过渡）
        if self.original_playlist and hasattr(self.player, 'set_playlist'):
            print(f"DEBUG: 调用set_playlist恢复播放列表")
            self.player.set_playlist(self.original_playlist)
            self.original_playlist = []
        else:
            print("DEBUG: 无法恢复播放列表，条件不满足")
            # 如果无法恢复播放列表，至少停止当前播放
            if self.player and hasattr(self.player, '_stop_current_playback'):
                print("DEBUG: 调用_stop_current_playback停止播放")
                self.player._stop_current_playback()
        
        print("紧急呼叫模式已结束，恢复原始播放列表")
    
    def _is_mpv_playing(self) -> bool:
        """检查MPV是否正在播放（通过IPC查询状态）"""
        try:
            if self.player and hasattr(self.player, 'query_mpv_status'):
                status = self.player.query_mpv_status()
                if isinstance(status, dict) and 'paused' in status:
                    return not status['paused']  # paused=True表示暂停，False表示播放
            return True  # 默认认为正在播放
        except Exception as e:
            print(f"查询MPV播放状态失败: {e}")
            return True  # 默认认为正在播放
    
    def set_gesture_action(self, gesture: str, action: str) -> None:
        """
        设置手势动作映射
        
        Args:
            gesture: 手势名称
            action: 对应动作
        """
        self.gesture_actions[gesture] = action
        print(f"设置手势映射: {gesture} -> {action}")
    
    def get_performance_stats(self) -> dict:
        """获取性能统计"""
        elapsed = time.time() - self.start_time
        return {
            'fps': self.frame_count / elapsed if elapsed > 0 else 0,
            'frame_count': self.frame_count,
            'running_time': elapsed,
            'running': self.running
        }


def main():
    """测试函数"""
    def gesture_callback(data: dict):
        print(f"收到手势动作: {data}")
    
    controller = GestureController(config={}, player=None)
    
    try:
        if controller.start(callback=gesture_callback):
            print("手势识别测试开始，按Ctrl+C停止")
            
            # 运行一段时间
            import time
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n收到停止信号")
    finally:
        controller.stop()
        print("测试完成")


if __name__ == "__main__":
    main()