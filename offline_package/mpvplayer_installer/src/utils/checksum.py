import hashlib
from pathlib import Path


def calc_checksum(path: Path, algo: str = "md5", chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_checksum(path: Path, expected: str, algo: str = "md5") -> bool:
    try:
        return calc_checksum(path, algo).lower() == expected.lower()
    except FileNotFoundError:
        return False
