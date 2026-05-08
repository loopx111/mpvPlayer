"""
摄像头模块 - AI增强的摄像头采集和预处理

基于现有CameraController进行扩展，
添加AI分析功能和核心绑定优化。
"""

from .embedded_mediapipe_controller import (
    EmbeddedMediaPipeCameraWidget,
    EmbeddedMediaPipeCameraThread,
    EmbeddedMediaPipeCameraController
)

__all__ = [
    'EmbeddedMediaPipeCameraWidget',
    'EmbeddedMediaPipeCameraThread',
    'EmbeddedMediaPipeCameraController'
]
