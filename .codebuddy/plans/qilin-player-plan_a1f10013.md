---
name: qilin-player-plan
overview: 在麒麟系统上构建 Python+mpv 广告屏播放器，新增桌面窗口控制界面，沿用 ohosPlayer MQTT/文件分发协议
design:
  architecture:
    framework: react
    component: tdesign
  styleKeywords:
    - 深色科技
    - 卡片化
    - 渐变高光
    - 状态可视化
    - 动效反馈
  fontSystem:
    fontFamily: Poppins
    heading:
      size: 28px
      weight: 600
    subheading:
      size: 18px
      weight: 500
    body:
      size: 15px
      weight: 400
  colorSystem:
    primary:
      - "#6C63FF"
      - "#5ED0FF"
    background:
      - "#0F1424"
      - "#131A2E"
    text:
      - "#E8ECF7"
      - "#A9B4CC"
    functional:
      - "#3DCC91"
      - "#FFB347"
      - "#F76C6C"
todos:
  - id: scan-repo
    content: 使用 [subagent:code-explorer] 盘点现有 mpvPlayer 仓库结构与可复用模块
    status: completed
  - id: mqtt-plan
    content: 梳理 MQTT 主题/命令与 ohosPlayer 对齐的指令映射方案
    status: completed
    dependencies:
      - scan-repo
  - id: file-dist-spec
    content: 定义文件分发流程：下载、校验、解压、落盘与回执策略
    status: completed
    dependencies:
      - scan-repo
  - id: player-scheduler
    content: 设计 mpv 播放调度：队列、预加载、异常重启与音量控制
    status: completed
    dependencies:
      - mqtt-plan
      - file-dist-spec
  - id: desktop-ui
    content: 规划桌面控制界面信息架构：导航、播放列表、状态/进度、连接指示与快捷控制
    status: completed
    dependencies:
      - player-scheduler
  - id: config-logging
    content: 确定配置管理与日志策略：MQTT 参数、本地路径、自启动与滚动日志
    status: completed
    dependencies:
      - desktop-ui
---

## 产品概述

在麒麟系统上基于 Python 与 mpv 构建广告屏播放器，保持与 ohosPlayer 相同的 MQTT 主题/命令与文件分发协议，并提供本地桌面窗口控制界面。

## 核心特性

- MQTT 指令监听与解析，覆盖播放控制、状态上报、文件分发同步
- mpv 播放核心：支持循环播放、预加载、异常重启、音量/静音控制
- 本地媒体库管理：文件分发落盘、校验、任务进度与错误重试
- 桌面控制界面：播放列表管理、播放状态与系统资源监测、网络/MQTT 连接状态可视化
- 配置管理：MQTT 连接参数、本地缓存路径、日志与自启动开关可视化配置

## 技术选型

- 语言/运行时：Python
- 播放引擎：mpv（通过 Python 绑定）
- 桌面端：跨平台 UI 框架（含窗口、表格、图表、托盘图标）
- 通信：MQTT 客户端，文件分发复用 ohosPlayer 协议
- 存储：本地文件系统 + 配置/状态文件（JSON/YAML/SQLite）
- 日志与监控：本地滚动日志，异常自动恢复

## 系统架构

- 分层结构：接口层（MQTT/文件分发、本地 UI）、业务层（播放调度、任务管理、配置管理）、基础层（mpv 适配、存储、日志）

```mermaid
graph LR
  UI[桌面控制界面] -->|操作| Ctrl[播放/配置服务]
  MQTT[MQTT 客户端] -->|指令| Ctrl
  FileSrv[文件分发] -->|媒资/校验| Media[媒体库管理]
  Ctrl --> MPV[mpv 播放适配]
  Media --> MPV
  Ctrl --> Config[配置与状态存储]
  UI --> Config
  Ctrl --> Log[日志监控]
```

## 模块划分

- MQTT/指令模块：连接、重连、主题/命令对齐 ohosPlayer，状态上报
- 文件分发模块：下载、校验、解压、落盘与回执
- 播放调度模块：mpv 适配、播放队列、异常重启、音量/静音
- 配置与存储模块：MQTT 参数、路径、日志级别、自启动；状态与缓存
- 桌面 UI 模块：播放列表、状态监控、任务进度、连接/资源可视化、托盘控制
- 日志与监控模块：本地滚动日志、错误告警钩子

## 数据流

```mermaid
flowchart LR
  MQTTIn[MQTT 指令] --> Parse[指令解析]
  Parse --> Queue[播放/任务队列]
  FileDist[文件分发] --> Verify[校验/解压] --> Library[媒体库]
  Queue --> Player[mpv 适配]
  Library --> Player
  Player --> Status[状态采集]
  Status --> MQTTOut[MQTT 上报]
  UI[桌面 UI 操作] --> Queue
  UI --> Config[配置存储]
  Config --> MQTTIn
```

## 目录结构（新增/主要）

```
project-root/
├── src/
│   ├── mqtt/             # MQTT 连接与指令解析
│   ├── file_dist/        # 文件分发与校验
│   ├── player/           # mpv 适配与播放调度
│   ├── ui/               # 桌面窗口与控件
│   ├── config/           # 配置加载/保存
│   └── utils/            # 日志、校验、重试
```

## 关键结构

- 播放任务：{id, uri/path, duration, checksum, priority, expireAt, volume}
- MQTT 命令：{topic, cmd, payload}，映射到播放/下载/配置操作
- 状态上报：{playerState, currentMedia, progress, volume, netStatus, errors}

### 设计思路

桌面控制界面采用深色科技风，分为侧边导航与主工作区；使用卡片化布局呈现播放列表、状态监控与任务进度，顶部提供全局连接状态与快捷控制，底部固定托盘操作区，交互含悬停高亮与进度动画。

## 可用扩展

- **code-explorer (SubAgent)**
- Purpose: 全局检索现有仓库结构与关键代码，快速定位复用点
- Expected outcome: 生成项目结构与可复用文件的清单，指导后续开发