import threading
import os
import subprocess
import platform
import queue
import time
from pathlib import Path
from typing import Optional, List
from ..utils.logger import get_logger


class MpvController:
    def __init__(self, video_path: str, volume: int = 70, loop: bool = True, show_controls: bool = True):
        self.log = get_logger("mpv")
        # 根据操作系统选择 mpv 可执行文件
        system = platform.system().lower()
        if system == "windows":
            self.mpv_exe = r"D:\soft\mpv\mpv.exe"
        elif system == "linux":
            self.mpv_exe = "mpv"  # Linux 系统使用系统路径中的 mpv
        else:
            self.mpv_exe = "mpv"  # 其他系统也使用 mpv
            
        self.log.info(f"检测到系统: {system}, 使用 mpv 路径: {self.mpv_exe}")
        self.queue: List[Path] = []
        self.loop = loop
        self.volume = volume
        self._lock = threading.Lock()
        self.current_process: Optional[subprocess.Popen] = None
        self.current_file_index = 0  # 当前播放文件的索引
        
        # 异步控制队列
        self._command_queue = queue.Queue()
        self._running = True
        self._worker_thread = threading.Thread(target=self._command_worker, daemon=True)
        self._worker_thread.start()
        
        # 延迟初始化播放列表
        threading.Thread(target=self._init_playlist, args=(video_path,), daemon=True).start()

    def _init_playlist(self, video_path: str) -> None:
        """在后台线程中初始化播放列表"""
        self.set_playlist_dir(video_path)

    def _command_worker(self) -> None:
        """命令处理工作线程"""
        while self._running:
            try:
                command, args, kwargs = self._command_queue.get(timeout=1)
                try:
                    if hasattr(self, command):
                        getattr(self, command)(*args, **kwargs)
                    else:
                        self.log.error("未知命令: %s", command)
                except Exception as e:
                    self.log.error("执行命令 %s 时出错: %s", command, e)
                finally:
                    self._command_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.log.error("命令工作线程异常: %s", e)
                time.sleep(0.1)

    def _queue_command(self, command: str, *args, **kwargs) -> None:
        """将命令加入队列"""
        try:
            self._command_queue.put((command, args, kwargs), timeout=1)
        except queue.Full:
            self.log.warning("命令队列已满，丢弃命令: %s", command)

    def set_playlist_dir(self, path: str) -> None:
        """设置播放目录，在后台线程中执行"""
        def _set_playlist_internal():
            dir_path = Path(path)
            if dir_path.is_dir():
                # 递归搜索所有 mp4 文件
                mp4_files = []
                for root, dirs, files in os.walk(dir_path):
                    for file in files:
                        if file.lower().endswith('.mp4'):
                            mp4_files.append(Path(root) / file)
                
                # 按文件名排序
                mp4_files.sort()
                
                with self._lock:
                    self.queue = mp4_files
                
                if self.queue:
                    self.log.info(f"在 {path} 目录下找到 {len(self.queue)} 个 mp4 文件")
                    for i, file_path in enumerate(self.queue[:5]):  # 只显示前5个文件
                        self.log.info(f"  {i+1}. {file_path.name}")
                    if len(self.queue) > 5:
                        self.log.info(f"  ... 还有 {len(self.queue) - 5} 个文件")
                    
                    # 延迟启动播放器
                    time.sleep(1)  # 等待 1 秒让 UI 完全加载
                    self._queue_command("_play_internal", self.queue[0])
                else:
                    self.log.warning("在目录 %s 中未找到 mp4 文件", path)
            else:
                self.log.error("目录不存在: %s", path)
        
        threading.Thread(target=_set_playlist_internal, daemon=True).start()

    def play(self, file: Path) -> None:
        """播放文件（异步）"""
        self._queue_command("_play_internal", file)

    def _is_headless_mode(self) -> bool:
        """检测是否在无头模式中运行"""
        # Windows系统默认不使用无头模式
        if platform.system().lower() == "windows":
            return False
        
        # 检查是否在Kylin系统上运行
        if os.path.exists('/etc/kylin-version'):
            # Kylin系统强制使用图形模式
            self.log.info("检测到Kylin系统，强制使用图形模式")
            return False
        
        # 检查QT_QPA_PLATFORM环境变量
        qt_platform = os.environ.get('QT_QPA_PLATFORM', '').lower()
        if qt_platform == 'offscreen':
            return True
        
        # Linux系统：检查DISPLAY环境变量
        if os.environ.get('DISPLAY') is None:
            return True
        
        # 检查是否在容器中运行
        if os.path.exists('/.dockerenv') or os.path.exists('/.container'):
            return True
            
        return False

    def _play_internal(self, file: Path) -> None:
        """内部播放实现（在命令工作线程中执行）"""
        self.log.info(f"开始播放文件: {file.name}")
        
        # 更新当前文件索引
        try:
            self.current_file_index = self.queue.index(file)
            self.log.info(f"当前播放索引: {self.current_file_index + 1}/{len(self.queue)}")
        except ValueError:
            self.current_file_index = 0
        
        # 停止当前播放
        self._stop_current_playback()
        
        # 构建基础 mpv 命令
        cmd = [
            self.mpv_exe,
            file.as_posix(),
            f"--volume={self.volume}",
            "--no-terminal",
            "--keep-open=yes"
        ]
        
        # 检测是否在无头模式中运行
        is_headless = self._is_headless_mode()
        
        if is_headless:
            self.log.info("检测到无头模式，调整 MPV 参数")
            # 无头模式下的参数
            cmd.extend([
                "--vo=null",  # 无视频输出
                "--ao=null",  # 无音频输出
                "--no-video"  # 不加载视频
            ])
        else:
            # 有显示环境下的参数
            cmd.extend([
                "--fs",  # 全屏播放
                "--force-window=immediate"  # 立即显示窗口
            ])
        
        # 仅在Linux/Unix系统启用IPC
        if platform.system().lower() != "windows":
            cmd.extend([
                "--input-ipc-server=/tmp/mpv-socket",  # 启用IPC通信
                "--input-file=/dev/stdin"  # 允许通过stdin输入
            ])
        
        if self.loop:
            cmd.append("--loop=inf")
        
        self.log.info(f"启动 MPV 命令: {' '.join(cmd)}")
        
        # 启动 mpv 进程
        try:
            self.log.info("启动 MPV 进程")
            # 根据操作系统选择不同的启动方式
            if platform.system().lower() == "windows":
                # Windows系统使用CREATE_NEW_CONSOLE
                process = subprocess.Popen(
                    cmd, 
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # Linux/Unix系统不使用特殊标志
                process = subprocess.Popen(cmd)
                
            self.current_process = process
            self.log.info(f"MPV 进程已启动，PID: {process.pid}")
        except Exception as e:
            self.log.error("启动 MPV 失败: %s", e)
            # 尝试不使用特殊标志
            try:
                process = subprocess.Popen(cmd)
                self.current_process = process
                self.log.info(f"MPV 进程已启动（不使用特殊标志），PID: {process.pid}")
            except Exception as e2:
                self.log.error("第二次启动 MPV 失败: %s", e2)

    def _stop_current_playback(self) -> None:
        """停止当前播放（在命令工作线程中执行）"""
        if not self.current_process:
            return
            
        try:
            self.log.info("终止当前播放进程")
            self.current_process.terminate()
            
            # 等待进程终止
            def wait_for_termination():
                try:
                    self.current_process.wait(timeout=3)
                    self.log.info("播放进程已正常终止")
                except subprocess.TimeoutExpired:
                    self.log.warning("进程终止超时，强制杀死进程")
                    try:
                        self.current_process.kill()
                        self.log.info("进程已被强制杀死")
                    except:
                        pass
                finally:
                    self.current_process = None
            
            # 在后台线程中等待进程终止，避免阻塞命令工作线程
            termination_thread = threading.Thread(target=wait_for_termination, daemon=True)
            termination_thread.start()
            
        except Exception as e:
            self.log.warning("终止播放进程时出现异常: %s", e)
            try:
                self.current_process.kill()
                self.current_process = None
                self.log.info("强制杀死播放进程")
            except:
                pass

    def toggle_pause(self) -> None:
        """播放/暂停（异步）"""
        self._queue_command("_toggle_pause_internal")

    def _toggle_pause_internal(self) -> None:
        """内部播放/暂停实现"""
        self.log.info("用户点击播放/暂停按钮")
        if self.current_process:
            # 优先尝试通过IPC控制
            if self._send_mpv_ipc_command("cycle pause"):
                self.log.info("通过IPC发送暂停/播放指令")
                return
            
            # IPC失败则尝试键盘模拟
            try:
                import pyautogui
                pyautogui.press('space')
                self.log.info("通过键盘模拟发送暂停/播放指令")
            except ImportError:
                self.log.warning("pyautogui 未安装，无法控制播放/暂停")
            except Exception as e:
                self.log.error("控制播放/暂停失败: %s", e)
        else:
            self.log.warning("没有正在运行的播放进程，无法暂停/播放")

    def set_volume(self, vol: int) -> None:
        """设置音量（异步）"""
        self._queue_command("_set_volume_internal", vol)

    def _set_volume_internal(self, vol: int) -> None:
        """内部音量设置实现"""
        self.volume = max(0, min(vol, 100))
        # 无法实时调整音量，需要重启播放器
        if self.current_process:
            current_file = self._get_current_file()
            if current_file:
                self._play_internal(current_file)

    def _get_current_file(self) -> Optional[Path]:
        """获取当前播放的文件"""
        with self._lock:
            if self.current_process and self.queue and 0 <= self.current_file_index < len(self.queue):
                return self.queue[self.current_file_index]
        return None

    def next_file(self) -> None:
        """切换到下一首（异步）"""
        self._queue_command("_next_file_internal")

    def _next_file_internal(self) -> None:
        """内部下一首实现"""
        self.log.info("用户点击下一首按钮")
        
        with self._lock:
            if not self.queue:
                self.log.warning("播放队列为空，无法切换到下一首")
                return
            
            current_file = self._get_current_file()
            if not current_file:
                self.log.warning("当前没有播放文件，无法切换到下一首")
                return
            
            self.log.info(f"当前播放文件: {current_file.name} (索引: {self.current_file_index})")
            
            # 计算下一个文件的索引
            next_index = self.current_file_index + 1
            
            if next_index < len(self.queue):
                nxt = self.queue[next_index]
                self.log.info(f"切换到下一首: {nxt.name} (索引: {next_index})")
            elif self.loop and self.queue:
                nxt = self.queue[0]
                self.log.info("播放队列结束，循环到第一首: %s", nxt.name)
                next_index = 0
            else:
                self.log.info("播放队列结束，没有更多文件")
                return
        
        # 更新当前文件索引并播放下一首
        self.current_file_index = next_index
        self._play_internal(nxt)

    def stop_play(self) -> None:
        """停止播放（异步）"""
        self._queue_command("_stop_play_internal")

    def _send_mpv_ipc_command(self, command: str) -> bool:
        """通过IPC发送命令给MPV"""
        try:
            import socket
            import json
            import platform
            
            # 检查操作系统类型
            system = platform.system().lower()
            
            if system == "windows":
                # Windows系统使用命名管道
                # 注意：MPV在Windows上默认不启用IPC，这里直接返回False
                return False
            else:
                # Linux/Unix系统使用Unix域套接字
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(2.0)  # 2秒超时
                sock.connect("/tmp/mpv-socket")
                
                # 发送JSON-RPC命令
                cmd = {
                    "command": ["keypress", command] if " " not in command else command.split()
                }
                sock.send(json.dumps(cmd).encode() + b'\n')
                
                # 读取响应
                response = sock.recv(1024).decode()
                sock.close()
                
                self.log.debug(f"IPC命令发送成功: {command}")
                return True
                
        except Exception as e:
            self.log.warning(f"IPC命令失败，将使用备用方案: {e}")
            return False

    def _stop_play_internal(self) -> None:
        """内部停止播放实现"""
        self._stop_current_playback()

    def cleanup(self) -> None:
        """清理资源"""
        self._running = False
        self._stop_current_playback()
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
