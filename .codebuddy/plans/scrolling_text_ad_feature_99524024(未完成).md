---
name: scrolling_text_ad_feature
overview: 在MPV播放器中实现滚动文字广告功能，支持屏幕旋转90度时的特殊显示需求
todos:
  - id: create-ad-config-model
    content: 创建广告配置数据模型，支持文字内容、字体、颜色、速度等参数
    status: in_progress
  - id: develop-scrolling-text-component
    content: 开发滚动文字广告核心组件，实现文字渲染和动画控制
    status: pending
    dependencies:
      - create-ad-config-model
  - id: implement-rotation-adaptation
    content: 实现屏幕旋转90度适配功能，支持开发模式与生产模式切换
    status: pending
    dependencies:
      - develop-scrolling-text-component
  - id: integrate-with-main-window
    content: 将滚动文字广告功能集成到主窗口UI中
    status: pending
    dependencies:
      - implement-rotation-adaptation
  - id: add-ad-control-interface
    content: 添加广告控制界面，支持动态配置和开关控制
    status: pending
    dependencies:
      - integrate-with-main-window
  - id: test-rotation-display
    content: 测试屏幕旋转90度时的文字显示效果
    status: pending
    dependencies:
      - add-ad-control-interface
  - id: optimize-performance
    content: 优化性能，确保文字叠加不影响视频播放流畅度
    status: pending
    dependencies:
      - test-rotation-display
---

## 产品概述

在MPV播放器中实现滚动文字广告功能，支持屏幕旋转90度时的特殊显示需求

## 核心功能

- 滚动文字广告显示：支持在视频播放时叠加显示滚动文字广告
- 屏幕旋转适配：屏幕实际逆时针旋转90度放置时，文字从右向左滚动显示
- 开发调试模式：开发时文字从屏幕画面最右侧从下往上滚动显示，便于调试
- 广告内容管理：支持动态更新广告文字内容、字体、颜色、滚动速度等参数
- 叠加显示控制：可以控制广告文字是否显示，以及显示位置的调整

## 技术栈

- 前端框架：PySide6 (Qt for Python)
- 图形渲染：OpenGL或Qt Graphics View框架
- 文字渲染：Qt文本渲染引擎
- 动画处理：Qt动画框架

## 技术架构

### 系统架构

```mermaid
graph LR
    A[滚动文字广告模块] --> B[MPV播放器主窗口]
    B --> C[视频渲染层]
    A --> D[文字叠加渲染层]
    D --> E[旋转变换处理]
    E --> F[最终显示输出]
```

### 模块划分

- **广告管理器模块**：负责广告内容管理、显示参数配置
- **文字渲染模块**：处理文字渲染、字体样式、颜色设置
- **动画控制器模块**：控制滚动动画效果和速度
- **旋转适配模块**：处理屏幕旋转90度时的显示适配

### 数据流

用户配置广告内容 → 广告管理器解析参数 → 文字渲染模块生成文字图像 → 动画控制器应用滚动效果 → 旋转适配模块处理屏幕旋转 → 叠加到视频画面显示

## 实现细节

### 核心目录结构

```
d:/code/mpvPlayer/
├── src/
│   ├── ui/
│   │   ├── main_window.py              # 修改主窗口以集成广告功能
│   │   └── scrolling_text_ad.py        # 新增：滚动文字广告组件
│   ├── player/
│   │   └── mpv_controller.py           # 修改：支持文字叠加显示
│   └── config/
│       └── models.py                   # 新增：广告配置模型
```

### 关键技术实现

1. **文字叠加技术**：使用Qt的QPainter在视频画面上叠加渲染文字
2. **动画控制**：使用QPropertyAnimation控制文字位置变化
3. **旋转适配**：通过坐标变换矩阵实现屏幕旋转90度的适配
4. **性能优化**：使用双缓冲技术避免闪烁，优化文字渲染性能

### 技术难点解决

- **文字平滑滚动**：使用线性插值动画确保滚动流畅
- **旋转显示适配**：通过坐标变换实现开发模式与生产模式的统一
- **资源管理**：动态加载字体资源，支持多语言文字显示