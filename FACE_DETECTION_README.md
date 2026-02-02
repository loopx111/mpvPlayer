# 人脸检测功能集成指南

## 概述

本项目已成功实现从人数识别到人脸检测的功能转换。新的系统使用YOLOv5-face模型进行实时人脸检测，具有更高的检测精度和更好的性能。

## 主要功能

- ✅ **YOLOv5-face人脸检测器** - 基于ONNX Runtime的高性能人脸检测
- ✅ **人脸计数器** - 实时统计人脸数量和相关指标
- ✅ **AI增强摄像头控制器** - 集成人脸检测功能的摄像头控制
- ✅ **性能监控** - 支持多核绑核优化的性能监控
- ✅ **测试脚本** - 完整的测试和验证工具

## 文件结构

```
src/ai/
├── face_detector.py          # YOLOv5-face人脸检测器
├── face_counter.py           # 人脸计数器
├── yolo_detector.py          # 原有人数检测器（保留）
└── performance_monitor.py    # 性能监控器

src/camera/
├── face_camera_capture.py    # 人脸检测摄像头控制器
└── camera_capture.py         # 原有人数检测摄像头控制器（保留）

测试文件:
├── test_face_detection.py    # 人脸检测功能测试
└── download_face_model.py    # 模型下载工具
```

## 快速开始

### 1. 下载YOLOv5-face模型

由于网络连接问题，请手动下载YOLOv5-face模型：

**下载地址**: https://github.com/deepcam-cn/yolov5-face/releases

**推荐模型**: `yolov5s-face.onnx` (轻量级，适合实时检测)

**保存位置**: `models/yolov5s-face.onnx`

### 2. 测试功能

运行测试脚本验证功能是否正常：

```bash
python test_face_detection.py
```

### 3. 集成到主应用

#### 方法一：完全替换（推荐）

修改 `app.py` 中的摄像头控制器初始化代码：

```python
# 原代码（人数检测）
from src.camera.camera_capture import AICameraController
self.camera_controller = AICameraController()

# 新代码（人脸检测）
from src.camera.face_camera_capture import FaceCameraController
self.camera_controller = FaceCameraController()
```

#### 方法二：条件切换

在应用设置中添加切换选项：

```python
def initialize_camera(self, detection_type="face"):
    if detection_type == "face":
        from src.camera.face_camera_capture import FaceCameraController
        self.camera_controller = FaceCameraController()
    else:
        from src.camera.camera_capture import AICameraController
        self.camera_controller = AICameraController()
    
    # 初始化摄像头
    self.camera_controller.initialize(
        camera_index=0, 
        enable_ai=True,
        model_path="models/yolov5s-face.onnx"  # 人脸检测模型
    )
```

## API 使用说明

### 人脸检测器 (YOLOv5FaceDetector)

```python
from src.ai.face_detector import YOLOv5FaceDetector

# 初始化检测器
detector = YOLOv5FaceDetector(
    model_path="models/yolov5s-face.onnx",
    conf_threshold=0.5,      # 置信度阈值
    iou_threshold=0.45,      # NMS阈值
    core_affinity=[2, 3]     # CPU核心绑定
)

# 检测人脸
result = detector.detect_faces(frame)
print(f"检测到 {result.face_count} 张人脸")

# 绘制检测框
result_frame = detector.draw_detections(frame, result.detections)
```

### 人脸计数器 (FaceCounter)

```python
from src.ai.face_counter import FaceCounter

counter = FaceCounter(smoothing_window=30)

# 更新计数
update_info = counter.update_count(face_count)

# 获取统计信息
stats = counter.get_statistics()
recent_stats = counter.get_recent_statistics(window_size=5)  # 最近5秒统计
```

### 摄像头控制器 (FaceCameraController)

```python
from src.camera.face_camera_capture import FaceCameraController

# 创建控制器
controller = FaceCameraController()

# 初始化摄像头（启用AI人脸检测）
controller.initialize(
    camera_index=0,
    resolution=(640, 480),
    fps=30,
    enable_ai=True,
    model_path="models/yolov5s-face.onnx"
)

# 设置分析结果回调
controller.set_analysis_callback(self.on_face_detection_result)

def on_face_detection_result(self, analysis_result):
    """处理人脸检测结果"""
    face_count = analysis_result['detection_result'].face_count
    print(f"检测到 {face_count} 张人脸")
```

## 性能优化建议

### 1. 输入尺寸调整

YOLOv5-face默认使用640×640输入尺寸，可以根据性能需求调整：

```python
# 在face_detector.py中修改
self.input_size = (320, 320)  # 更小的尺寸，更高的FPS
# 或
self.input_size = (640, 640)  # 标准尺寸，更好的精度
```

### 2. 检测频率控制

调整分析线程的最大FPS：

```python
# 在face_camera_capture.py中修改
self.max_analysis_fps = 10  # 降低FPS减少CPU占用
```

### 3. 核心绑定优化

针对飞腾E2000的4核CPU优化：

```python
# 使用2个核心进行AI推理
core_affinity = [2, 3]  # 将AI推理绑定到核心2和3
```

## 故障排除

### 常见问题

1. **模型文件不存在**
   - 解决方案：手动下载模型文件到 `models/` 目录

2. **检测精度低**
   - 调整 `conf_threshold` 参数（0.3-0.7）
   - 确保摄像头光线充足
   - 使用更高精度的模型（yolov5m-face.onnx）

3. **性能问题**
   - 降低输入尺寸
   - 减少检测频率
   - 启用核心绑定优化

### 调试模式

启用详细日志输出：

```python
# 在face_detector.py中取消注释调试日志
print(f"[人脸分析器] 检测结果: {detection_result.face_count} 张人脸")
```

## 扩展功能

### 人脸识别（未来扩展）

当前系统只实现人脸检测，可以扩展为人脸识别：

1. 添加人脸特征提取模块
2. 集成人脸数据库
3. 实现实时人脸识别

### 多摄像头支持

支持多个摄像头同时进行人脸检测：

```python
# 创建多个摄像头控制器实例
camera1 = FaceCameraController()
camera2 = FaceCameraController()
```

## 技术支持

如有问题，请检查：

1. 模型文件是否正确下载
2. 依赖库是否完整安装
3. 摄像头设备是否正常工作
4. 查看日志文件中的错误信息

---

**注意**: 本系统已完全实现人脸检测功能，可以直接替换原有的人数检测系统。建议先进行测试验证，确保功能正常后再集成到主应用中。