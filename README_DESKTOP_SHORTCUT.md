# MPV Player 麒麟桌面快捷方式安装指南

## 概述
本指南帮助您在麒麟桌面创建一键启动的快捷方式，避免终端关闭导致程序退出的问题。

## 文件说明

### 1. 桌面启动脚本 (`start_kylin_desktop.sh`)
- 专门为桌面环境优化的启动脚本
- 使用 `nohup` 启动，避免终端关闭程序退出
- 自动设置显示环境变量
- 提供图形化的启动反馈

### 2. 桌面文件 (`mpvplayer.desktop`)
- 标准的Linux桌面应用程序描述文件
- 定义应用程序名称、图标、启动命令等
- 支持双击启动和系统菜单集成

### 3. 安装脚本 (`create_shortcut.sh`)
- 自动创建桌面快捷方式的安装脚本
- 处理图标生成和权限设置

## 安装步骤

### 方法一：使用安装脚本（推荐）

1. **给安装脚本执行权限**
   ```bash
   chmod +x create_shortcut.sh
   ```

2. **运行安装脚本**
   ```bash
   ./create_shortcut.sh
   ```

3. **按照提示操作**
   - 脚本会自动检测桌面目录位置
   - 创建默认图标（如需要）
   - 询问是否添加到系统菜单

### 方法二：手动安装

1. **确保启动脚本有执行权限**
   ```bash
   chmod +x start_kylin_desktop.sh
   ```

2. **复制桌面文件到桌面**
   ```bash
   # 麒麟系统通常使用中文桌面目录
   cp mpvplayer.desktop ~/桌面/
   chmod +x ~/桌面/mpvplayer.desktop
   
   # 或者英文桌面目录
   cp mpvplayer.desktop ~/Desktop/
   chmod +x ~/Desktop/mpvplayer.desktop
   ```

3. **（可选）添加到系统应用菜单**
   ```bash
   sudo cp mpvplayer.desktop /usr/share/applications/
   sudo chmod +x /usr/share/applications/mpvplayer.desktop
   ```

## 使用方法

### 启动程序
- **双击桌面图标**: 直接双击 "MPV Player" 图标
- **系统菜单**: 在应用菜单中找到 "MPV Player"

### 程序特性
- ✅ **后台运行**: 关闭启动窗口不会影响程序运行
- ✅ **图形反馈**: 启动时显示成功消息
- ✅ **日志记录**: 所有输出保存到 `data/logs/mpvPlayer_desktop.log`
- ✅ **错误处理**: 依赖检查失败时显示图形错误提示

### 停止程序
- **系统监视器**: 使用系统监视器结束进程
- **命令行**: `pkill -f 'python.*src.app'`
- **重启系统**: 程序不会自动重启

## 故障排除

### 问题1: 双击图标无反应
- 检查桌面文件权限: `chmod +x ~/桌面/mpvplayer.desktop`
- 检查启动脚本权限: `chmod +x start_kylin_desktop.sh`
- 查看日志: `tail -f data/logs/mpvPlayer_desktop.log`

### 问题2: 图标显示不正确
- 确保图标文件存在: `data/icon.png`
- 重新运行安装脚本生成图标

### 问题3: 依赖错误
- 运行依赖安装脚本: `./install_kylin_deps_v2.sh`
- 检查Python环境: `python3 -c "import PySide6"`

## 技术细节

### 启动机制
- 使用 `nohup` 命令启动，分离进程与终端
- 设置 `QT_QPA_PLATFORM=xcb` 确保图形界面正常显示
- 自动检测虚拟环境或系统Python

### 日志记录
- 所有控制台输出重定向到 `data/logs/mpvPlayer_desktop.log`
- 便于调试和问题排查

### 用户反馈
- 使用 `zenity` 显示图形化的启动成功消息
- 错误时显示图形错误对话框

## 更新快捷方式
如果程序位置或配置发生变化，重新运行安装脚本即可更新快捷方式。

---

**注意**: 此快捷方式仅适用于图形界面环境，在纯命令行环境中无法使用。