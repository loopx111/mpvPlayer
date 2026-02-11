"""
性能监控模块

专门用于监控YOLOv5推理性能，提供实时性能分析和优化建议。
"""

import time
import threading
import psutil
from typing import Dict, List, Optional
from dataclasses import dataclass
from collections import deque


@dataclass
class PerformanceSnapshot:
    """性能快照数据结构"""
    timestamp: float
    inference_fps: float
    inference_time_ms: float
    cpu_usage: Dict[int, float]  # 各核心CPU使用率
    memory_usage: float
    ai_core_usage: float  # AI核心平均使用率
    

@dataclass
class PerformanceAnalysis:
    """性能分析结果"""
    avg_fps: float
    avg_inference_time: float
    cpu_bottleneck: bool
    memory_bottleneck: bool
    ai_core_utilization: float
    optimization_suggestions: List[str]
    

class YOLOv5PerformanceMonitor:
    """YOLOv5性能监控器"""
    
    def __init__(self, ai_core_affinity: List[int], window_size: int = 100):
        """
        初始化性能监控器
        
        Args:
            ai_core_affinity: AI推理绑定的核心列表
            window_size: 性能数据窗口大小
        """
        self.ai_core_affinity = ai_core_affinity
        self.window_size = window_size
        
        # 性能数据队列
        self.performance_history = deque(maxlen=window_size)
        self.inference_times = deque(maxlen=window_size)
        
        # 监控状态
        self.monitoring_active = False
        self.monitoring_thread = None
        self.start_time = None
        
        # 统计信息
        self.total_inferences = 0
        self.total_inference_time = 0.0
        
        print(f"[成功] YOLOv5性能监控器初始化完成")
        print(f"[成功] AI核心绑定: {ai_core_affinity}")
        print(f"[成功] 监控窗口大小: {window_size}")
    
    def record_inference(self, inference_time_ms: float):
        """记录一次推理性能数据"""
        current_time = time.time()
        
        # 计算FPS
        fps = 1000 / inference_time_ms if inference_time_ms > 0 else 0
        
        # 获取系统性能数据
        cpu_usage = self._get_cpu_usage()
        memory_usage = psutil.virtual_memory().percent
        
        # 计算AI核心平均使用率
        ai_core_usage = sum(cpu_usage[core] for core in self.ai_core_affinity) / len(self.ai_core_affinity)
        
        # 创建性能快照
        snapshot = PerformanceSnapshot(
            timestamp=current_time,
            inference_fps=fps,
            inference_time_ms=inference_time_ms,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            ai_core_usage=ai_core_usage
        )
        
        # 添加到历史记录
        self.performance_history.append(snapshot)
        self.inference_times.append(inference_time_ms)
        
        # 更新统计信息
        self.total_inferences += 1
        self.total_inference_time += inference_time_ms
    
    def _get_cpu_usage(self) -> Dict[int, float]:
        """获取各核心CPU使用率"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
            return {i: usage for i, usage in enumerate(cpu_percent)}
        except:
            return {}
    
    def get_current_performance(self) -> Dict:
        """获取当前性能数据"""
        if not self.performance_history:
            return {}
        
        latest = self.performance_history[-1]
        
        return {
            'timestamp': latest.timestamp,
            'current_fps': round(latest.inference_fps, 2),
            'current_inference_time_ms': round(latest.inference_time_ms, 2),
            'cpu_usage': {k: round(v, 1) for k, v in latest.cpu_usage.items()},
            'memory_usage': round(latest.memory_usage, 1),
            'ai_core_usage': round(latest.ai_core_usage, 1),
            'total_inferences': self.total_inferences,
            'avg_inference_time_ms': round(self.total_inference_time / self.total_inferences, 2) if self.total_inferences > 0 else 0
        }
    
    def analyze_performance(self) -> PerformanceAnalysis:
        """分析性能数据，提供优化建议"""
        if len(self.performance_history) < 10:
            return PerformanceAnalysis(
                avg_fps=0,
                avg_inference_time=0,
                cpu_bottleneck=False,
                memory_bottleneck=False,
                ai_core_utilization=0,
                optimization_suggestions=["数据不足，请收集更多性能数据"]
            )
        
        # 计算平均性能指标
        recent_snapshots = list(self.performance_history)[-50:]  # 最近50个快照
        
        avg_fps = sum(snapshot.inference_fps for snapshot in recent_snapshots) / len(recent_snapshots)
        avg_inference_time = sum(snapshot.inference_time_ms for snapshot in recent_snapshots) / len(recent_snapshots)
        avg_ai_core_usage = sum(snapshot.ai_core_usage for snapshot in recent_snapshots) / len(recent_snapshots)
        
        # 分析性能瓶颈
        cpu_bottleneck = avg_ai_core_usage > 80  # AI核心使用率超过80%
        memory_bottleneck = any(snapshot.memory_usage > 85 for snapshot in recent_snapshots)
        
        # 生成优化建议
        suggestions = []
        
        if avg_fps < 8:
            suggestions.append("当前FPS较低，建议检查模型输入尺寸和置信度阈值")
        
        if cpu_bottleneck:
            suggestions.append("CPU核心使用率过高，建议降低分析频率或优化模型")
        
        if memory_bottleneck:
            suggestions.append("内存使用率过高，建议减少并发处理或优化内存使用")
        
        if avg_ai_core_usage < 50 and avg_fps < 10:
            suggestions.append("AI核心利用率不足，建议增加并行处理或检查模型配置")
        
        if not suggestions:
            suggestions.append("性能表现良好，继续保持当前配置")
        
        return PerformanceAnalysis(
            avg_fps=round(avg_fps, 2),
            avg_inference_time=round(avg_inference_time, 2),
            cpu_bottleneck=cpu_bottleneck,
            memory_bottleneck=memory_bottleneck,
            ai_core_utilization=round(avg_ai_core_usage, 1),
            optimization_suggestions=suggestions
        )
    
    def get_performance_summary(self) -> Dict:
        """获取性能摘要报告"""
        analysis = self.analyze_performance()
        current = self.get_current_performance()
        
        return {
            'current_performance': current,
            'performance_analysis': {
                'avg_fps': analysis.avg_fps,
                'avg_inference_time_ms': analysis.avg_inference_time,
                'cpu_bottleneck': analysis.cpu_bottleneck,
                'memory_bottleneck': analysis.memory_bottleneck,
                'ai_core_utilization': analysis.ai_core_utilization,
                'optimization_suggestions': analysis.optimization_suggestions
            },
            'statistics': {
                'total_inferences': self.total_inferences,
                'data_points': len(self.performance_history),
                'window_size': self.window_size
            }
        }
    
    def start_realtime_monitoring(self, interval: float = 2.0):
        """启动实时性能监控"""
        if self.monitoring_active:
            print("[警告] 性能监控已在运行")
            return
        
        self.monitoring_active = True
        self.start_time = time.time()
        
        def monitoring_loop():
            while self.monitoring_active:
                try:
                    # 每interval秒打印一次性能摘要
                    summary = self.get_performance_summary()
                    
                    print("\n" + "="*50)
                    print("YOLOv5 实时性能监控报告")
                    print("="*50)
                    
                    current = summary['current_performance']
                    analysis = summary['performance_analysis']
                    
                    print(f"当前FPS: {current.get('current_fps', 0):.1f}")
                    print(f"平均FPS: {analysis.get('avg_fps', 0):.1f}")
                    print(f"推理延迟: {current.get('current_inference_time_ms', 0):.1f}ms")
                    print(f"AI核心使用率: {analysis.get('ai_core_utilization', 0):.1f}%")
                    print(f"内存使用率: {current.get('memory_usage', 0):.1f}%")
                    
                    print("\n优化建议:")
                    for i, suggestion in enumerate(analysis.get('optimization_suggestions', []), 1):
                        print(f"  {i}. {suggestion}")
                    
                    print("="*50)
                    
                    time.sleep(interval)
                    
                except Exception as e:
                    print(f"性能监控错误: {e}")
                    time.sleep(interval)
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        print(f"[成功] 实时性能监控已启动，间隔: {interval}秒")
    
    def stop_realtime_monitoring(self):
        """停止实时性能监控"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5.0)
        print("[成功] 实时性能监控已停止")
    
    def reset_statistics(self):
        """重置性能统计"""
        self.performance_history.clear()
        self.inference_times.clear()
        self.total_inferences = 0
        self.total_inference_time = 0.0
        print("[成功] 性能统计已重置")


# 使用示例
if __name__ == "__main__":
    # 创建性能监控器（假设AI绑定到核心1,2,3）
    monitor = YOLOv5PerformanceMonitor(ai_core_affinity=[1, 2, 3])
    
    # 模拟记录一些推理数据
    for i in range(10):
        inference_time = 100 + i * 5  # 模拟推理时间从100ms到145ms
        monitor.record_inference(inference_time)
        time.sleep(0.1)
    
    # 获取性能摘要
    summary = monitor.get_performance_summary()
    print("性能摘要:", summary)
    
    # 启动实时监控
    monitor.start_realtime_monitoring(interval=3.0)
    
    # 运行一段时间后停止
    time.sleep(10)
    monitor.stop_realtime_monitoring()