# 快速开始指南

## 🚀 5分钟快速部署

### 麒麟系统（最简单方式）

#### 第一步：安装依赖
```bash
# 运行增强版安装脚本（包含所有修复）
./install_kylin_deps_v2.sh
```

#### 第二步：启动应用
```bash
# 使用专用启动脚本
./start_kylin.sh
```

✅ **完成！应用现在应该正常运行**

---

## 📋 验证安装

应用启动后，检查以下内容：

1. **视频播放**：MPV窗口应该全屏播放视频
2. **控制界面**：应该能看到PySide6控制台界面
3. **日志输出**：查看控制台输出确认无错误

### 快速测试命令
```bash
# 检查基本功能
python3 -c "import PySide6; print('✓ PySide6正常')"
mpv --version && echo "✓ MPV正常"
```

---

## 🔧 遇到问题？

### 常见快速修复

#### 问题1：UI界面不显示
```bash
# 重新启动（脚本已包含修复）
./start_kylin.sh
```

#### 问题2：依赖安装失败
```bash
# 手动安装关键依赖
sudo apt install python3 python3-pip python3-venv mpv
pip install PySide6 paho-mqtt python-mpv
```

#### 问题3：权限问题
```bash
# 给脚本执行权限
chmod +x *.sh
```

---

## 📁 文件说明

### 必须文件
- `src/` - 源代码目录
- `data/config_kylin.json` - 麒麟系统配置
- `requirements.txt` - Python依赖列表

### 重要脚本
- `install_kylin_deps_v2.sh` - **推荐安装脚本**
- `start_kylin.sh` - **推荐启动脚本**

---

## 🎯 下一步

应用正常运行后，你可以：

1. **配置MQTT**：修改 `data/config_kylin.json` 中的MQTT设置
2. **添加视频**：将视频文件放入 `/opt/mpvPlayer/data/videos/`
3. **查看文档**：阅读 `README.md` 了解高级功能
4. **故障排除**：查看 `docs/故障排除.md` 解决具体问题

---

## 💡 提示

- **生产环境**：使用 `sudo ./install_kylin.sh` 进行系统级安装
- **开发测试**：使用增强版脚本在当前目录安装
- **问题反馈**：查看 `data/logs/mpvPlayer.log` 获取详细错误信息

**记住：对于日常使用，只需要两个命令：**
```bash
./install_kylin_deps_v2.sh  # 安装（只需一次）
./start_kylin.sh           # 启动（每次使用）
```