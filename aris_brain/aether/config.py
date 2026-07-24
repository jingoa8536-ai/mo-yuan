"""
Aether Config — 配置管理系统
YAML + 环境变量 + .env + 多Profile
用法: from aether.config import get_config
"""

import json, os, re
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CONFIG = {
    "app_name": "Aether", "version": "1.0.0", "debug": False,
    "log": {"level": "INFO", "file": "logs/aether.log", "max_size_mb": 10, "backup_count": 5},
    "llm": {"provider": "deepseek", "deepseek_api_key": "", "deepseek_model": "deepseek-chat",
            "temperature": 0.7, "max_tokens": 4096, "daily_budget_tokens": 1000000},
    "agent": {"max_steps": 10, "max_tokens_per_turn": 32000, "memory_threshold": 0.5,
              "enable_rules": True, "enable_memory": True},
    "server": {"host": "127.0.0.1", "port": 11527, "enable_3d_viz": True},
    "feishu": {"app_id": "", "app_secret": ""},
    "profiles_dir": "profiles", "state_dir": "state", "skills_dir": "skills",
}


class AetherConfig:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or "D:/LAAP/aris_brain")
        self._data: Dict = {}
        self._loaded = False

    def load(self, profile="aris"):
        self._data = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
        self._load_yaml("config.yaml")
        self._load_yaml(f"profiles/{profile}/config.yaml")
        self._load_dotenv()
        self._apply_env()
        self._resolve_paths()
        self._loaded = True
        return self

    def _load_yaml(self, path):
        p = self.base_dir / path
        if not p.exists():
            return
        try:
            import yaml
            data = yaml.safe_load(p.read_text("utf-8"))
            if isinstance(data, dict):
                self._merge(self._data, data)
        except Exception:
            pass

    def _load_dotenv(self):
        p = self.base_dir / ".env"
        if not p.exists():
            return
        for line in p.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if v.startswith("'") or v.startswith('"'):
                v = v[1:-1]
            if k and v and v != "***":
                os.environ.setdefault(k, v)

    def _apply_env(self):
        for ek, ck in [
            ("DEEPSEEK_API_KEY", "llm.deepseek_api_key"),
            ("DEEPSEEK_MODEL", "llm.deepseek_model"),
            ("FEISHU_APP_ID", "feishu.app_id"),
            ("FEISHU_APP_SECRET", "feishu.app_secret"),
            ("AETHER_DEBUG", "debug"),
            ("AETHER_LOG_LEVEL", "log.level"),
            ("AETHER_PORT", "server.port"),
        ]:
            v = os.environ.get(ek)
            if v:
                self._set(ck, v)

    def _resolve_paths(self):
        for k in ["log.file", "state_dir", "profiles_dir", "skills_dir"]:
            v = self.get(k)
            if isinstance(v, str) and not Path(v).is_absolute():
                self._set(k, str(self.base_dir / v))

    def get(self, key, default=None):
        keys = key.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    def _merge(self, base, override):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._merge(base[k], v)
            else:
                base[k] = v

    def _set(self, path, val):
        keys = path.split(".")
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = val

    def to_dict(self):
        return dict(self._data)


_config = None


def get_config(profile="aris"):
    global _config
    if _config is None:
        _config = AetherConfig()
        _config.load(profile)
    return _config


if __name__ == "__main__":
    c = get_config()
    key = c.get("llm.deepseek_api_key")
    print(f"Aether Config v1")
    print(f"  LLM Key: {'SET (' + key[-4:] + ')' if key else 'NOT SET'}")
    print(f"  LLM Model: {c.get('llm.deepseek_model')}")
    print(f"  Debug: {c.get('debug')}")
    print(f"  Log Level: {c.get('log.level')}")
    print(f"  Port: {c.get('server.port')}")
