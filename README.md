# MPV Player - 广告屏视频播放器

一个基于MPV播放器的广告屏视频播放应用，支持远程控制、文件分发和自动播放功能。

## 🎯 项目简介

MPV Player是一个专为广告屏设计的视频播放应用，具有以下特性：
- 🎬 基于MPV的高性能视频播放
- 🌐 MQTT远程控制支持
- 📁 自动文件下载和分发
- 🖥️ 图形化控制界面（PySide6）
- 🔄 自动循环播放
- 🐧 麒麟系统兼容

## 📋 系统要求

### 操作系统
- **麒麟系统** (Kylin V10+)
- **Windows 10/11** (开发测试)

### 软件依赖
- Python 3.8+
- MPV播放器
- X11显示系统（麒麟系统）

## 🚀 快速开始

### 麒麟系统安装

#### 方式一：开发环境（推荐）
```bash
# 1. 安装依赖
./install_kylin_deps_v2.sh

# 2. 启动应用
./start_kylin.sh
```

#### 方式二：生产环境
```bash
# 安装到系统目录
sudo ./install_kylin.sh
# 然后从桌面快捷方式启动
```

### Windows系统
```bash
# 1. 设置虚拟环境
setup_venv.bat

# 2. 启动应用
start_windows.bat
```

## 📁 项目结构

```
mpvPlayer/
├── src/                    # 源代码
│   ├── app.py             # 主应用入口
│   ├── comm/              # 通信模块（MQTT）
│   ├── config/            # 配置管理
│   ├── file_dist/         # 文件分发
│   ├── player/            # 播放器控制
│   ├── ui/                # 用户界面
│   └── utils/             # 工具类
├── data/                  # 数据目录
│   ├── config.json        # 主配置文件
│   ├── config_kylin.json  # 麒麟系统配置
│   └── logs/              # 日志文件
├── scripts/               # 启动脚本
├── requirements.txt       # Python依赖
└── README.md             # 本文档
```

## ⚙️ 配置说明

### 主要配置文件
- `data/config.json` - 通用配置
- `data/config_kylin.json` - 麒麟系统专用配置

### 配置项说明
```json
{
  "mqtt": {
    "host": "127.0.0.1",      # MQTT服务器地址
    "port": 1883,             # MQTT端口
    "enabled": true           # 是否启用MQTT
  },
  "player": {
    "autoPlay": true,         # 自动播放
    "loop": true,             # 循环播放
    "volume": 70              # 音量设置
  }
}
```

## 🎮 使用说明

### 基本操作
1. **启动应用**：运行对应系统的启动脚本
2. **控制界面**：应用启动后会显示控制台界面
3. **视频播放**：支持MP4、AVI等常见视频格式
4. **远程控制**：通过MQTT协议发送控制指令

### 视频文件管理
- 默认视频目录：`/opt/mpvPlayer/data/videos/`
- 支持自动检测新文件
- 可配置播放顺序和循环模式

### 远程控制指令
通过MQTT发送JSON指令控制播放器：
```json
{
  "command": "play",
  "file": "video.mp4"
}
```

## 🔧 故障排除

### 常见问题

#### 1. UI界面不显示
**问题**：视频播放正常，但控制台界面不显示
**解决**：确保在图形界面环境中运行，脚本已设置正确的显示环境变量

#### 2. MPV播放器无法启动
**解决**：检查MPV是否安装：`sudo apt install mpv`

#### 3. 依赖安装失败
**解决**：使用增强版安装脚本：`./install_kylin_deps_v2.sh`

### 日志查看
应用日志位于：`data/logs/mpvPlayer.log`

## 📞 技术支持

- 查看详细文档：`docs/` 目录
- 查看脚本说明：`scripts/README.md`
- 问题反馈：检查日志文件获取详细信息

## 📄 许可证

本项目仅供内部使用。