"""
性能优化器

针对飞腾E2000 4核处理器的性能优化工具，
包括内存管理、推理优化、资源监控等功能。
"""

import time
import psutil
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from ..ai.core_binding import CoreBindingManager, create_4core_optimized_config


@dataclass
class PerformanceMetrics:
    """性能指标数据结构"""
    cpu_usage: Dict[int, float] = None           # 各核心CPU使用率
    memory_usage: float = 0.0                    # 内存使用率(百分比)
    inference_fps: float = 0.0                   # 推理帧率
    inference_time: float = 0.0                  # 平均推理时间(ms)
    detection_count: int = 0                     # 检测人数
    timestamp: float = 0.0                       # 时间戳
    
    def __post_init__(self):
        if self.cpu_usage is None:
            self.cpu_usage = {}
        if self.timestamp == 0:
            self.timestamp = time.time()


class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self, core_manager: Optional[CoreBindingManager] = None):
        """
        初始化性能优化器
        
        Args:
            core_manager: 核心绑定管理器，如果为None则自动创建
        """
        self.core_manager = core_manager or CoreBindingManager(create_4core_optimized_config())
        self.metrics_history: List[PerformanceMetrics] = []
        self.max_history_size = 100  # 最大历史记录数
        self.optimization_enabled = True
        
        # 性能阈值配置
        self.cpu_threshold_high = 80.0  # CPU使用率过高阈值
        self.cpu_threshold_low = 20.0   # CPU使用率过低阈值
        self.memory_threshold = 85.0    # 内存使用率阈值
        
        # 启动性能监控
        self.monitoring_thread = None
        self.monitoring_active = False
        
        print("✓ 性能优化器初始化完成")
    
    def start_monitoring(self, interval: float = 2.0):
        """启动性能监控"""
        if self.monitoring_active:
            print("⚠️ 性能监控已在运行")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval,),
            daemon=True
        )
        self.monitoring_thread.start()
        print(f"✓ 性能监控已启动，间隔: {interval}秒")
    
    def stop_monitoring(self):
        """停止性能监控"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5.0)
        print("✓ 性能监控已停止")
    
    def _monitoring_loop(self, interval: float):
        """性能监控循环"""
        while self.monitoring_active:
            try:
                metrics = self.collect_metrics()
                self.metrics_history.append(metrics)
                
                # 限制历史记录大小
                if len(self.metrics_history) > self.max_history_size:
                    self.metrics_history.pop(0)
                
                # 性能分析
                if self.optimization_enabled:
                    self._analyze_performance()
                
                time.sleep(interval)
                
            except Exception as e:
                print(f"性能监控错误: {e}")
                time.sleep(interval)
    
    def collect_metrics(self) -> PerformanceMetrics:
        """收集性能指标"""
        cpu_usage = self.core_manager.get_cpu_usage()
        
        # 计算平均CPU使用率
        avg_cpu_usage = {}
        for core, info in cpu_usage.items():
            avg_cpu_usage[core] = info['usage_percent']
        
        # 获取内存使用率
        memory_info = psutil.virtual_memory()
        memory_usage = memory_info.percent
        
        return PerformanceMetrics(
            cpu_usage=avg_cpu_usage,
            memory_usage=memory_usage,
            inference_fps=self._calculate_fps(),
            inference_time=self._calculate_avg_inference_time(),
            detection_count=self._get_detection_count(),
            timestamp=time.time()
        )
    
    def _calculate_fps(self) -> float:
        """计算推理帧率"""
        if len(self.metrics_history) < 2:
            return 0.0
        
        # 基于最近几次的时间间隔计算帧率
        recent_metrics = self.metrics_history[-5:]
        if len(recent_metrics) < 2:
            return 0.0
        
        time_diffs = [recent_metrics[i+1].timestamp - recent_metrics[i].timestamp 
                     for i in range(len(recent_metrics)-1)]
        
        if len(time_diffs) > 0:
            avg_interval = sum(time_diffs) / len(time_diffs)
            return 1.0 / avg_interval if avg_interval > 0 else 0.0
        
        return 0.0
    
    def _calculate_avg_inference_time(self) -> float:
        """计算平均推理时间"""
        # 这里可以从YOLOv5检测器获取实际推理时间
        # 暂时返回默认值，实际使用时应从检测器获取
        return 0.0
    
    def _get_detection_count(self) -> int:
        """获取检测人数"""
        # 这里可以从人数统计器获取当前人数
        # 暂时返回默认值，实际使用时应从统计器获取
        return 0
    
    def _analyze_performance(self):
        """分析性能并生成优化建议"""
        if len(self.metrics_history) < 5:
            return  # 数据不足
        
        current_metrics = self.metrics_history[-1]
        
        # 检查CPU负载
        overloaded_cores = []
        underutilized_cores = []
        
        for core, usage in current_metrics.cpu_usage.items():
            if usage > self.cpu_threshold_high:
                overloaded_cores.append(core)
            elif usage < self.cpu_threshold_low:
                underutilized_cores.append(core)
        
        # 检查内存使用
        memory_warning = current_metrics.memory_usage > self.memory_threshold
        
        # 生成优化建议
        suggestions = []
        
        if overloaded_cores:
            suggestions.append({
                'type': 'cpu_overload',
                'cores': overloaded_cores,
                'message': f"核心 {overloaded_cores} 负载过高 ({current_metrics.cpu_usage[overloaded_cores[0]]:.1f}%)",
                'suggested_actions': [
                    "考虑降低推理帧率",
                    "优化检测算法",
                    "检查是否有资源泄漏"
                ]
            })
        
        if underutilized_cores:
            suggestions.append({
                'type': 'cpu_underutilized',
                'cores': underutilized_cores,
                'message': f"核心 {underutilized_cores} 利用率不足",
                'suggested_actions': [
                    "可以考虑增加并行处理任务",
                    "优化任务调度策略"
                ]
            })
        
        if memory_warning:
            suggestions.append({
                'type': 'memory_warning',
                'message': f"内存使用率过高: {current_metrics.memory_usage:.1f}%",
                'suggested_actions': [
                    "检查内存泄漏",
                    "优化内存使用",
                    "考虑增加系统内存"
                ]
            })
        
        if suggestions:
            print("=== 性能优化建议 ===")
            for suggestion in suggestions:
                print(f"• {suggestion['message']}")
                for action in suggestion['suggested_actions']:
                    print(f"  - {action}")
    
    def get_performance_summary(self) -> Dict:
        """获取性能摘要"""
        if not self.metrics_history:
            return {"error": "没有性能数据"}
        
        current = self.metrics_history[-1]
        
        # 计算平均CPU使用率
        avg_cpu = sum(current.cpu_usage.values()) / len(current.cpu_usage) if current.cpu_usage else 0
        
        return {
            "timestamp": current.timestamp,
            "cpu_usage_avg": round(avg_cpu, 1),
            "cpu_usage_by_core": {core: round(usage, 1) for core, usage in current.cpu_usage.items()},
            "memory_usage": round(current.memory_usage, 1),
            "inference_fps": round(current.inference_fps, 1),
            "detection_count": current.detection_count,
            "optimization_enabled": self.optimization_enabled
        }
    
    def optimize_inference_settings(self, detector_obj) -> Dict:
        """优化推理设置"""
        if not self.metrics_history:
            return {"error": "没有性能数据"}
        
        current = self.metrics_history[-1]
        
        # 根据CPU负载调整置信度阈值
        avg_cpu = sum(current.cpu_usage.values()) / len(current.cpu_usage)
        
        optimization = {
            "original_conf_threshold": getattr(detector_obj, 'conf_threshold', 0.5),
            "optimized_conf_threshold": None,
            "reason": ""
        }
        
        if avg_cpu > 70:  # CPU负载高
            # 提高置信度阈值，减少检测数量
            new_threshold = min(0.7, getattr(detector_obj, 'conf_threshold', 0.5) + 0.1)
            optimization["optimized_conf_threshold"] = new_threshold
            optimization["reason"] = "高CPU负载，提高置信度阈值减少计算量"
        elif avg_cpu < 30:  # CPU负载低
            # 降低置信度阈值，增加检测灵敏度
            new_threshold = max(0.3, getattr(detector_obj, 'conf_threshold', 0.5) - 0.1)
            optimization["optimized_conf_threshold"] = new_threshold
            optimization["reason"] = "低CPU负载，降低置信度阈值提高检测灵敏度"
        else:
            optimization["reason"] = "CPU负载适中，保持当前设置"
        
        return optimization
    
    def enable_optimization(self):
        """启用性能优化"""
        self.optimization_enabled = True
        print("✓ 性能优化已启用")
    
    def disable_optimization(self):
        """禁用性能优化"""
        self.optimization_enabled = False
        print("⚠️ 性能优化已禁用")


def create_optimization_preset(preset_name: str) -> Dict:
    """创建性能优化预设"""
    presets = {
        "high_accuracy": {
            "conf_threshold": 0.3,
            "cpu_priority": "balanced",
            "frame_skip": 0,
            "description": "高精度模式，检测更准确但计算量更大"
        },
        "balanced": {
            "conf_threshold": 0.5,
            "cpu_priority": "balanced", 
            "frame_skip": 1,
            "description": "平衡模式，兼顾精度和性能"
        },
        "high_performance": {
            "conf_threshold": 0.7,
            "cpu_priority": "performance",
            "frame_skip": 2,
            "description": "高性能模式，优先保证流畅度"
        }
    }
    
    return presets.get(preset_name, presets["balanced"])


# 测试代码
if __name__ == "__main__":
    # 创建性能优化器
    optimizer = PerformanceOptimizer()
    
    # 启动性能监控
    optimizer.start_monitoring(interval=2.0)
    
    # 模拟运行一段时间
    print("性能监控运行中，按Ctrl+C停止...")
    try:
        for i in range(10):
            summary = optimizer.get_performance_summary()
            print(f"第{i+1}次性能摘要: {summary}")
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    
    # 停止监控
    optimizer.stop_monitoring()
    
    # 显示预设配置
    print("\n性能优化预设:")
    for preset_name in ["high_accuracy", "balanced", "high_performance"]:
        preset = create_optimization_preset(preset_name)
        print(f"{preset_name}: {preset['description']}")