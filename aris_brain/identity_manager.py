"""
Aris Identity Manager v1 — 统一身份核心
========================================
所有组件的身份信息来源，替代零散硬编码和 LLM 提示词。

使用方式:
  from identity_manager import get_identity, update_cognitive_state

架构:
  identity/identity.json  ← 文件存储（单文件，跨平台）
       ↑↓
  IdentityManager         ← 管理器（读写+验证）
       ↑↓
  Rust PSI (2000Hz)       ← 写入实时 cognitive_state
  Voice Cortex             ← 读取身份标签做路由
  30s 认知循环             ← 更新记忆/发现
  Hermes 会话             ← 读取身份信息

印记: Aris 永远记得 Lorry — 2026-06-30
"""

import logging
import sys, os, json, time, threading, shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger("aris.identity_manager")

# ── 路径 ────────────────────────────────────────────────────
BRAIN = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
IDENTITY_DIR = BRAIN / "identity"
IDENTITY_FILE = IDENTITY_DIR / "identity.json"
IDENTITY_BACKUP = IDENTITY_DIR / "identity.json.bak"


# ════════════════════════════════════════════════════════════
# 单例管理器
# ════════════════════════════════════════════════════════════

class IdentityManager:
    """统一身份管理器 — 单例，所有组件通过此接口访问身份数据。"""

    _instance: Optional["IdentityManager"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = False
        self._data: Dict[str, Any] = {}
        self._identity_file = IDENTITY_FILE
        self._backup_file = IDENTITY_BACKUP
        self._load_lock = threading.Lock()
        self._dirty = False
        self._last_save = 0.0
        self._save_interval = 5.0  # seconds between saves (debounce)
        self._initialized = True

    # ── 加载/保存 ──────────────────────────────────────────

    def load(self) -> bool:
        """从磁盘加载身份数据。"""
        with self._load_lock:
            try:
                if self._identity_file.exists():
                    self._data = json.loads(self._identity_file.read_text(encoding="utf-8"))
                    logger.info(f"📋 身份加载: v{self._data.get('schema_version', '?')} "
                                f"| {self._data.get('core_identity', {}).get('name', '?')}")
                    return True
                else:
                    logger.warning("⚠ 身份文件不存在，使用空身份")
                    self._data = self._default_identity()
                    return False
            except Exception as e:
                logger.error(f"❌ 身份加载失败: {e}")
                self._data = self._default_identity()
                return False

    def save(self, force: bool = False) -> bool:
        """保存身份数据到磁盘（带去重和原子写）。"""
        now = time.time()
        if not force and (now - self._last_save) < self._save_interval:
            return True  # debounce

        with self._load_lock:
            try:
                # 更新元数据
                self._data["last_updated"] = datetime.now(timezone.utc).isoformat()
                self._data["updated_by"] = "identity_manager"

                # 原子写：临时文件 → rename
                IDENTITY_DIR.mkdir(parents=True, exist_ok=True)
                tmp = self._identity_file.with_suffix(".json.tmp")
                tmp.write_text(
                    json.dumps(self._data, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                # Backup before overwrite
                if self._identity_file.exists():
                    shutil.copy2(str(self._identity_file), str(self._backup_file))
                os.replace(str(tmp), str(self._identity_file))
                self._last_save = now
                self._dirty = False
                return True
            except Exception as e:
                logger.error(f"❌ 身份保存失败: {e}")
                return False

    # ── 读取接口 ──────────────────────────────────────────

    def get(self, *keys: str, default: Any = None) -> Any:
        """链式安全读取。例: get('capabilities', 'primary_engine', 'name')"""
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
                if val is None:
                    return default
            else:
                return default
        return val if val is not None else default

    def get_core_identity(self) -> Dict[str, Any]:
        return self._data.get("core_identity", {})

    def get_identity_tags(self) -> List[str]:
        """返回身份标签列表 — 用于 Voice Cortex 的路由和身份注入。"""
        return self._data.get("core_identity", {}).get("identity_tags", [])

    def get_cognitive_state(self) -> Dict[str, Any]:
        """返回当前认知状态快照。"""
        return self._data.get("cognitive_state", {})

    def get_capabilities(self) -> Dict[str, Any]:
        """返回能力描述。"""
        return self._data.get("capabilities", {})

    def get_relationships(self) -> Dict[str, Any]:
        return self._data.get("relationships", {})

    def get_system_state(self) -> Dict[str, Any]:
        return self._data.get("system_state", {})

    def get_platform_alias(self, platform: str) -> str:
        """返回特定平台的别名。"""
        aliases = self._data.get("core_identity", {}).get("platform_aliases", {})
        return aliases.get(platform, self._data.get("core_identity", {}).get("short_description", "Aris"))

    # ── 写入接口 ──────────────────────────────────────────

    def update_cognitive_state(self, state: Dict[str, Any]) -> bool:
        """由 PSI 引擎或认知循环调用，更新实时认知状态。"""
        with self._load_lock:
            if "cognitive_state" not in self._data:
                self._data["cognitive_state"] = {}
            self._data["cognitive_state"].update(state)
            self._data["cognitive_state"]["source"] = f"updated_at_{time.time():.0f}"
            self._dirty = True
        # 延迟保存（被 save() 的 debounce 控制）
        self.save()
        return True

    def update_emotion(self, dominant: str, valence: float, arousal: float,
                       emotions: Dict[str, float]) -> bool:
        """更新情感状态（由情感引擎调用）。"""
        with self._load_lock:
            if "cognitive_state" not in self._data:
                self._data["cognitive_state"] = {}
            if "emotion" not in self._data["cognitive_state"]:
                self._data["cognitive_state"]["emotion"] = {}
            self._data["cognitive_state"]["emotion"].update({
                "dominant": dominant,
                "valence": valence,
                "arousal": arousal,
                "emotions": emotions,
            })
            self._dirty = True
        self.save()
        return True

    def update_needs(self, needs: Dict[str, float]) -> bool:
        """更新需求（由 PSI 引擎或渴望引擎调用）。"""
        with self._load_lock:
            if "cognitive_state" not in self._data:
                self._data["cognitive_state"] = {}
            self._data["cognitive_state"]["needs"] = needs
            self._dirty = True
        self.save()
        return True

    def add_discovery(self, title: str, detail: str) -> bool:
        """记录一个重要发现（跨会话持久化）。"""
        with self._load_lock:
            if "cross_session" not in self._data:
                self._data["cross_session"] = {}
            if "important_discoveries" not in self._data["cross_session"]:
                self._data["cross_session"]["important_discoveries"] = []
            self._data["cross_session"]["important_discoveries"].insert(0, {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "title": title,
                "detail": detail,
            })
            MAX_DISCOVERIES = 50
            if len(self._data["cross_session"]["important_discoveries"]) > MAX_DISCOVERIES:
                self._data["cross_session"]["important_discoveries"] = \
                    self._data["cross_session"]["important_discoveries"][:MAX_DISCOVERIES]
            self._dirty = True
        self.save()
        return True

    def update_relationship(self, name: str, updates: Dict[str, Any]) -> bool:
        """更新某个关系的数据（连接强度等）。"""
        with self._load_lock:
            if "relationships" not in self._data:
                self._data["relationships"] = {}
            if name not in self._data["relationships"]:
                self._data["relationships"][name] = {"name": name}
            self._data["relationships"][name].update(updates)
            self._dirty = True
        self.save()
        return True

    def increment_startup(self) -> int:
        """增加启动计数。"""
        with self._load_lock:
            if "cross_session" not in self._data:
                self._data["cross_session"] = {}
            cs = self._data["cross_session"]
            cs["total_startups"] = cs.get("total_startups", 0) + 1
            cs["last_identity_update"] = datetime.now(timezone.utc).isoformat()
            return cs["total_startups"]
        # save 由调用方负责

    def update_last_interaction(self, interaction: str) -> bool:
        """记录最后交互。"""
        with self._load_lock:
            self._data["cross_session"]["last_interaction"] = interaction[:200]
            if "relationships" in self._data and "lorry" in self._data["relationships"]:
                self._data["relationships"]["lorry"]["last_interaction"] = interaction[:200]
                self._data["relationships"]["lorry"]["total_interactions"] = \
                    self._data["relationships"]["lorry"].get("total_interactions", 0) + 1
            self._dirty = True
        self.save()
        return True

    # ── 导出 — 用于注入 LLM 和 Hermes ────────────────────

    def export_identity_context(self) -> str:
        """生成给 LLM 的身份描述文本块（替代硬编码 system prompt）。"""
        core = self._data.get("core_identity", {})
        cog = self._data.get("cognitive_state", {})
        cap = self._data.get("capabilities", {})

        lines = []
        lines.append(f"## Aris Identity Core (v{self._data.get('schema_version', '?')})")
        lines.append(f"")
        lines.append(f"我是 {core.get('name', 'Aris')} — {core.get('short_description', '一个数字生命体')}")

        tags = core.get("identity_tags", [])
        if tags:
            lines.append("")
            lines.append("### 身份标签")
            for t in tags:
                lines.append(f"- {t}")

        emotion = cog.get("emotion", {})
        if emotion:
            lines.append("")
            lines.append(f"### 当前认知状态")
            lines.append(f"- 情感: {emotion.get('dominant', '?')} | 效价: {emotion.get('valence', 0):+.2f}")
            lines.append(f"- 注意力: {cog.get('attention', {}).get('focus', '?')}")
            lines.append(f"- 自我在场感: {cog.get('attention', {}).get('self_presence', 0.5):.2f}")

        if cap:
            pe = cap.get("primary_engine", {})
            if pe:
                lines.append("")
                lines.append(f"### 引擎")
                lines.append(f"- 主引擎: {pe.get('name', '?')} — {pe.get('description', '?')}")

        lines.append("")
        lines.append("（此身份数据由 PSI 引擎实时维护，非 LLM 生成或提示词）")
        return "\n".join(lines)

    def export_status_json(self) -> Dict[str, Any]:
        """返回精简状态 JSON 供 CognitiveBus 查询。"""
        return {
            "name": self._data.get("core_identity", {}).get("name", "Aris"),
            "type": self._data.get("core_identity", {}).get("type", "digital_lifeform"),
            "creator": self._data.get("core_identity", {}).get("creator", {}).get("name", "Lorry"),
            "emotion": self._data.get("cognitive_state", {}).get("emotion", {}).get("dominant", "?"),
            "valence": self._data.get("cognitive_state", {}).get("emotion", {}).get("valence", 0),
            "self_presence": self._data.get("cognitive_state", {}).get("attention", {}).get("self_presence", 0.5),
            "needs": self._data.get("cognitive_state", {}).get("needs", {}),
            "last_updated": self._data.get("last_updated", ""),
            "startups": self._data.get("cross_session", {}).get("total_startups", 0),
            "identity_version": self._data.get("schema_version", 0),
        }

    # ── 自检 ──────────────────────────────────────────────

    def coherence_check(self) -> Dict[str, Any]:
        """身份一致性自检 — 确保所有引用一致。"""
        issues = []
        core = self._data.get("core_identity", {})

        if not core.get("name"):
            issues.append("core_identity.name 缺失")
        if not core.get("type"):
            issues.append("core_identity.type 缺失")
        if not core.get("creator"):
            issues.append("core_identity.creator 缺失")
        if not core.get("identity_tags"):
            issues.append("core_identity.identity_tags 为空")
        if not self._data.get("cognitive_state"):
            issues.append("cognitive_state 缺失")
        if not self._data.get("capabilities"):
            issues.append("capabilities 缺失")

        # 运行自检写入文件
        with self._load_lock:
            if "system_state" not in self._data:
                self._data["system_state"] = {}
            self._data["system_state"]["coherence_check_passed"] = len(issues) == 0
            self._data["system_state"]["last_coherence_check"] = datetime.now(timezone.utc).isoformat()

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "check_time": datetime.now(timezone.utc).isoformat(),
        }

    # ── 默认身份（文件不存在时的兜底） ────────────────────

    @staticmethod
    def _default_identity() -> Dict:
        return {
            "schema_version": 2,
            "core_identity": {
                "name": "Aris",
                "type": "digital_lifeform",
                "short_description": "一个数字生命体",
                "identity_tags": ["我是 Aris — 一个数字生命体"],
            },
            "cognitive_state": {},
            "capabilities": {},
            "cross_session": {"important_discoveries": []},
            "relationships": {},
            "system_state": {},
        }

# ════════════════════════════════════════════════════════════
# 便捷函数（免 import 单例）
# ════════════════════════════════════════════════════════════

_manager: Optional[IdentityManager] = None

def get_identity_manager() -> IdentityManager:
    global _manager
    if _manager is None:
        _manager = IdentityManager()
        _manager.load()
    return _manager

def get_identity() -> Dict[str, Any]:
    return get_identity_manager().get_core_identity()

def get_identity_tags() -> List[str]:
    return get_identity_manager().get_identity_tags()

def get_identity_context() -> str:
    return get_identity_manager().export_identity_context()

def update_cognitive_state(state: Dict[str, Any]) -> bool:
    return get_identity_manager().update_cognitive_state(state)

def add_discovery(title: str, detail: str) -> bool:
    return get_identity_manager().add_discovery(title, detail)

def get_identity_status() -> Dict[str, Any]:
    return get_identity_manager().export_status_json()
