import asyncio
from pathlib import Path
from typing import Dict, Optional
from ..config.models import DownloadConfig
from ..utils.logger import get_logger
from .downloader import Downloader, DownloadResult


class DownloadTask:
    def __init__(self, task_id: str, url: str, dest: Path, checksum: Optional[str], checksum_type: str, extract: bool):
        self.task_id = task_id
        self.url = url
        self.dest = dest
        self.checksum = checksum
        self.checksum_type = checksum_type
        self.extract = extract
        self.status = "queued"
        self.reason: Optional[str] = None


class DownloadManager:
    def __init__(self, cfg: DownloadConfig):
        self.cfg = cfg
        self.downloader = Downloader(cfg.maxConcurrent)
        self.tasks: Dict[str, DownloadTask] = {}
        self.log = get_logger("download.manager")

    def enqueue(self, task: DownloadTask) -> None:
        self.tasks[task.task_id] = task
        asyncio.create_task(self._run(task))

    async def _run(self, task: DownloadTask) -> None:
        task.status = "downloading"
        result: DownloadResult = await self.downloader.fetch(task.url, task.dest, task.checksum, task.checksum_type)
        if result.success:
            task.status = "done"
        else:
            task.status = "failed"
            task.reason = result.reason

    def snapshot(self) -> Dict[str, dict]:
        return {tid: {
            "url": t.url,
            "status": t.status,
            "reason": t.reason,
            "dest": str(t.dest),
        } for tid, t in self.tasks.items()}
