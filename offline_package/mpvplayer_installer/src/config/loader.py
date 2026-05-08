import json
from pathlib import Path
from typing import Any, Dict, Optional
from .models import AppConfig, MqttConfig, DownloadConfig, PlayerConfig, SystemConfig
from ..utils.paths import config_path, downloads_dir


def _dict_to_config(data: Dict[str, Any]) -> AppConfig:
    mqtt = data.get("mqtt", {})
    download = data.get("download", {})
    player = data.get("player", {})
    system = data.get("system", {})

    cfg = AppConfig(
        mqtt=MqttConfig(**{k: v for k, v in mqtt.items() if k in MqttConfig().__dict__}),
        download=DownloadConfig(**{k: v for k, v in download.items() if k in DownloadConfig().__dict__}),
        player=PlayerConfig(**{k: v for k, v in player.items() if k in PlayerConfig().__dict__}),
        system=SystemConfig(**{k: v for k, v in system.items() if k in SystemConfig().__dict__}),
    )
    cfg.clamp()
    if not cfg.download.path:
        cfg.download.path = str(downloads_dir())
    return cfg


def load_config(path: Optional[Path] = None) -> AppConfig:
    cfg_path = path or config_path()
    if not cfg_path.exists():
        cfg = AppConfig()
        cfg.download.path = str(downloads_dir())
        save_config(cfg, cfg_path)
        return cfg
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return _dict_to_config(data)
    except Exception:
        cfg = AppConfig()
        cfg.download.path = str(downloads_dir())
        save_config(cfg, cfg_path)
        return cfg


def save_config(cfg: AppConfig, path: Optional[Path] = None) -> None:
    cfg.clamp()
    cfg_path = path or config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg_path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, default=lambda o: o.__dict__, ensure_ascii=False, indent=2)
