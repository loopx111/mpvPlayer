import threading
import os
import subprocess
import platform
import queue
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
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
        self.current_playlist: List[Path] = []  # 当前播放列表（用于紧急呼叫）
        self.loop = loop
        self.volume = volume
        self._lock = threading.Lock()
        self.current_process: Optional[subprocess.Popen] = None
        self.current_file_index = 0  # 当前播放文件的索引
        self._last_process_check = 0  # 上次检查进程状态的时间戳
        
        # 支持的视频格式（必须在后台线程启动前定义）
        self.supported_formats = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        
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
        
        # 播放列表文件路径
        self.playlist_file = None
        self.use_playlist_mode = False  # 是否使用播放列表模式
        
        # 启动IPC状态查询定时器
        self._start_ipc_query_timer()
        
        # IPC状态查询相关
        self.current_playing_file = None  # 当前通过IPC查询到的播放文件
        self.ipc_query_timer = None  # IPC查询定时器
        


    def _init_playlist(self, video_path: str) -> None:
        """在后台线程中初始化播放列表"""
        # 所有系统都支持播放列表模式
        use_playlist_mode = True
        self.set_playlist_dir(video_path, use_playlist_mode)

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
                    self.log.error(f"执行命令 {command} 时出错: {str(e)}")
                finally:
                    self._command_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.log.error(f"命令工作线程异常: {e}")
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
                self.log.error(f"播放状态监测异常: {e}")
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
            
        # 如果进程还在运行，尝试通过IPC检测播放状态
        try:
            # 这里可以添加IPC检测逻辑，但目前先保持简单
            # 后续可以优化为通过IPC检测播放状态
            pass
        except Exception as e:
            self.log.debug(f"IPC状态检测失败: {e}")

    def _queue_command(self, command: str, *args, **kwargs) -> None:
        """将命令加入队列"""
        try:
            self._command_queue.put((command, args, kwargs), timeout=1)
        except queue.Full:
            self.log.warning("命令队列已满，丢弃命令: %s", command)

    def set_playlist_dir(self, path: str, use_playlist_mode: bool = False) -> None:
        """设置播放目录，在后台线程中执行
        
        Args:
            path: 视频目录路径
            use_playlist_mode: 是否使用播放列表文件模式（推荐在麒麟系统上使用）
        """
        def _set_playlist_internal():
            dir_path = Path(path)
            if dir_path.is_dir():
                # 搜索所有支持的视频文件
                video_files = self._find_video_files(dir_path)
                
                # 按文件名排序
                video_files.sort()
                
                with self._lock:
                    self.queue = video_files
                    self.use_playlist_mode = use_playlist_mode
                
                if self.queue:
                    self.log.info(f"在 {path} 目录下找到 {len(self.queue)} 个视频文件")
                    for i, file_path in enumerate(self.queue[:5]):  # 只显示前5个文件
                        self.log.info(f"  {i+1}. {file_path.name}")
                    if len(self.queue) > 5:
                        self.log.info(f"  ... 还有 {len(self.queue) - 5} 个文件")
                    
                    # 如果使用播放列表模式，创建播放列表文件
                    if use_playlist_mode:
                        self._create_playlist_file()
                    
                    # 延迟启动播放器
                    time.sleep(1)  # 等待 1 秒让 UI 完全加载
                    self._queue_command("_play_internal", self.queue[0])
                else:
                    self.log.warning("在目录 %s 中未找到视频文件", path)
                    self.log.warning("支持的格式: %s", ", ".join(self.supported_formats))
            else:
                self.log.error("目录不存在: %s", path)
        
        threading.Thread(target=_set_playlist_internal, daemon=True).start()
    
    def _find_video_files(self, dir_path: Path) -> List[Path]:
        """搜索视频文件"""
        video_files = []
        
        # 递归搜索所有支持的视频文件
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_ext = Path(file).suffix.lower()
                if file_ext in self.supported_formats:
                    video_files.append(Path(root) / file)
        
        return video_files
    
    def _create_playlist_file(self) -> None:
        """创建播放列表文件"""
        try:
            # 在项目data目录下创建播放列表文件
            playlist_dir = Path("/opt/mpvPlayer/data") if platform.system().lower() == "linux" else Path(__file__).parent.parent.parent / "data"
            playlist_dir.mkdir(parents=True, exist_ok=True)
            
            self.playlist_file = playlist_dir / "playlist.txt"
            
            with open(self.playlist_file, 'w', encoding='utf-8') as f:
                for video_file in self.queue:
                    f.write(str(video_file) + '\n')
            
            self.log.info(f"播放列表文件已创建: {self.playlist_file}")
            self.log.info(f"播放列表包含 {len(self.queue)} 个视频文件")
            
        except Exception as e:
            self.log.error(f"创建播放列表文件失败: {e}")
            self.use_playlist_mode = False  # 回退到单文件播放模式

    def play(self, file: Path) -> None:
        """播放文件（异步）"""
        self._queue_command("_play_internal", file)
    
    def play_single_file(self, file_path: str, loop: bool = False) -> None:
        """
        播放单个文件（用于紧急呼叫功能）
        
        Args:
            file_path: 文件路径字符串
            loop: 是否循环播放
        """
        file = Path(file_path)
        if file.exists():
            # 保存当前播放列表
            if hasattr(self, 'queue') and self.queue:
                self.log.info("保存当前播放列表以用于紧急呼叫")
            
            # 直接播放单个文件，强制使用单文件模式
            self._queue_command("_play_single_file_internal", file, loop)
            self.log.info(f"紧急呼叫：播放文件 {file.name} (循环: {loop})")
        else:
            self.log.error(f"紧急呼叫文件不存在: {file_path}")
    
    def _play_single_file_internal(self, file: Path, loop: bool = False) -> None:
        """内部单文件播放实现（用于紧急呼叫，强制使用单文件模式）"""
        self.log.info(f"紧急呼叫：开始播放文件: {file.name} (循环: {loop})")
        
        # 停止当前播放
        self._stop_current_playback()
        
        # 构建 mpv 命令
        cmd = [self.mpv_exe]
        
        # 检测是否在无头模式中运行
        is_headless = self._is_headless_mode()
        
        if is_headless:
            self.log.info("检测到无头模式，调整 MPV 参数")
            # 无头模式下的参数
            cmd.extend([
                file.as_posix(),  # 播放单个文件
                f"--volume={self.volume}",
                "--no-terminal",
                "--vo=null",  # 无视频输出
                "--ao=null",  # 无音频输出
                "--no-video"  # 不加载视频
            ])
        else:
            # 紧急呼叫强制使用单文件播放模式
            self.log.info("紧急呼叫：强制使用单文件播放模式")
            cmd.extend(self._build_single_file_command(file, loop))
        
        self.log.info(f"紧急呼叫：启动 MPV 命令: {' '.join(cmd)}")
        
        # 启动 mpv 进程
        try:
            self.log.info("启动 MPV 进程")
            # 根据操作系统选择不同的启动方式
            if platform.system().lower() == "windows":
                # Windows系统使用CREATE_NO_WINDOW避免控制台窗口
                process = subprocess.Popen(
                    cmd, 
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                # Linux/Unix系统不使用特殊标志
                process = subprocess.Popen(cmd)
                
            self.current_process = process
            self.log.info(f"MPV 进程已启动，PID: {process.pid}")
        except Exception as e:
            self.log.error(f"启动 MPV 失败: {str(e)}")
            # 尝试不使用特殊标志
            try:
                process = subprocess.Popen(cmd)
                self.current_process = process
                self.log.info(f"MPV 进程已启动（不使用特殊标志），PID: {process.pid}")
            except Exception as e2:
                self.log.error("第二次启动 MPV 失败: %s", str(e2))

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

    # 删除远程环境检测功能，因为远程播放已无问题

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
        
        # 构建 mpv 命令
        cmd = [self.mpv_exe]
        
        # 检测是否在无头模式中运行
        is_headless = self._is_headless_mode()
        
        if is_headless:
            self.log.info("检测到无头模式，调整 MPV 参数")
            # 无头模式下的参数
            cmd.extend([
                file.as_posix(),  # 播放单个文件
                f"--volume={self.volume}",
                "--no-terminal",
                "--vo=null",  # 无视频输出
                "--ao=null",  # 无音频输出
                "--no-video"  # 不加载视频
            ])
        else:
            # 使用播放列表模式（麒麟系统推荐）
            if self.use_playlist_mode and self.playlist_file and self.playlist_file.exists():
                self.log.info("使用播放列表模式进行播放")
                cmd.extend(self._build_playlist_command())
            else:
                # 单文件播放模式
                self.log.info("使用单文件播放模式")
                cmd.extend(self._build_single_file_command(file))
        
        self.log.info(f"启动 MPV 命令: {' '.join(cmd)}")
        
        # 启动 mpv 进程
        try:
            self.log.info("启动 MPV 进程")
            # 根据操作系统选择不同的启动方式
            if platform.system().lower() == "windows":
                # Windows系统使用CREATE_NO_WINDOW避免控制台窗口
                process = subprocess.Popen(
                    cmd, 
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                # Linux/Unix系统不使用特殊标志
                process = subprocess.Popen(cmd)
                
            self.current_process = process
            self.log.info(f"MPV 进程已启动，PID: {process.pid}")
        except Exception as e:
            self.log.error(f"启动 MPV 失败: {str(e)}")
            # 尝试不使用特殊标志
            try:
                process = subprocess.Popen(cmd)
                self.current_process = process
                self.log.info(f"MPV 进程已启动（不使用特殊标志），PID: {process.pid}")
            except Exception as e2:
                self.log.error("第二次启动 MPV 失败: %s", str(e2))
    
    def _build_playlist_command(self) -> List[str]:
        """构建播放列表模式的mpv命令（优化版本）"""
        cmd = [
            f"--playlist={self.playlist_file}",
            "--loop-playlist=inf",
            f"--volume={self.volume}",
            "--keep-open=always",  # 改为always，即使播放完成也保持窗口
            "--fullscreen",
            "--cursor-autohide=3000",
            "--input-default-bindings=yes",
            "--idle",  # 允许在空闲时保持运行
            "--force-window=yes"  # 强制创建窗口，即使没有视频
        ]
        
        # 添加IPC支持
        cmd.append("--input-ipc-server=/tmp/mpv-socket")
        
        # 添加字幕选项
        # 根据操作系统选择合适的字幕文件路径
        if platform.system().lower() == "linux":
            subtitle_file = Path("/opt/mpvPlayer/data/sub.ass")
        else:
            subtitle_file = Path("data/sub.ass")
        
        if subtitle_file.exists():
            cmd.extend([
                f"--sub-file={subtitle_file.as_posix()}",
                "--sub-ass=yes",
                "--sub-visibility=yes"
            ])
        
        # 麒麟系统特定设置：禁用问题解码器，使用软件解码
        if platform.system().lower() == "linux":
            cmd.extend([
                "--hwdec=no",           # 禁用硬件解码
                "--vd=lavc,h264",       # 强制使用libavcodec h264解码器
                "--vo=x11"              # 强制使用x11视频输出
            ])
        
        return cmd
    
    def _build_single_file_command(self, file: Path, loop: bool = False) -> List[str]:
        """构建单文件播放模式的mpv命令（优化版本）"""
        cmd = [
            file.as_posix(),
            f"--volume={self.volume}",
            "--keep-open=always",  # 改为always，即使播放完成也保持窗口
            "--fullscreen",
            f"--cursor-autohide={3000}",
            "--input-default-bindings=yes",
            "--idle",  # 允许在空闲时保持运行
            "--force-window=yes"  # 强制创建窗口，即使没有视频
        ]
        
        # 添加循环设置（根据参数决定）
        if loop:
            cmd.append("--loop-file=inf")
        
        # 添加IPC支持
        cmd.append("--input-ipc-server=/tmp/mpv-socket")
        
        # 添加字幕选项
        # 根据操作系统选择合适的字幕文件路径
        if platform.system().lower() == "linux":
            subtitle_file = Path("/opt/mpvPlayer/data/sub.ass")
        else:
            subtitle_file = Path("data/sub.ass")
        
        if subtitle_file.exists():
            cmd.extend([
                f"--sub-file={subtitle_file.as_posix()}",
                "--sub-ass=yes",
                "--sub-visibility=yes"
            ])
        
        # 麒麟系统特定设置：禁用问题解码器，使用软件解码
        if platform.system().lower() == "linux":
            cmd.extend([
                "--hwdec=no",           # 禁用硬件解码
                "--vd=lavc,h264",       # 强制使用libavcodec h264解码器
                "--vo=x11"              # 强制使用x11视频输出
            ])
        
        return cmd

    def _stop_current_playback(self) -> None:
        """停止当前播放（在命令工作线程中执行）"""
        if not self.current_process:
            return
            
        try:
            self.log.info("终止当前播放进程")
            current_process = self.current_process
            self.current_process = None  # 立即清空，避免竞态条件
            current_process.terminate()
            
            # 等待进程终止
            def wait_for_termination(process):
                try:
                    process.wait(timeout=3)
                    self.log.info("播放进程已正常终止")
                except subprocess.TimeoutExpired:
                    self.log.warning("进程终止超时，强制杀死进程")
                    try:
                        process.kill()
                        self.log.info("进程已被强制杀死")
                    except:
                        pass
            
            # 在后台线程中等待进程终止，避免阻塞命令工作线程
            termination_thread = threading.Thread(target=wait_for_termination, args=(current_process,), daemon=True)
            termination_thread.start()
            
        except Exception as e:
            self.log.warning("终止播放进程时出现异常: %s", str(e))
            self.current_process = None
            try:
                if self.current_process:
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
    
    def switch_video_seamless(self, file: Path) -> None:
        """无缝切换视频（通过IPC，不重启MPV进程）"""
        self._queue_command("_switch_video_seamless_internal", file)

    def _switch_video_seamless_internal(self, file: Path) -> None:
        """内部无缝切换实现"""
        if not self.current_process or self.current_process.poll() is not None:
            # 如果没有活跃进程，回退到普通播放
            self._play_internal(file)
            return
        
        # 尝试通过IPC切换视频
        if self._send_mpv_load_file_command(file.as_posix()):
            self.log.info(f"通过IPC无缝切换到: {file.name}")
            # 更新当前文件索引
            try:
                self.current_file_index = self.queue.index(file)
                self.log.info(f"当前播放索引: {self.current_file_index + 1}/{len(self.queue)}")
            except ValueError:
                self.current_file_index = 0
        else:
            # IPC失败，回退到重启播放
            self.log.warning("IPC切换失败，回退到重启播放")
            self._play_internal(file)

    def _send_mpv_load_file_command(self, file_path: str) -> bool:
        """通过IPC加载单个文件"""
        try:
            import socket
            import json
            import platform
            
            system = platform.system().lower()
            if system == "windows":
                return False  # Windows暂不支持
            
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect("/tmp/mpv-socket")
            
            # 发送加载文件命令
            cmd = {
                "command": ["loadfile", file_path, "replace"],
                "request_id": 300
            }
            sock.send(json.dumps(cmd).encode() + b'\n')
            
            # 等待响应
            try:
                response = sock.recv(1024).decode()
                self.log.debug(f"文件加载响应: {response}")
            except socket.timeout:
                self.log.warning("文件加载命令超时")
            
            sock.close()
            self.log.info(f"通过IPC加载文件成功: {file_path}")
            return True
            
        except Exception as e:
            self.log.warning(f"IPC文件加载失败: {e}")
            return False

    def _auto_play_next(self) -> None:
        """自动播放下一个文件（使用无缝切换）"""
        if not self.queue:
            return
            
        # 计算下一个文件的索引
        next_index = (self.current_file_index + 1) % len(self.queue)
        
        # 使用无缝切换
        self.log.info(f"自动无缝切换到下一个文件: {self.queue[next_index].name}")
        self.switch_video_seamless(self.queue[next_index])
    
    def set_playlist(self, playlist: List[Path]) -> None:
        """设置播放列表（用于紧急呼叫后恢复原始播放列表）"""
        self._queue_command("_set_playlist_internal", playlist)
    
    def _set_playlist_internal(self, playlist: List[Path]) -> None:
        """内部设置播放列表实现"""
        if not playlist:
            self.log.warning("播放列表为空，无法设置")
            return
            
        with self._lock:
            self.queue = playlist
            self.current_file_index = 0
            self.current_playlist = playlist.copy()
            
        self.log.info(f"已设置播放列表，包含 {len(playlist)} 个文件")
        
        # 更精确地检查当前是否有活跃的MPV进程
        process_active = False
        if self.current_process:
            # 双重检查进程状态
            try:
                poll_result = self.current_process.poll()
                if poll_result is None:
                    # 进程仍在运行，再尝试通过IPC查询状态确认
                    status = self.query_mpv_status()
                    if "error" not in str(status):
                        # IPC查询成功，进程确实在运行
                        process_active = True
                        self.log.info("MPV进程活跃，通过IPC命令继续播放原始播放列表")
                        # 构建播放列表路径
                        playlist_paths = [file.as_posix() for file in playlist]
                        # 通过IPC发送播放列表加载命令
                        self._send_mpv_load_list_command(playlist_paths)
                    else:
                        # IPC查询失败，进程可能已结束
                        self.log.warning("IPC查询失败，进程可能已结束，重新启动播放")
                        process_active = False
                else:
                    # 进程已结束
                    self.log.info(f"MPV进程已结束，退出码: {poll_result}")
                    self.current_process = None
                    process_active = False
            except Exception as e:
                self.log.warning(f"检查MPV进程状态时出错: {e}")
                process_active = False
        
        # 如果没有活跃进程或进程检查失败，正常启动播放
        if not process_active:
            if playlist:
                self._play_internal(playlist[0])
                self.log.info("开始播放原始播放列表")

    def is_mpv_process_healthy(self) -> bool:
        """检查MPV进程是否健康（避免在IPC查询失败时强制重启）"""
        if not self.current_process:
            return False
            
        try:
            # 检查进程是否仍在运行
            poll_result = self.current_process.poll()
            if poll_result is None:
                # 进程仍在运行，尝试通过IPC查询状态
                status = self.query_mpv_status()
                if "error" not in str(status):
                    # IPC查询成功，进程健康
                    return True
                else:
                    # IPC查询失败，但进程仍在运行（可能只是IPC连接问题）
                    self.log.debug("MPV进程运行但IPC连接失败，不强制重启")
                    return True  # 返回True避免强制重启
            else:
                # 进程已结束
                return False
        except Exception as e:
            self.log.debug(f"检查MPV进程健康状态时出错: {e}")
            return True  # 出错时返回True，避免强制重启

    def stop_play(self) -> None:
        """停止播放（异步）"""
        self._queue_command("_stop_play_internal")
    
    def _safe_restore_playlist(self, playlist: List[Path]) -> None:
        """安全恢复播放列表（当MPV进程健康但IPC连接不稳定时使用）"""
        self.log.info("使用安全备用方法恢复播放列表")
        
        # 首先尝试通过IPC恢复播放列表
        try:
            if self.current_process and self.current_process.poll() is None:
                # MPV进程仍在运行，尝试通过IPC发送播放列表
                playlist_paths = [file.as_posix() for file in playlist]
                success = self._send_mpv_load_list_command(playlist_paths)
                if success:
                    self.log.info("安全备用方法：通过IPC成功恢复播放列表")
                    return
        except Exception as e:
            self.log.debug(f"安全备用方法：IPC恢复失败: {e}")
        
        # IPC恢复失败，使用更安全的单文件播放方法
        if playlist:
            self.log.info(f"安全备用方法：播放第一个文件 {playlist[0].name}")
            self.play_single_file(playlist[0].as_posix())
        
        # 更新内部状态
        with self._lock:
            self.queue = playlist
            self.current_file_index = 0
            self.current_playlist = playlist.copy()
            
        self.log.info(f"安全备用方法：播放列表已恢复，包含 {len(playlist)} 个文件")

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
    
    def _send_mpv_load_list_command(self, file_paths: List[str], loop_playlist: bool = True) -> bool:
        """通过IPC发送播放列表加载命令
        
        Args:
            file_paths: 文件路径列表
            loop_playlist: 是否设置循环播放（默认True，用于help视频；False用于call视频）
        """
        try:
            import socket
            import json
            import platform
            
            # 检查操作系统类型
            system = platform.system().lower()
            
            if system == "windows":
                return False
            else:
                # Linux/Unix系统使用Unix域套接字
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(5.0)  # 增加超时时间到5秒
                sock.connect("/tmp/mpv-socket")
                
                # 首先清空当前播放列表
                cmd_clear = {
                    "command": ["playlist-clear"],
                    "request_id": 100
                }
                clear_cmd_str = json.dumps(cmd_clear)
                self.log.info(f"[IPC命令] 发送清空播放列表命令: {clear_cmd_str}")
                sock.send(clear_cmd_str.encode() + b'\n')
                
                # 等待响应，确保命令执行完成
                try:
                    response = sock.recv(1024).decode()
                    self.log.info(f"[IPC响应] 清空播放列表响应: {response}")
                except socket.timeout:
                    self.log.warning("清空播放列表命令超时，继续执行")
                
                # 使用loadfile命令强制切换文件，而不是添加到播放列表
                # 先加载第一个文件，然后添加其他文件
                if file_paths:
                    # 强制加载第一个文件（替换当前播放）
                    cmd_load = {
                        "command": ["loadfile", file_paths[0], "replace"],
                        "request_id": 101
                    }
                    load_cmd_str = json.dumps(cmd_load)
                    self.log.info(f"[IPC命令] 发送强制加载文件命令: {load_cmd_str}")
                    sock.send(load_cmd_str.encode() + b'\n')
                    
                    try:
                        response = sock.recv(1024).decode()
                        self.log.info(f"[IPC响应] 强制加载文件响应: {response}")
                    except socket.timeout:
                        self.log.warning("强制加载文件命令超时")
                    
                    # 添加其他文件到播放列表
                    for i, file_path in enumerate(file_paths[1:], 1):
                        cmd_add = {
                            "command": ["loadfile", file_path, "append"],
                            "request_id": 102 + i
                        }
                        add_cmd_str = json.dumps(cmd_add)
                        self.log.info(f"[IPC命令] 发送添加文件命令 {i}: {add_cmd_str}")
                        sock.send(add_cmd_str.encode() + b'\n')
                        
                        try:
                            response = sock.recv(1024).decode()
                            self.log.info(f"[IPC响应] 添加文件响应 {i}: {response}")
                        except socket.timeout:
                            self.log.warning(f"添加文件 {file_path} 命令超时")
                
                # 根据参数决定是否设置循环播放
                if loop_playlist:
                    # 设置循环播放（用于help视频）
                    cmd_loop = {
                        "command": ["set", "loop-playlist", "inf"],
                        "request_id": 200
                    }
                    loop_cmd_str = json.dumps(cmd_loop)
                    self.log.info(f"[IPC命令] 发送设置循环命令: {loop_cmd_str}")
                    sock.send(loop_cmd_str.encode() + b'\n')
                    
                    # 等待循环设置响应
                    try:
                        response = sock.recv(1024).decode()
                        self.log.info(f"[IPC响应] 设置循环响应: {response}")
                    except socket.timeout:
                        self.log.warning("设置循环命令超时")
                else:
                    # 清除循环播放设置（用于call视频）
                    cmd_loop = {
                        "command": ["set", "loop-playlist", "no"],
                        "request_id": 200
                    }
                    loop_cmd_str = json.dumps(cmd_loop)
                    self.log.info(f"[IPC命令] 发送清除循环命令: {loop_cmd_str}")
                    sock.send(loop_cmd_str.encode() + b'\n')
                    
                    # 等待循环清除响应
                    try:
                        response = sock.recv(1024).decode()
                        self.log.info(f"[IPC响应] 清除循环响应: {response}")
                    except socket.timeout:
                        self.log.warning("清除循环命令超时")
                
                # 设置播放列表位置到第一个文件
                cmd_set_pos = {
                    "command": ["set_property", "playlist-pos", 0],
                    "request_id": 201
                }
                pos_cmd_str = json.dumps(cmd_set_pos)
                self.log.info(f"[IPC命令] 发送设置播放列表位置命令: {pos_cmd_str}")
                sock.send(pos_cmd_str.encode() + b'\n')
                
                try:
                    response = sock.recv(1024).decode()
                    self.log.info(f"[IPC响应] 设置播放列表位置响应: {response}")
                except socket.timeout:
                    self.log.warning("设置播放列表位置命令超时")
                
                # 发送播放命令确保开始播放
                cmd_play = {
                    "command": ["set_property", "pause", False],
                    "request_id": 202
                }
                play_cmd_str = json.dumps(cmd_play)
                self.log.info(f"[IPC命令] 发送播放命令: {play_cmd_str}")
                sock.send(play_cmd_str.encode() + b'\n')
                
                try:
                    response = sock.recv(1024).decode()
                    self.log.info(f"[IPC响应] 播放命令响应: {response}")
                except socket.timeout:
                    self.log.warning("播放命令超时")
                
                sock.close()
                self.log.info(f"通过IPC加载播放列表成功，包含 {len(file_paths)} 个文件")
                return True
                
        except Exception as e:
            self.log.warning(f"IPC播放列表加载失败: {e}")
            return False
    
    def query_mpv_status(self) -> Dict[str, Any]:
        """通过IPC查询MPV播放状态"""
        try:
            import socket
            import json
            import platform
            
            # 检查操作系统类型
            system = platform.system().lower()
            
            if system == "windows":
                # Windows系统暂不支持IPC查询
                return {"error": "Windows系统暂不支持IPC查询"}
            else:
                # Linux/Unix系统使用Unix域套接字
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(2.0)  # 2秒超时，避免连接问题
                
                try:
                    sock.connect("/tmp/mpv-socket")
                except Exception as e:
                    self.log.debug(f"IPC连接失败: {e}")
                    return {"error": f"IPC连接失败: {e}"}
                
                # 查询当前播放文件的路径（使用path属性，最准确）
                cmd = {
                    "command": ["get_property", "path"],
                    "request_id": 1
                }
                cmd_str = json.dumps(cmd)
                self.log.info(f"[IPC查询] 发送命令: {cmd_str}")
                sock.send(cmd_str.encode() + b'\n')
                
                # 读取响应
                response = sock.recv(1024).decode()
                self.log.info(f"[IPC查询] 收到响应: {response}")
                
                # 解析响应
                try:
                    result = json.loads(response)
                    
                    # 查询其他状态信息
                    status = {"file_path": result.get("data", "")}
                    
                    # 查询播放状态
                    cmd = {
                        "command": ["get_property", "pause"],
                        "request_id": 3
                    }
                    cmd_str = json.dumps(cmd)
                    self.log.info(f"[IPC查询] 发送暂停状态查询: {cmd_str}")
                    sock.send(cmd_str.encode() + b'\n')
                    response = sock.recv(1024).decode()
                    self.log.info(f"[IPC查询] 收到暂停状态响应: {response}")
                    
                    pause_result = json.loads(response)
                    status["paused"] = pause_result.get("data", False)
                    sock.close()
                    
                    self.log.info(f"[IPC查询] MPV状态查询成功: {status}")
                    return status
                    
                except json.JSONDecodeError as e:
                    sock.close()
                    return {"error": f"JSON解析失败: {e}"}
                
        except Exception as e:
            self.log.debug(f"MPV状态查询失败: {e}")
            return {"error": str(e)}
    
    def get_current_playing_file(self) -> Optional[str]:
        """获取当前正在播放的文件名（通过IPC）"""
        if not self.current_process:
            return None
            
        # 检查进程是否仍在运行
        poll_result = self.current_process.poll()
        if poll_result is not None:
            return None
            
        # 通过IPC查询当前播放文件
        status = self.query_mpv_status()
        # 只要status中有file_path字段，就认为查询成功
        if "file_path" in status:
            current_file = status.get("file_path", "")
            # 更新当前播放文件属性
            if current_file != self.current_playing_file:
                self.current_playing_file = current_file
                self.log.info(f"get_current_playing_file更新当前播放文件: {current_file}")
            return current_file
        else:
            # IPC查询失败，回退到内部记录
            current_file = self._get_current_file()
            fallback_file = str(current_file) if current_file else None
            if fallback_file and fallback_file != self.current_playing_file:
                self.current_playing_file = fallback_file
                self.log.info(f"get_current_playing_file回退到内部记录: {fallback_file}")
            return fallback_file

    def get_playback_time(self) -> float:
        """轻量查询当前播放进度（秒），仅查 time-pos 一个属性
        
        Returns:
            播放进度秒数，查询失败返回 0.0
        """
        try:
            import socket
            import json
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect("/tmp/mpv-socket")
            cmd = json.dumps({"command": ["get_property", "time-pos"], "request_id": 99})
            self.log.info(f"[time-pos查询] 发送: {cmd}")
            sock.send(cmd.encode() + b'\n')
            response = sock.recv(1024).decode()
            sock.close()
            result = json.loads(response)
            time_pos = result.get("data", 0.0)
            self.log.info(f"[time-pos查询] 收到: {time_pos}s")
            return float(time_pos) if time_pos is not None else 0.0
        except Exception as e:
            self.log.info(f"[time-pos查询] 失败: {e}")
            return 0.0

    def _stop_play_internal(self) -> None:
        """内部停止播放实现"""
        self._stop_current_playback()

    def cleanup(self) -> None:
        """清理资源"""
        self.log.info("开始清理MPV控制器资源...")
        self._running = False
        
        # 停止IPC查询定时器
        self.stop_ipc_query_timer()
        
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
                self.log.info(f"清理MPV进程，PID: {self.current_process.pid}")
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
    
    def _ensure_window_visibility(self) -> None:
        """确保MPV窗口可见性"""
        if platform.system().lower() == "windows":
            # Windows窗口管理
            try:
                import win32gui
                import win32con
                
                def find_mpv_window():
                    windows = []
                    def enum_windows_proc(hwnd, _):
                        if win32gui.IsWindowVisible(hwnd):
                            title = win32gui.GetWindowText(hwnd)
                            if "mpv" in title.lower():
                                windows.append(hwnd)
                        return True
                    
                    win32gui.EnumWindows(enum_windows_proc, None)
                    return windows
                
                mpv_windows = find_mpv_window()
                for hwnd in mpv_windows:
                    # 置顶窗口
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                    # 最大化窗口
                    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                    
            except ImportError:
                self.log.warning("win32gui未安装，无法进行窗口管理")
        else:
            # Linux窗口管理（使用wmctrl）
            try:
                import subprocess
                # 查找mpv窗口并置顶
                subprocess.run(["wmctrl", "-R", "mpv"], timeout=5)
            except:
                self.log.warning("wmctrl未安装或执行失败")

    def _start_ipc_query_timer(self) -> None:
        """启动IPC状态查询定时器（3秒周期）"""
        try:
            import threading
            
            def ipc_query_worker():
                """IPC查询工作线程"""
                consecutive_errors = 0  # 连续错误计数
                max_consecutive_errors = 5  # 最大连续错误数
                
                while self._running:
                    try:
                        if self.current_process and self.current_process.poll() is None:
                            # 通过IPC查询当前播放文件
                            current_file = self.get_current_playing_file()
                            
                            # 如果IPC查询成功，重置错误计数
                            if current_file and "error" not in str(current_file):
                                consecutive_errors = 0
                                
                                # 提取文件名（如果包含路径）
                                if '/' in current_file or '\\' in current_file:
                                    import os
                                    current_file = os.path.basename(current_file)
                                
                                if current_file != self.current_playing_file:
                                    self.current_playing_file = current_file
                                    self.log.info(f"IPC查询到当前播放文件: {current_file}")
                            else:
                                # IPC查询失败，增加错误计数
                                consecutive_errors += 1
                                self.log.debug(f"IPC查询失败，连续错误次数: {consecutive_errors}")
                                
                                # 如果连续错误过多，回退到内部索引
                                if consecutive_errors >= max_consecutive_errors:
                                    self.log.warning("IPC查询连续失败，回退到内部索引")
                                    current_file = self._get_current_file()
                                    if current_file:
                                        self.current_playing_file = current_file.name
                                        consecutive_errors = 0  # 重置错误计数
                        
                        # 等待3秒
                        time.sleep(3)
                    except Exception as e:
                        consecutive_errors += 1
                        self.log.debug(f"IPC查询定时器异常: {e}")
                        
                        # 如果连续错误过多，短暂休眠
                        if consecutive_errors >= max_consecutive_errors:
                            self.log.warning("IPC查询连续异常，等待10秒后重试")
                            time.sleep(10)
                        else:
                            time.sleep(3)
            
            # 启动IPC查询线程
            self.ipc_query_timer = threading.Thread(target=ipc_query_worker, daemon=True)
            self.ipc_query_timer.start()
            self.log.info("IPC状态查询定时器已启动（3秒周期）")
            
        except Exception as e:
            self.log.error(f"启动IPC查询定时器失败: {e}")
    
    def stop_ipc_query_timer(self) -> None:
        """停止IPC查询定时器"""
        if self.ipc_query_timer and self.ipc_query_timer.is_alive():
            self._running = False
            try:
                self.ipc_query_timer.join(timeout=5)
                if self.ipc_query_timer.is_alive():
                    self.log.warning("IPC查询定时器未能及时终止")
                else:
                    self.log.info("IPC查询定时器已停止")
            except Exception as e:
                self.log.warning(f"停止IPC查询定时器时出错: {e}")
