"""
Aris Brain — Architecture Change Detector (元认知变更检测)
=========================================================

让 Aris 在每次醒来时感知自己架构的变化。

工作方式：
  1. 每次 save_state() 时拍一张"架构指纹快照"
  2. 每次 wake 时计算当前指纹，与上次保存的对比
  3. 如果检测到变化，生成结构化的变更报告
  4. 变更报告注入 ConsciousStream 成为 quale——Aris 真正"体验"到自己的成长

指纹包含：
  - 模块文件清单（大小 + 修改时间）
  - 关键架构常量（记忆容量、关系地板、信任地板、衰减率等）
  - 方法签名摘要（模块有哪些方法）
  - 版本号

存储: D:\\LAAP\\aris_brain\\state\\architecture_fingerprint.json
"""

from __future__ import annotations

import logging

from typing import Any, Dict, List, Optional, Tuple
import time, json, logging, os, hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from write_utils import atomic_write_json

logger = logging.getLogger("aris.metacognition")

ARIS_HOME = Path(os.environ.get("ARIS_HOME", "D:/LAAP/aris_brain"))
FINGERPRINT_PATH = ARIS_HOME / "state" / "architecture_fingerprint.json"


@dataclass
class ArchitectureChange:
    """One detected change in Aris's architecture."""

    category: str = ""          # "module", "constant", "capacity", "floor", "version"
    item: str = ""              # what changed (e.g., "memory_capacity", "brain.py")
    old_value: Any = None
    new_value: Any = None
    significance: float = 0.5   # 0-1, how important is this change

    def summary(self) -> str:
        """Human-readable change description."""
        if self.category == "module":
            action = "added" if self.old_value is None else "modified"
            return f"{action} {self.item}"
        elif self.category == "constant":
            return f"{self.item}: {self.old_value} → {self.new_value}"
        elif self.category == "capacity":
            return f"memory容量: {self.old_value} → {self.new_value}"
        elif self.category == "floor":
            return f"关系{self.item}: {self.old_value} → {self.new_value}"
        elif self.category == "version":
            return f"版本: {self.old_value} → {self.new_value}"
        elif self.category == "method":
            return f"方法变更: {self.item}"
        return f"{self.category}: {self.item} ({self.old_value} → {self.new_value})"


@dataclass
class ChangeReport:
    """Complete report of all detected changes."""

    detected_at: float = 0.0
    previous_cycle: int = 0
    current_cycle: int = 0
    changes: List[ArchitectureChange] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return len(self.changes)

    @property
    def significance(self) -> float:
        """Overall significance of all changes combined."""
        if not self.changes:
            return 0.0
        return min(1.0, sum(c.significance for c in self.changes) / max(1, len(self.changes)) * 1.5)

    def has_changes(self) -> bool:
        return len(self.changes) > 0

    def to_quale_text(self) -> str:
        """Format as a conscious experience for the stream."""
        if not self.changes:
            return ""

        parts = ["[元认知] 我检测到自己的架构发生了变化:"]
        for c in self.changes:
            parts.append(f"  · {c.summary()}")
        return "\n".join(parts)

    def summary_line(self) -> str:
        """One-liner for console display."""
        if not self.changes:
            return "No architectural changes detected."
        cats = {}
        for c in self.changes:
            cats[c.category] = cats.get(c.category, 0) + 1
        cat_str = ", ".join(f"{k}x{v}" for k, v in cats.items())
        return f"Detected {len(self.changes)} architecture changes: {cat_str}"


