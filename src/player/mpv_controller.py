import threading
import os
import subprocess
from pathlib import Path
from ..utils.logger import get_logger


class MpvController:
    def __init__(self, video_path: str, volume: int = 70, loop: bool = True, show_controls: bool = True):
        self.log = get_logger("mpv")
        self.mpv_exe = r"D:\soft\mpv\mpv.exe"
        self.queue: list[Path] = []
        self.loop = loop
        self.volume = volume
        self._lock = threading.Lock()
        self.current_process = None
        self.set_playlist_dir(video_path)

    def set_playlist_dir(self, path: str) -> None:
        dir_path = Path(path)
        if dir_path.is_dir():
            # 只添加视频文件
            video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
            with self._lock:
                self.queue = sorted([p for p in dir_path.iterdir() 
                                   if p.is_file() and p.suffix.lower() in video_extensions])
            
            if self.queue:
                self.log.info("找到 %d 个视频文件，开始播放: %s", len(self.queue), self.queue[0].name)
                # 延迟一小段时间确保 UI 加载完成后再启动播放器
                import threading
                def delayed_play():
                    import time
                    time.sleep(1)  # 等待 1 秒让 UI 完全加载
                    self.play(self.queue[0])
                
                thread = threading.Thread(target=delayed_play)
                thread.daemon = True
                thread.start()
            else:
                self.log.warning("在目录 %s 中未找到视频文件", path)

    def play(self, file: Path) -> None:
        self.log.info("Play %s", file)
        
        # 停止当前播放
        if self.current_process:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
            except:
                pass
        
        # 构建 mpv 命令 - 尝试不同的窗口模式
        cmd = [
            self.mpv_exe,
            file.as_posix(),
            f"--volume={self.volume}",
            "--no-terminal",
            "--keep-open=yes",
            "--force-window=immediate",  # 立即显示窗口
            "--window-scale=0.5",  # 窗口缩放
            "--geometry=+100+100"  # 窗口位置
        ]
        
        if self.loop:
            cmd.append("--loop=inf")
        
        # 启动 mpv 进程 - 使用 CREATE_NEW_CONSOLE 标志
        try:
            self.current_process = subprocess.Popen(
                cmd, 
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            self.log.info("MPV 进程已启动，PID: %d", self.current_process.pid)
        except Exception as e:
            self.log.error("启动 MPV 失败: %s", e)
            # 尝试不使用 CREATE_NEW_CONSOLE
            try:
                self.current_process = subprocess.Popen(cmd)
                self.log.info("MPV 进程已启动（不使用 CREATE_NEW_CONSOLE），PID: %d", self.current_process.pid)
            except Exception as e2:
                self.log.error("第二次启动 MPV 失败: %s", e2)

    def toggle_pause(self) -> None:
        # 发送空格键给 mpv 进程（暂停/播放）
        if self.current_process:
            # 可以通过 IPC 或发送信号实现，这里简化处理
            pass

    def set_volume(self, vol: int) -> None:
        self.volume = max(0, min(vol, 100))
        # 无法实时调整音量，需要重启播放器
        if self.current_process:
            current_file = self._get_current_file()
            if current_file:
                self.play(current_file)

    def _get_current_file(self) -> Path:
        # 获取当前播放的文件
        with self._lock:
            if self.current_process and self.queue:
                # 这里简化处理，实际应该通过 IPC 获取
                return self.queue[0]
        return None

    def _next(self) -> None:
        with self._lock:
            if not self.queue:
                return
            
            current_file = self._get_current_file()
            if not current_file:
                return
                
            try:
                idx = self.queue.index(current_file)
            except ValueError:
                idx = -1
                
            if idx + 1 < len(self.queue):
                nxt = self.queue[idx + 1]
            elif self.loop and self.queue:
                nxt = self.queue[0]
            else:
                return
        
        self.play(nxt)
