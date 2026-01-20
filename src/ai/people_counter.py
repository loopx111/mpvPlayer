"""
人数统计模块

实现基于时间序列的人数统计和趋势分析，
支持人数变化检测和统计信息生成。
"""

import time
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from collections import deque


@dataclass
class PeopleCountStats:
    """人数统计信息"""
    current_count: int = 0
    max_count: int = 0
    min_count: int = 0
    avg_count: float = 0.0
    total_detections: int = 0
    detection_rate: float = 0.0
    trend: str = "stable"  # increasing, decreasing, stable
    change_count: int = 0  # 人数变化次数


class PeopleCounter:
    """实时人数统计器"""
    
    def __init__(self, history_size: int = 60, change_threshold: int = 1):
        """
        初始化人数统计器
        
        Args:
            history_size: 历史记录大小（秒）
            change_threshold: 人数变化阈值
        """
        self.history_size = history_size
        self.change_threshold = change_threshold
        
        # 历史记录队列
        self.count_history = deque(maxlen=history_size)
        self.timestamp_history = deque(maxlen=history_size)
        
        # 统计信息
        self.current_count = 0
        self.max_count = 0
        self.min_count = float('inf')
        self.total_detections = 0
        self.start_time = time.time()
        self.last_change_time = time.time()
        
        # 趋势分析
        self.trend_window = 10  # 趋势分析窗口大小
        self.trend_threshold = 0.1  # 趋势变化阈值
    
    def update_count(self, new_count: int, timestamp: Optional[float] = None) -> Dict:
        """
        更新人数统计
        
        Args:
            new_count: 新检测到的人数
            timestamp: 时间戳（可选，默认使用当前时间）
            
        Returns:
            更新统计信息
        """
        if timestamp is None:
            timestamp = time.time()
        
        # 更新历史记录
        self.count_history.append(new_count)
        self.timestamp_history.append(timestamp)
        
        # 更新当前人数
        old_count = self.current_count
        self.current_count = new_count
        
        # 更新最大值和最小值
        self.max_count = max(self.max_count, new_count)
        if len(self.count_history) > 0:
            self.min_count = min(self.min_count, new_count)
        else:
            self.min_count = min(self.min_count, new_count) if self.min_count != float('inf') else new_count
        
        # 更新总检测次数
        self.total_detections += 1
        
        # 检测人数变化
        change_info = self._detect_change(old_count, new_count, timestamp)
        
        # 分析趋势
        trend_info = self._analyze_trend()
        
        return {
            'current_count': new_count,
            'old_count': old_count,
            'change_detected': change_info['changed'],
            'change_magnitude': change_info['magnitude'],
            'trend': trend_info['trend'],
            'trend_strength': trend_info['strength']
        }
    
    def _detect_change(self, old_count: int, new_count: int, timestamp: float) -> Dict:
        """检测人数变化"""
        magnitude = abs(new_count - old_count)
        changed = magnitude >= self.change_threshold
        
        if changed:
            self.last_change_time = timestamp
        
        return {
            'changed': changed,
            'magnitude': magnitude,
            'direction': 'increase' if new_count > old_count else 'decrease' if new_count < old_count else 'stable'
        }
    
    def _analyze_trend(self) -> Dict:
        """分析人数变化趋势"""
        if len(self.count_history) < self.trend_window:
            return {'trend': 'insufficient_data', 'strength': 0.0}
        
        # 获取最近的数据点
        recent_counts = list(self.count_history)[-self.trend_window:]
        
        # 计算线性回归斜率
        x = np.arange(len(recent_counts))
        y = np.array(recent_counts)
        
        # 计算斜率
        if len(set(y)) > 1:  # 避免除零错误
            slope = np.polyfit(x, y, 1)[0]
        else:
            slope = 0
        
        # 判断趋势
        if slope > self.trend_threshold:
            trend = 'increasing'
            strength = min(abs(slope) / 5.0, 1.0)  # 归一化到0-1
        elif slope < -self.trend_threshold:
            trend = 'decreasing'
            strength = min(abs(slope) / 5.0, 1.0)
        else:
            trend = 'stable'
            strength = 0.0
        
        return {'trend': trend, 'strength': strength}
    
    def get_statistics(self) -> PeopleCountStats:
        """获取完整的统计信息"""
        current_time = time.time()
        runtime = current_time - self.start_time
        
        # 计算平均人数
        if len(self.count_history) > 0:
            avg_count = sum(self.count_history) / len(self.count_history)
        else:
            avg_count = 0.0
        
        # 计算检测率（每秒检测次数）
        detection_rate = self.total_detections / runtime if runtime > 0 else 0
        
        # 获取趋势信息
        trend_info = self._analyze_trend()
        
        # 计算人数变化次数（基于历史记录）
        change_count = self._count_changes()
        
        return PeopleCountStats(
            current_count=self.current_count,
            max_count=self.max_count,
            min_count=self.min_count if self.min_count != float('inf') else 0,
            avg_count=round(avg_count, 2),
            total_detections=self.total_detections,
            detection_rate=round(detection_rate, 2),
            trend=trend_info['trend'],
            change_count=change_count
        )
    
    def _count_changes(self) -> int:
        """计算人数变化次数"""
        if len(self.count_history) < 2:
            return 0
        
        change_count = 0
        previous_count = self.count_history[0]
        
        for count in list(self.count_history)[1:]:
            if abs(count - previous_count) >= self.change_threshold:
                change_count += 1
            previous_count = count
        
        return change_count
    
    def get_recent_data(self, window_size: int = 30) -> Dict:
        """获取最近的数据点"""
        if len(self.count_history) == 0:
            return {'counts': [], 'timestamps': []}
        
        # 获取最近的window_size个数据点
        recent_counts = list(self.count_history)[-window_size:]
        recent_timestamps = list(self.timestamp_history)[-window_size:]
        
        # 转换为相对时间（秒）
        if recent_timestamps:
            base_time = recent_timestamps[0]
            relative_timestamps = [t - base_time for t in recent_timestamps]
        else:
            relative_timestamps = []
        
        return {
            'counts': recent_counts,
            'timestamps': relative_timestamps,
            'time_window': window_size
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.count_history.clear()
        self.timestamp_history.clear()
        self.current_count = 0
        self.max_count = 0
        self.min_count = float('inf')
        self.total_detections = 0
        self.start_time = time.time()
        self.last_change_time = time.time()
    
    def get_performance_info(self) -> Dict:
        """获取性能信息"""
        current_time = time.time()
        runtime = current_time - self.start_time
        
        stats = self.get_statistics()
        recent_data = self.get_recent_data(10)  # 最近10个数据点
        
        return {
            'runtime_seconds': round(runtime, 2),
            'total_detections': stats.total_detections,
            'detection_rate': stats.detection_rate,
            'current_count': stats.current_count,
            'avg_count': stats.avg_count,
            'max_count': stats.max_count,
            'min_count': stats.min_count,
            'trend': stats.trend,
            'change_count': stats.change_count,
            'recent_data_points': len(recent_data['counts'])
        }


# 测试代码
if __name__ == "__main__":
    # 创建人数统计器
    counter = PeopleCounter(history_size=30)
    
    # 模拟数据更新
    test_counts = [0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 4, 3, 2]
    
    for i, count in enumerate(test_counts):
        result = counter.update_count(count)
        stats = counter.get_statistics()
        
        print(f"检测 {i+1}: 人数={count}, 变化={result['change_detected']}, "
              f"趋势={stats.trend}, 平均={stats.avg_count}")
        
        time.sleep(0.1)  # 模拟实时检测间隔