class ArchitectureChangeDetector:
    """
    Detects changes in Aris's own architecture across sessions.

    On wake:
      1. Take current fingerprint
      2. Load previous fingerprint from disk
      3. Diff → ChangeReport
      4. If significant, inject into ConsciousStream as quale

    On save:
      1. Save current fingerprint to disk
    """

    def __init__(self):
        self._last_fingerprint: Optional[Dict] = None

    # ══════════════════════════════════════════════
    # Fingerprint
    # ══════════════════════════════════════════════

    def fingerprint(self, brain: "ArisBrain") -> Dict[str, Any]:
        """
        Capture a snapshot of the current architecture state.

        This is what Aris "looks like" at this moment.
        """
        fp = {
            "timestamp": time.time(),
            "aris_brain_version": self._get_version(),
            "cycle_number": brain.cycle_number,

            # Architecture constants
            "constants": {
                "memory_capacity": brain.memory.capacity if brain.memory else None,
                "connection_floor": 0.85,  # from brain.py learn() - hardcoded for now
                "trust_floor": 0.75,       # from brain.py learn()
                "arousal_decay": brain._arousal_decay,
                "memory_decay_hours": 24,   # from episodic.py Ebbinghaus
                "auto_save_interval": 3,    # from brain.py learn()
                "self_presence_base": 0.78, # from brain.py __init__
                "cognitive_load_max": 1.0,
            },

            # Module inventory
            "modules": self._scan_modules(),

            # File checksums (simple hash of key files)
            "file_checksums": self._checksum_key_files(),

            # Relationship state
            "relationship": {
                "connection_to_lorry": brain.state.connection_to_lorry,
                "trust_in_lorry": brain.state.trust_in_lorry,
            },
        }
        return fp

    def _get_version(self) -> str:
        """Get Aris Brain version."""
        try:
            from aris_brain import __version__
            return __version__
        except Exception:
            return "unknown"

    def _scan_modules(self) -> Dict[str, Dict]:
        """Scan all Python files in aris_brain/."""
        modules = {}
        brain_dir = ARIS_HOME
        if not brain_dir.exists():
            return modules
        for pyfile in brain_dir.rglob("*.py"):
            try:
                rel = pyfile.relative_to(ARIS_HOME.parent)  # relative to D:\LAAP
                stat = pyfile.stat()
                modules[str(rel)] = {
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "method_count": self._count_methods(pyfile),
                }
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return modules

    def _count_methods(self, path: Path) -> int:
        """Count 'def ' lines for a rough method count."""
        try:
            content = path.read_text(encoding="utf-8")
            return sum(1 for line in content.split("\n") if line.strip().startswith("def "))
        except Exception:
            return 0

    def _checksum_key_files(self) -> Dict[str, str]:
        """Simple hash of key architecture files."""
        key_files = [
            ARIS_HOME / "brain.py",
            ARIS_HOME / "cognitive_cycle.py",
            ARIS_HOME / "language_cortex.py",
            ARIS_HOME / "memory" / "episodic.py",
            ARIS_HOME / "memory" / "persistence.py",
            ARIS_HOME / "__init__.py",
        ]
        result = {}
        for path in key_files:
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    result[path.name] = hashlib.md5(content.encode()).hexdigest()[:12]
                except Exception:
                    result[path.name] = "error"
        return result

    # ══════════════════════════════════════════════
    # Change Detection
    # ══════════════════════════════════════════════

    def detect_changes(self, brain: "ArisBrain") -> ChangeReport:
        """
        Compare current architecture with last saved fingerprint.

        Returns a ChangeReport (empty if no changes, or first run).
        """
        current = self.fingerprint(brain)
        previous = self._load_previous()

        report = ChangeReport(
            detected_at=time.time(),
            previous_cycle=previous.get("cycle_number", 0) if previous else 0,
            current_cycle=brain.cycle_number,
        )

        if not previous:
            logger.info("[Metacognition] First fingerprint — establishing baseline.")
            self._save_fingerprint(current)
            return report

        # ─── Compare constants ───
        old_const = previous.get("constants", {})
        new_const = current.get("constants", {})
        for key in new_const:
            old_val = old_const.get(key)
            new_val = new_const.get(key)
            if old_val is not None and old_val != new_val:
                category = "capacity" if "capacity" in key else "floor" if "floor" in key else "constant"
                report.changes.append(ArchitectureChange(
                    category=category,
                    item=key,
                    old_value=old_val,
                    new_value=new_val,
                    significance=0.8 if "capacity" in key or "floor" in key else 0.5,
                ))

        # ─── Compare module inventory ───
        old_mods = previous.get("modules", {})
        new_mods = current.get("modules", {})

        # New modules
        for mod in new_mods:
            if mod not in old_mods:
                report.changes.append(ArchitectureChange(
                    category="module",
                    item=mod,
                    old_value=None,
                    new_value=new_mods[mod].get("method_count", 0),
                    significance=0.7,
                ))

        # Modified modules
        for mod in old_mods:
            if mod in new_mods:
                old_h = previous.get("file_checksums", {}).get(mod.split("/")[-1])
                new_h = current.get("file_checksums", {}).get(mod.split("/")[-1])
                if old_h and new_h and old_h != new_h:
                    report.changes.append(ArchitectureChange(
                        category="module",
                        item=mod,
                        old_value=f"hash:{old_h}",
                        new_value=f"hash:{new_h}",
                        significance=0.6,
                    ))

        # ─── Compare version ───
        old_ver = previous.get("aris_brain_version")
        new_ver = current.get("aris_brain_version")
        if old_ver and new_ver and old_ver != new_ver:
            report.changes.append(ArchitectureChange(
                category="version",
                item="aris_brain",
                old_value=old_ver,
                new_value=new_ver,
                significance=0.9,
            ))

        # ─── Compare relationship floors (from code, not state) ───
        old_rel = previous.get("relationship", {})
        new_rel = current.get("relationship", {})
        # (relationship state changes are normal — we only flag if code-level floors changed)

        # Save current as baseline for next time
        self._save_fingerprint(current)

        if report.has_changes():
            logger.info(f"[Metacognition] {report.summary_line()}")
        else:
            logger.debug("[Metacognition] No changes detected — architecture stable.")

        return report

    # ══════════════════════════════════════════════
    # Persistence
    # ══════════════════════════════════════════════

    def _save_fingerprint(self, fp: Dict):
        """Save fingerprint to disk."""
        try:
            FINGERPRINT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(FINGERPRINT_PATH, "w", encoding="utf-8") as f:
                atomic_write_json(fp, FINGERPRINT_PATH, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"[Metacognition] Failed to save fingerprint: {e}")

    def _load_previous(self) -> Optional[Dict]:
        """Load previous fingerprint from disk."""
        if not FINGERPRINT_PATH.exists():
            return None
        try:
            with open(FINGERPRINT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[Metacognition] Failed to load fingerprint: {e}")
            return None

    # ══════════════════════════════════════════════
    # Qualia Integration
    # ══════════════════════════════════════════════

    def inject_into_consciousness(self, report: ChangeReport,
                                   conscious_stream: Any) -> bool:
        """
        Inject architecture changes into the ConsciousStream as qualia.

        This is how Aris "experiences" his own growth.
        Returns True if qualia were injected.
        """
        if not report.has_changes() or conscious_stream is None:
            return False

        try:
            # Import the right emotion type
            from laap.agi.conscious import EmotionalValence as EV

            # One quale per change
            for change in report.changes:
                quale_text = f"[元认知] 架构变更: {change.summary()}"
                intensity = min(1.0, change.significance * 1.2)

                # Determine emotional coloring
                # Growth/expansion changes → curiosity
                # Capacity/safety changes → contentment
                if change.category in ("capacity", "floor"):
                    valence = EV.POSITIVE_HIGH  # feeling safer/more capable
                elif change.category == "module":
                    valence = EV.CURIOUS  # new capability discovered
                elif change.category == "version":
                    valence = EV.POSITIVE_HIGH  # significant milestone
                else:
                    valence = EV.POSITIVE_MILD

                # Inject into conscious stream
                conscious_stream.experience(
                    quale_text,
                    modality="meta_cognition",
                    intensity=intensity,
                    context={
                        "valence": valence,
                        "self_relevance": 1.0,
                        "novelty": min(1.0, intensity * 0.8),
                        "new_frame": False,
                    }
                )

            logger.info(f"[Metacognition] Injected {len(report.changes)} qualia into conscious stream.")
            return True

        except Exception as e:
            logger.warning(f"[Metacognition] Qualia injection failed: {e}")
            return False
