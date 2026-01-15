# 脚本说明文档

本目录包含MPV Player的各种启动和安装脚本。

## 📜 脚本列表

### 麒麟系统脚本

| 脚本名称 | 用途 | 使用场景 |
|---------|------|----------|
| `install_kylin.sh` | **生产环境安装** | 将应用安装到系统目录，创建桌面快捷方式 |
| `install_kylin_deps.sh` | **开发环境依赖安装** | 在当前目录安装依赖包 |
| `install_kylin_deps_v2.sh` | **开发环境依赖安装（增强版）** | 包含问题修复，推荐使用 |
| `start_kylin.sh` | **日常启动脚本** | 自动处理环境变量，推荐日常使用 |

### Windows系统脚本

| 脚本名称 | 用途 |
|---------|------|
| `setup_venv.bat` | 设置Python虚拟环境 |
| `start_windows.bat` | 启动Windows版本应用 |

## 🎯 推荐使用流程

### 麒麟系统 - 开发测试
```bash
# 1. 安装依赖（只需一次）
./install_kylin_deps_v2.sh

# 2. 启动应用（每次使用）
./start_kylin.sh
```

### 麒麟系统 - 生产部署
```bash
# 安装到系统目录
sudo ./install_kylin.sh
# 然后从桌面快捷方式启动
```

### Windows系统
```bash
# 1. 设置环境
setup_venv.bat

# 2. 启动应用
start_windows.bat
```

## 🔧 脚本详细说明

### install_kylin_deps_v2.sh（推荐）
**功能**：
- 安装系统依赖（Python3、pip、mpv等）
- 创建Python虚拟环境
- 安装Python包依赖
- 修复已知问题：
  - Path导入问题
  - 无头模式检测逻辑

**使用场景**：开发测试环境

### install_kylin.sh
**功能**：
- 将应用安装到 `/opt/mpvPlayer` 目录
- 创建桌面快捷方式
- 设置系统级启动脚本

**使用场景**：生产环境部署

### start_kylin.sh
**功能**：
- 自动检测虚拟环境
- 设置X11显示环境变量
- 使用麒麟系统专用配置
- 启动图形界面应用

**特殊配置**：
- 第112行：`export QT_QPA_PLATFORM=xcb` - 强制使用X11后端
- 第101行：`export DISPLAY=${DISPLAY:-:0}` - 设置显示设备

## ⚠️ 注意事项

1. **权限问题**：生产环境安装需要sudo权限
2. **显示环境**：确保在图形界面中运行脚本
3. **依赖冲突**：如果遇到问题，使用v2版本的安装脚本
4. **日志查看**：启动问题可查看 `data/logs/mpvPlayer.log`

## 🔄 更新和维护

- 添加新依赖时，更新 `requirements.txt`
- 修改配置时，同步更新各环境的配置文件
- 脚本更新后，确保向后兼容性