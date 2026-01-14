import asyncio
from pathlib import Path
from typing import Optional
import aiohttp
from ..utils.logger import get_logger
from ..utils.checksum import verify_checksum


class DownloadResult:
    def __init__(self, path: Path, success: bool, reason: str | None = None):
        self.path = path
        self.success = success
        self.reason = reason


class Downloader:
    def __init__(self, max_concurrent: int = 3):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.log = get_logger("downloader")

    async def fetch(self, url: str, dest: Path, checksum: str | None = None, checksum_type: str = "md5", headers: Optional[dict] = None) -> DownloadResult:
        async with self.semaphore:
            tmp = dest.with_suffix(dest.suffix + ".part")
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url) as resp:
                        resp.raise_for_status()
                        tmp.parent.mkdir(parents=True, exist_ok=True)
                        with tmp.open("wb") as f:
                            async for chunk in resp.content.iter_chunked(1024 * 64):
                                f.write(chunk)
                if checksum and not verify_checksum(tmp, checksum, algo=checksum_type):
                    self.log.error("Checksum mismatch for %s", url)
                    tmp.unlink(missing_ok=True)
                    return DownloadResult(tmp, False, "checksum_mismatch")
                tmp.rename(dest)
                return DownloadResult(dest, True)
            except Exception as exc:
                self.log.error("Download failed %s: %s", url, exc)
                tmp.unlink(missing_ok=True)
                return DownloadResult(tmp, False, str(exc))
