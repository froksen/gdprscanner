import os
import json
import copy
import pathlib


class ConfigStore:
    APP_DIR: pathlib.Path = pathlib.Path(os.environ["APPDATA"]) / "GDPRScanner"
    CONFIG_FILE: pathlib.Path = APP_DIR / "config.json"
    DEFAULT_CONFIG: dict = {
        "scan_folders": [],
        "file_age_days": 30,
        "scan_interval_minutes": 1440,
        "file_types": [".docx", ".xlsx", ".xls", ".csv", ".pdf", ".txt", ".log"],
        "ignore_paths": [],
    }

    def __init__(self) -> None:
        self._ensure_dir()
        self.config = self.load()

    def _ensure_dir(self) -> None:
        os.makedirs(self.APP_DIR, exist_ok=True)

    def load(self) -> dict:
        try:
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            return copy.deepcopy(self.DEFAULT_CONFIG)
        except json.JSONDecodeError:
            return copy.deepcopy(self.DEFAULT_CONFIG)

    def save(self, config: dict) -> None:
        tmp_path = self.CONFIG_FILE.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2, ensure_ascii=False)
        os.replace(tmp_path, self.CONFIG_FILE)
        self.config = config

    def get_config(self) -> dict:
        return copy.deepcopy(self.config)

    def get_ignore_paths(self) -> list[str]:
        return list(self.config.get("ignore_paths", []))

    def add_ignore_path(self, path: str) -> None:
        current = set(self.config.get("ignore_paths", []))
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized not in current:
            current.add(normalized)
            self.config["ignore_paths"] = list(current)
            self.save(self.config)

    def remove_ignore_path(self, path: str) -> None:
        current = set(self.config.get("ignore_paths", []))
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in current:
            current.remove(normalized)
            self.config["ignore_paths"] = list(current)
            self.save(self.config)

