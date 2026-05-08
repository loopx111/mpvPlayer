"""
AI模块配置管理

管理YOLOv5检测、人数统计、性能优化等AI相关配置。
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class YOLOv5Config:
    """YOLOv5模型配置"""
    model_path: str = "models/yolov5s.onnx"
    conf_threshold: float = 0.5
    iou_threshold: float = 0.45
    input_size: tuple = (640, 640)
    enable_nms: bool = True
    min_detection_area: int = 100
    core_affinity: list = None
    
    def __post_init__(self):
        if self.core_affinity is None:
            self.core_affinity = [3]  # 默认绑定到核心3


@dataclass 
class PeopleCounterConfig:
    """人数统计配置"""
    history_size: int = 30
    trend_threshold: float = 0.1
    stability_threshold: int = 5
    enable_trend_analysis: bool = True
    enable_performance_stats: bool = True


@dataclass
class CameraAIConfig:
    """摄像头AI配置"""
    enable_ai: bool = True
    detection_interval: int = 0  # 检测间隔（帧数）
    display_detections: bool = True
    display_stats: bool = True
    confidence_display: bool = True
    enable_auto_optimization: bool = True


@dataclass
class PerformanceConfig:
    """性能配置"""
    cpu_threshold_high: float = 80.0
    cpu_threshold_low: float = 20.0
    memory_threshold: float = 85.0
    optimization_preset: str = "balanced"  # high_accuracy, balanced, high_performance
    enable_realtime_monitoring: bool = True
    monitoring_interval: float = 2.0
    enable_auto_adjust: bool = True


@dataclass
class CoreBindingConfig:
    """核心绑定配置"""
    system_cores: list = None
    camera_cores: list = None
    mpv_cores: list = None
    ai_cores: list = None
    enable_binding: bool = True
    
    def __post_init__(self):
        if self.system_cores is None:
            self.system_cores = [0]
        if self.camera_cores is None:
            self.camera_cores = [1]
        if self.mpv_cores is None:
            self.mpv_cores = [2]
        if self.ai_cores is None:
            self.ai_cores = [3]


@dataclass
class AIConfig:
    """AI模块总配置"""
    yolo_config: YOLOv5Config = None
    counter_config: PeopleCounterConfig = None
    camera_config: CameraAIConfig = None
    performance_config: PerformanceConfig = None
    core_config: CoreBindingConfig = None
    
    def __post_init__(self):
        if self.yolo_config is None:
            self.yolo_config = YOLOv5Config()
        if self.counter_config is None:
            self.counter_config = PeopleCounterConfig()
        if self.camera_config is None:
            self.camera_config = CameraAIConfig()
        if self.performance_config is None:
            self.performance_config = PerformanceConfig()
        if self.core_config is None:
            self.core_config = CoreBindingConfig()


class AIConfigManager:
    """AI配置管理器"""
    
    def __init__(self, config_file: str = "data/ai_config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = AIConfig()
        
        # 确保配置目录存在
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        # 加载配置
        self.load_config()
    
    def load_config(self) -> bool:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_dict = json.load(f)
                
                # 递归构建配置对象
                self.config = self._dict_to_config(config_dict, AIConfig)
                print(f"✓ AI配置加载成功: {self.config_file}")
                return True
            else:
                # 配置文件不存在，创建默认配置
                print(f"⚠️ 配置文件不存在，使用默认配置: {self.config_file}")
                self.save_config()
                return True
                
        except Exception as e:
            print(f"✗ AI配置加载失败: {e}")
            return False
    
    def save_config(self) -> bool:
        """保存配置文件"""
        try:
            # 转换为字典
            config_dict = self._config_to_dict(self.config)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            print(f"✓ AI配置保存成功: {self.config_file}")
            return True
            
        except Exception as e:
            print(f"✗ AI配置保存失败: {e}")
            return False
    
    def _config_to_dict(self, config_obj) -> Dict[str, Any]:
        """配置对象转字典"""
        if hasattr(config_obj, '__dataclass_fields__'):
            result = {}
            for field_name in config_obj.__dataclass_fields__:
                field_value = getattr(config_obj, field_name)
                if hasattr(field_value, '__dataclass_fields__'):
                    result[field_name] = self._config_to_dict(field_value)
                else:
                    result[field_name] = field_value
            return result
        else:
            return config_obj
    
    def _dict_to_config(self, config_dict: Dict[str, Any], config_class) -> Any:
        """字典转配置对象"""
        if not hasattr(config_class, '__dataclass_fields__'):
            return config_dict
        
        # 获取字段信息
        fields = config_class.__dataclass_fields__
        
        # 构建参数字典
        kwargs = {}
        for field_name, field_info in fields.items():
            if field_name in config_dict:
                field_value = config_dict[field_name]
                
                # 如果是嵌套的dataclass
                if hasattr(field_info.type, '__dataclass_fields__'):
                    kwargs[field_name] = self._dict_to_config(field_value, field_info.type)
                else:
                    kwargs[field_name] = field_value
        
        return config_class(**kwargs)
    
    def update_config(self, config_updates: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            # 递归更新配置
            self._update_config_recursive(self.config, config_updates)
            
            # 保存更新后的配置
            return self.save_config()
            
        except Exception as e:
            print(f"✗ 配置更新失败: {e}")
            return False
    
    def _update_config_recursive(self, config_obj, updates: Dict[str, Any]):
        """递归更新配置"""
        for key, value in updates.items():
            if hasattr(config_obj, key):
                current_value = getattr(config_obj, key)
                
                if isinstance(value, dict) and hasattr(current_value, '__dataclass_fields__'):
                    # 嵌套更新
                    self._update_config_recursive(current_value, value)
                else:
                    # 直接设置值
                    setattr(config_obj, key, value)
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "yolo": {
                "model_path": self.config.yolo_config.model_path,
                "conf_threshold": self.config.yolo_config.conf_threshold,
                "core_affinity": self.config.yolo_config.core_affinity
            },
            "camera": {
                "enable_ai": self.config.camera_config.enable_ai,
                "detection_interval": self.config.camera_config.detection_interval
            },
            "performance": {
                "preset": self.config.performance_config.optimization_preset,
                "auto_optimization": self.config.performance_config.enable_auto_adjust
            },
            "core_binding": {
                "enabled": self.config.core_config.enable_binding,
                "ai_cores": self.config.core_config.ai_cores
            }
        }
    
    def reset_to_defaults(self) -> bool:
        """重置为默认配置"""
        try:
            self.config = AIConfig()
            return self.save_config()
        except Exception as e:
            print(f"✗ 重置配置失败: {e}")
            return False


# 预定义优化预设
PRESET_CONFIGS = {
    "high_accuracy": {
        "yolo_config": {
            "conf_threshold": 0.3
        },
        "performance_config": {
            "optimization_preset": "high_accuracy"
        }
    },
    "balanced": {
        "yolo_config": {
            "conf_threshold": 0.5
        },
        "performance_config": {
            "optimization_preset": "balanced"
        }
    },
    "high_performance": {
        "yolo_config": {
            "conf_threshold": 0.7
        },
        "performance_config": {
            "optimization_preset": "high_performance"
        }
    }
}


def create_default_config() -> AIConfig:
    """创建默认配置"""
    return AIConfig()


# 测试代码
if __name__ == "__main__":
    # 创建配置管理器
    config_manager = AIConfigManager()
    
    # 显示配置摘要
    summary = config_manager.get_config_summary()
    print("当前配置摘要:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    # 测试配置更新
    updates = {
        "yolo_config": {
            "conf_threshold": 0.6
        },
        "camera_config": {
            "detection_interval": 1
        }
    }
    
    if config_manager.update_config(updates):
        print("✓ 配置更新成功")
    
    # 应用高性能预设
    if config_manager.update_config(PRESET_CONFIGS["high_performance"]):
        print("✓ 高性能预设应用成功")
    
    # 显示更新后的配置
    updated_summary = config_manager.get_config_summary()
    print("\n更新后配置摘要:")
    print(json.dumps(updated_summary, indent=2, ensure_ascii=False))