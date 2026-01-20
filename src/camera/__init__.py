"""
摄像头模块 - AI增强的摄像头采集和预处理

基于现有CameraController进行扩展，
添加AI分析功能和核心绑定优化。
"""

from .camera_capture import AICameraController, VideoAnalyzer

__all__ = [
    'AICameraController',
    'VideoAnalyzer'
]