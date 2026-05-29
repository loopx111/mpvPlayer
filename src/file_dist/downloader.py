import asyncio
from pathlib import Path
from typing import Optional
import aiohttp
from ..utils.logger import get_logger
from ..utils.checksum import verify_checksum


class DownloadResult:
    def __init__(self, path: Path, success: bool, reason: Optional[str] = None):
        self.path = path
        self.success = success
        self.reason = reason


class Downloader:
    def __init__(self, max_concurrent: int = 3):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.log = get_logger("downloader")
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建复用的 aiohttp Session（避免每次下载创建新连接）"""
        async with self._session_lock:
            if self._session is None or self._session.closed:
                connector = aiohttp.TCPConnector(
                    limit=10,
                    limit_per_host=5,
                    ttl_dns_cache=300,
                    force_close=False,
                )
                self._session = aiohttp.ClientSession(connector=connector)
            return self._session

    async def fetch(self, url: str, dest: Path, checksum: Optional[str] = None,
                    checksum_type: str = "md5", headers: Optional[dict] = None) -> DownloadResult:
        async with self.semaphore:
            tmp = dest.with_suffix(dest.suffix + ".part")
            try:
                session = await self._get_session()
                async with session.get(url, headers=headers) as resp:
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

    async def close(self) -> None:
        """关闭持久化 Session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self.log.debug("aiohttp session closed")
