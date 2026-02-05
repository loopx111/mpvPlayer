"""
人脸计数器

实现人脸检测结果的统计功能，包括人脸计数、检测频率统计等。
"""

import time
import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class FaceCountStats:
    """人脸统计数据结构"""
    total_faces: int = 0  # 累计检测到的人脸总数
    current_faces: int = 0  # 当前帧检测到的人脸数
    max_faces: int = 0  # 最大同时检测到的人脸数
    avg_faces: float = 0.0  # 平均每帧检测到的人脸数
    detection_frames: int = 0  # 检测到人脸的帧数
    total_frames: int = 0  # 总处理帧数
    detection_rate: float = 0.0  # 检测率（检测到人脸的帧数/总帧数）
    last_update_time: float = 0.0  # 最后更新时间


class FaceCounter:
    """人脸计数器类"""
    
    def __init__(self, smoothing_window: int = 30):
        """
        初始化人脸计数器
        
        Args:
            smoothing_window: 平滑窗口大小，用于计算平均检测率
        """
        self.smoothing_window = smoothing_window
        
        # 统计信息
        self.stats = FaceCountStats()
        
        # 历史记录
        self.face_counts_history = []  # 最近的人脸计数历史
        self.detection_times = []  # 检测时间记录
        
        # 时间跟踪
        self.start_time = time.time()
        self.last_reset_time = self.start_time
    
    def update_count(self, face_count: int, timestamp: Optional[float] = None) -> Dict:
        """
        更新人脸计数
        
        Args:
            face_count: 当前帧检测到的人脸数
            timestamp: 时间戳（可选，默认使用当前时间）
        
        Returns:
            更新统计信息
        """
        if timestamp is None:
            timestamp = time.time()
        
        # 更新总帧数
        self.stats.total_frames += 1
        
        # 更新当前人脸数
        self.stats.current_faces = face_count
        
        # 更新累计统计
        if face_count > 0:
            self.stats.detection_frames += 1
            self.stats.total_faces += face_count
            
            # 更新最大人脸数
            if face_count > self.stats.max_faces:
                self.stats.max_faces = face_count
        
        # 更新平均人脸数
        if self.stats.total_frames > 0:
            self.stats.avg_faces = self.stats.total_faces / self.stats.total_frames
            self.stats.detection_rate = self.stats.detection_frames / self.stats.total_frames
        
        # 更新最后更新时间
        self.stats.last_update_time = timestamp
        
        # 保存历史记录
        self.face_counts_history.append(face_count)
        self.detection_times.append(timestamp)
        
        # 保持历史记录在窗口大小内
        if len(self.face_counts_history) > self.smoothing_window:
            self.face_counts_history.pop(0)
            self.detection_times.pop(0)
        
        return self._get_update_info()
    
    def _get_update_info(self) -> Dict:
        """获取更新信息"""
        return {
            'current_faces': self.stats.current_faces,
            'total_faces': self.stats.total_faces,
            'max_faces': self.stats.max_faces,
            'avg_faces': round(self.stats.avg_faces, 2),
            'detection_rate': round(self.stats.detection_rate * 100, 2),
            'total_frames': self.stats.total_frames,
            'detection_frames': self.stats.detection_frames
        }
    
    def get_statistics(self) -> FaceCountStats:
        """获取完整统计信息"""
        return self.stats
    
    def get_recent_statistics(self, window_size: Optional[int] = None) -> Dict:
        """
        获取最近时间窗口内的统计信息
        
        Args:
            window_size: 窗口大小（秒），默认使用smoothing_window
        
        Returns:
            窗口内的统计信息
        """
        if window_size is None:
            window_size = self.smoothing_window
        
        current_time = time.time()
        window_start = current_time - window_size
        
        # 筛选窗口内的数据
        window_counts = []
        window_times = []
        
        for i, t in enumerate(self.detection_times):
            if t >= window_start:
                window_counts.append(self.face_counts_history[i])
                window_times.append(t)
        
        if not window_counts:
            return {
                'window_faces': 0,
                'window_avg_faces': 0.0,
                'window_detection_rate': 0.0,
                'window_frames': 0
            }
        
        window_total_faces = sum(window_counts)
        window_frames = len(window_counts)
        window_detection_frames = sum(1 for count in window_counts if count > 0)
        
        return {
            'window_faces': window_total_faces,
            'window_avg_faces': round(window_total_faces / window_frames, 2),
            'window_detection_rate': round(window_detection_frames / window_frames * 100, 2),
            'window_frames': window_frames
        }
    
    def get_detection_frequency(self) -> float:
        """获取检测频率（每秒检测次数）"""
        if len(self.detection_times) < 2:
            return 0.0
        
        time_span = self.detection_times[-1] - self.detection_times[0]
        if time_span <= 0:
            return 0.0
        
        return len(self.detection_times) / time_span
    
    def reset_statistics(self):
        """重置统计信息"""
        self.stats = FaceCountStats()
        self.face_counts_history = []
        self.detection_times = []
        self.start_time = time.time()
        self.last_reset_time = self.start_time
    
    def get_runtime_info(self) -> Dict:
        """获取运行时信息"""
        current_time = time.time()
        runtime = current_time - self.start_time
        time_since_reset = current_time - self.last_reset_time
        
        return {
            'runtime_seconds': round(runtime, 2),
            'time_since_reset': round(time_since_reset, 2),
            'detection_frequency': round(self.get_detection_frequency(), 2)
        }


def test_face_counter():
    """测试人脸计数器功能"""
    counter = FaceCounter()
    
    # 模拟一些检测结果
    test_counts = [0, 1, 0, 2, 0, 3, 0, 1, 0, 2, 0, 3, 0, 1, 0]
    
    for count in test_counts:
        counter.update_count(count)
        time.sleep(0.1)  # 模拟帧间隔
    
    # 打印统计结果
    stats = counter.get_statistics()
    print("人脸统计信息:")
    print("总帧数: " + str(stats.total_frames))
    print("检测帧数: " + str(stats.detection_frames))
    print("累计人脸数: " + str(stats.total_faces))
    print("最大人脸数: " + str(stats.max_faces))
    print("平均人脸数: " + str(round(stats.avg_faces, 2)))
    print("检测率: " + str(round(stats.detection_rate * 100, 2)) + "%")
    
    # 打印最近统计
    recent_stats = counter.get_recent_statistics(5)
    print("\n最近5秒统计:")
    print("窗口内人脸数: " + str(recent_stats['window_faces']))
    print("窗口内平均人脸数: " + str(recent_stats['window_avg_faces']))
    print("窗口内检测率: " + str(recent_stats['window_detection_rate']) + "%")


if __name__ == "__main__":
    test_face_counter()