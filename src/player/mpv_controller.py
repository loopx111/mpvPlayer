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
        self._last_process_check = 0  # 上次检查进程状态的时间戳
        
        # 异步控制队列
        self._command_queue = queue.Queue()
        self._running = True
        self._worker_thread = threading.Thread(target=self._command_worker, daemon=True)
        self._worker_thread.start()
        
        # 播放状态监测线程
        self._monitor_thread = threading.Thread(target=self._monitor_playback, daemon=True)
        self._monitor_thread.start()
        
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
    
    def _monitor_playback(self) -> None:
        """播放状态监测线程"""
        while self._running:
            try:
                current_time = time.time()
                # 每2秒检查一次播放进程状态
                if current_time - self._last_process_check > 2:
                    self._last_process_check = current_time
                    self._check_playback_status()
                time.sleep(1)
            except Exception as e:
                self.log.error("播放状态监测异常: %s", e)
                time.sleep(2)
    
    def _check_playback_status(self) -> None:
        """检查播放状态，如果播放完成则自动播放下一个文件"""
        if not self.current_process:
            return
            
        # 检查进程是否仍在运行
        poll_result = self.current_process.poll()
        if poll_result is not None:
            # 进程已结束，检查退出码
            self.log.info(f"MPV进程已结束，退出码: {poll_result}")
            self.current_process = None
            
            # 自动播放下一个文件
            if self.queue:
                self.log.info("检测到播放完成，自动播放下一个文件")
                self._queue_command("_auto_play_next")
            return

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

    def _is_remote_environment(self) -> bool:
        """检测是否在远程环境中运行"""
        import os
        import platform
        
        # 检查是否通过命令行参数强制启用远程模式
        if os.environ.get("MPV_REMOTE_MODE") == "true":
            return True
            
        # Windows系统远程桌面检测
        if platform.system().lower() == "windows":
            # 检查远程桌面会话
            try:
                import subprocess
                # 查询当前会话类型
                result = subprocess.run(["query", "session"], capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and "rdp" in result.stdout.lower():
                    return True
                
                # 检查远程桌面服务是否运行
                result = subprocess.run(["sc", "query", "TermService"], capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and "RUNNING" in result.stdout:
                    return True
            except:
                pass
        
        # Linux系统远程检测
        elif platform.system().lower() == "linux":
            # 检查SSH连接
            if os.environ.get("SSH_CONNECTION"):
                return True
                
            # 检查远程桌面环境变量
            remote_env_vars = ["SSH_TTY", "REMOTEHOST", "TERM", "XDG_SESSION_TYPE", "SSH_CLIENT", "SSH_AUTH_SOCK"]
            for var in remote_env_vars:
                if os.environ.get(var):
                    # 检查TERM是否为xterm或screen（远程终端）
                    if var == "TERM" and os.environ[var] in ["xterm", "screen", "linux", "xterm-256color"]:
                        return True
                    # 检查是否为远程会话
                    if var == "XDG_SESSION_TYPE" and os.environ[var] in ["tty", "x11"]:
                        return True
                    # SSH相关的环境变量
                    if var in ["SSH_CLIENT", "SSH_AUTH_SOCK"]:
                        return True
                    return True
            
            # 检查当前用户是否通过SSH登录
            try:
                import subprocess
                result = subprocess.run(["who", "am", "i"], capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and "pts" in result.stdout:
                    return True
            except:
                pass
                
            # 检查是否在远程桌面环境中（xrdp、VNC等）
            try:
                # 检查是否有远程桌面进程
                remote_procs = ["xrdp", "vncserver", "x11vnc", "tigervnc"]
                for proc in remote_procs:
                    result = subprocess.run(["pgrep", proc], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        return True
            except:
                pass
                
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
            "--keep-open=no"  # 播放完成后自动关闭，触发自动播放下一个文件
        ]
        
        # 检测是否在无头模式中运行
        is_headless = self._is_headless_mode()
        
        # 检测远程环境（仅Windows系统进行检测）
        is_remote = False
        if platform.system().lower() == "windows":
            is_remote = self._is_remote_environment()
        
        if is_headless:
            self.log.info("检测到无头模式，调整 MPV 参数")
            # 无头模式下的参数
            cmd.extend([
                "--vo=null",  # 无视频输出
                "--ao=null",  # 无音频输出
                "--no-video"  # 不加载视频
            ])
        elif is_remote:
            self.log.info("检测到远程环境，使用优化的远程播放参数")
            # Windows远程桌面优化参数
            cmd.extend([
                "--force-window=immediate",  # 立即显示窗口
                "--geometry=50%x50%+100+100",  # 小窗口播放
                "--hwdec=no",  # 禁用硬件解码，减少资源占用
                "--no-fullscreen",  # 禁用全屏模式
                "--ontop",  # 窗口置顶
                "--border=no",  # 无边框
                "--autofit=50%",  # 自动适应窗口大小
                "--no-input-default-bindings",  # 禁用默认键绑定
                "--input-cursor=no",  # 禁用鼠标输入
                "--cursor-autohide=no",  # 禁用鼠标自动隐藏
                "--loop-file=no",  # 禁用文件循环
                "--framedrop=yes",  # 允许丢帧，减少延迟
                "--demuxer-max-bytes=1M",  # 限制解复用器缓存
                "--cache=no",  # 禁用缓存
                "--profile=low-latency",  # 低延迟模式
                "--gpu-api=win7"  # 使用兼容性更好的GPU API
            ])
        elif platform.system().lower() != "windows":
            # Linux环境的参数（直接使用本地播放参数）
            cmd.extend([
                "--force-window=immediate",  # 立即显示窗口
                "--geometry=800x600+100+100",  # 设置窗口大小和位置
                "--input-ipc-server=/tmp/mpv-socket",  # 启用IPC通信
                "--input-file=/dev/stdin"  # 允许通过stdin输入
            ])
        else:
            # 本地Windows环境的参数
            cmd.extend([
                "--force-window=immediate",  # 立即显示窗口
                "--geometry=800x600+100+100"  # 设置窗口大小和位置
            ])
        
            # 移除文件循环设置，因为我们通过播放列表来实现循环
            # 单个文件播放完成后会自动关闭，触发自动播放下一个文件
        
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
        self._auto_play_next()
    
    def _auto_play_next(self) -> None:
        """自动播放下一个文件（用于播放完成后的自动切换）"""
        with self._lock:
            if not self.queue:
                self.log.warning("播放队列为空，无法自动播放下一个文件")
                return
            
            # 计算下一个文件的索引
            next_index = self.current_file_index + 1
            
            if next_index < len(self.queue):
                nxt = self.queue[next_index]
                self.log.info(f"自动播放下一个文件: {nxt.name} (索引: {next_index})")
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
        self.log.info("开始清理MPV控制器资源...")
        self._running = False
        
        # 停止所有工作线程
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
            if self._worker_thread.is_alive():
                self.log.warning("工作线程未能及时终止")
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
            if self._monitor_thread.is_alive():
                self.log.warning("监控线程未能及时终止")
        
        # 立即停止当前播放
        if self.current_process:
            try:
                self.log.info("清理MPV进程，PID: %d", self.current_process.pid)
                # 先尝试正常终止
                self.current_process.terminate()
                
                # 等待进程终止并回收资源
                try:
                    exit_code = self.current_process.wait(timeout=2)
                    self.log.info(f"MPV进程已正常终止，退出码: {exit_code}")
                except subprocess.TimeoutExpired:
                    self.log.warning("MPV进程终止超时，强制杀死")
                    if self.current_process:
                        self.current_process.kill()
                        self.current_process.wait(timeout=1)
                except Exception as e:
                    self.log.warning(f"等待MPV进程终止时出错: {e}")
                    if self.current_process:
                        self.current_process.kill()
                        try:
                            self.current_process.wait(timeout=1)
                        except:
                            pass
            except Exception as e:
                self.log.error(f"清理MPV进程失败: {e}")
            finally:
                self.current_process = None
        
        # 清理僵尸进程
        self._cleanup_zombie_processes()
        
        self.log.info("MPV控制器资源清理完成")
    
    def _cleanup_zombie_processes(self) -> None:
        """清理僵尸进程"""
        try:
            import subprocess
            
            # 在Linux系统上清理僵尸进程
            if platform.system().lower() == "linux":
                # 查找所有defunct的mpv进程
                try:
                    result = subprocess.run(
                        ["ps", "-ef"], 
                        capture_output=True, 
                        text=True, 
                        timeout=5
                    )
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        for line in lines:
                            if 'mpv' in line and '<defunct>' in line:
                                # 提取PID
                                parts = line.split()
                                if len(parts) >= 2:
                                    pid = parts[1]
                                    try:
                                        self.log.info(f"发现僵尸MPV进程 PID: {pid}, 尝试清理")
                                        # 尝试向父进程发送SIGCHLD信号
                                        subprocess.run(["kill", "-s", "SIGCHLD", pid], timeout=2)
                                    except:
                                        pass
                except Exception as e:
                    self.log.warning(f"清理僵尸进程时出错: {e}")
        except Exception as e:
            self.log.warning(f"僵尸进程清理功能异常: {e}")
