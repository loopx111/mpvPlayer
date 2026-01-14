import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def data_dir() -> Path:
    root = project_root()
    dir_path = root / "data"
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def config_path() -> Path:
    return data_dir() / "config.json"


def logs_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def downloads_dir(default: str | None = None) -> Path:
    if default:
        path = Path(default)
    else:
        path = data_dir() / "downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path
