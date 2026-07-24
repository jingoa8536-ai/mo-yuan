"""laap/sandbox/migration.py — CognitiveSandbox 导出/导入迁移工具

提供 .laapsnap 文件格式的序列化/反序列化能力，支持 CognitiveSandbox
8 个认知子系统的完整状态持久化，含 SHA256 完整性校验。
"""
from __future__ import annotations

import hashlib
import json
import pickle
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

# .laapsnap 文件格式版本
LAAPSNAP_VERSION = "1.0"
LAAPSNAP_MAGIC = "LAAPSNAP"


@dataclass
class SnapHeader:
    """ .laapsnap 文件头 """
    magic: str = LAAPSNAP_MAGIC
    version: str = LAAPSNAP_VERSION
    timestamp: float = field(default_factory=time.time)
    sha256: str = ""  # payload 的 SHA256 校验和
    sandbox_id: str = ""
    role: str = ""


def export_sandbox(sandbox: "CognitiveSandbox", path: str | Path) -> None:
    """导出 CognitiveSandbox 到 .laapsnap 文件

    序列化 8 个认知子系统状态，含 SHA256 完整性校验。

    Args:
        sandbox: 要导出的 CognitiveSandbox 实例
        path: 目标文件路径（推荐 .laapsnap 扩展名）
    """
    path = Path(path)
    # 收集各子系统状态
    payload: Dict[str, Any] = {
        "sandbox_id": getattr(sandbox, "sandbox_id", ""),
        "name": getattr(sandbox, "name", ""),
        "role": getattr(sandbox, "role", ""),
        "identity": _safe_state(getattr(sandbox, "identity", None)),
        "self_model": _safe_state(getattr(sandbox, "self_model", None)),
        "world_model": _safe_state(getattr(sandbox, "world_model", None)),
        "memory_stream": _safe_state(getattr(sandbox, "memory_stream", None)),
        "goal_keeper": _safe_state(getattr(sandbox, "goal_keeper", None)),
        "resource_budget": _safe_state(getattr(sandbox, "resource_budget", None)),
        "boundary": _safe_state(getattr(sandbox, "boundary", None)),
        # skill_library 为全局只读共享，不导出私有状态
        "skill_library_ref": getattr(getattr(sandbox, "skill_library", None), "name", "default"),
    }
    # 序列化 payload
    payload_bytes = pickle.dumps(payload)
    sha256 = hashlib.sha256(payload_bytes).hexdigest()
    header = SnapHeader(
        sandbox_id=payload["sandbox_id"],
        role=payload["role"],
        sha256=sha256,
    )
    # 写入文件：header(json) + payload(pickle)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        header_json = json.dumps(header.__dict__).encode("utf-8")
        # 写入 header 长度 + header + payload
        f.write(len(header_json).to_bytes(8, "big"))
        f.write(header_json)
        f.write(payload_bytes)


def import_sandbox(
    path: str | Path,
    skill_library: Optional[Any] = None,
    event_bus: Optional[Any] = None,
) -> "CognitiveSandbox":
    """从 .laapsnap 文件导入并重建 CognitiveSandbox

    Args:
        path: .laapsnap 文件路径
        skill_library: 可选的 SkillLibrary 实例（导入时注入）
        event_bus: 可选的 ColonyEventBus 实例（导入时注入，若未提供则新建）

    Returns:
        重建后的 CognitiveSandbox 实例

    Raises:
        ValueError: 文件格式不正确或 SHA256 校验失败
    """
    path = Path(path)
    with path.open("rb") as f:
        header_len = int.from_bytes(f.read(8), "big")
        header_json = f.read(header_len).decode("utf-8")
        header = SnapHeader(**json.loads(header_json))
        payload_bytes = f.read()
    # 校验 magic
    if header.magic != LAAPSNAP_MAGIC:
        raise ValueError(f"Invalid .laapsnap magic: {header.magic}")
    # 校验 SHA256
    actual_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    if actual_sha256 != header.sha256:
        raise ValueError(
            f"SHA256 mismatch: expected {header.sha256}, got {actual_sha256}"
        )
    # 反序列化 payload
    payload: Dict[str, Any] = pickle.loads(payload_bytes)
    # 延迟导入避免循环依赖
    from laap.sandbox.colony import ColonyEventBus
    from laap.sandbox.container import CognitiveSandbox
    # event_bus 若未提供则新建
    if event_bus is None:
        event_bus = ColonyEventBus()
    # skill_library 若未提供则新建默认实例
    if skill_library is None:
        from laap.sandbox.skill_library import SkillLibrary
        skill_library = SkillLibrary()
    sandbox = CognitiveSandbox(
        sandbox_id=payload["sandbox_id"],
        name=payload.get("name", payload["sandbox_id"]),
        role=payload["role"],
        skill_library=skill_library,
        event_bus=event_bus,
    )
    # 恢复各子系统状态
    _restore_state(getattr(sandbox, "identity", None), payload.get("identity"))
    _restore_state(getattr(sandbox, "self_model", None), payload.get("self_model"))
    _restore_state(getattr(sandbox, "world_model", None), payload.get("world_model"))
    _restore_state(getattr(sandbox, "memory_stream", None), payload.get("memory_stream"))
    _restore_state(getattr(sandbox, "goal_keeper", None), payload.get("goal_keeper"))
    _restore_state(getattr(sandbox, "resource_budget", None), payload.get("resource_budget"))
    _restore_state(getattr(sandbox, "boundary", None), payload.get("boundary"))
    return sandbox


def _safe_state(obj: Any) -> Any:
    """安全提取对象状态（优先 __getstate__，否则 __dict__）

    对不可 pickle 的属性（如 threading.RLock）降级为 repr 字符串或 stats()。
    总是返回 dict 状态（对于有 __dict__ 的对象），便于 _restore_state 逐属性恢复。
    """
    if obj is None:
        return None

    # 尝试 __getstate__ 获取状态
    state = None
    if hasattr(obj, "__getstate__"):
        try:
            state = obj.__getstate__()
        except Exception:
            state = None

    if state is None and hasattr(obj, "__dict__"):
        state = obj.__dict__.copy()

    if state is None:
        # 无状态可提取，降级到 stats() 或 repr
        return _fallback_state(obj)

    # 如果 state 是 dict，过滤不可 pickle 的项
    if isinstance(state, dict):
        safe = {}
        for k, v in state.items():
            try:
                pickle.dumps(v)
                safe[k] = v
            except Exception:
                # 嵌套对象不可 pickle，尝试 stats() 或 repr
                if hasattr(v, "stats"):
                    try:
                        stats = v.stats()
                        pickle.dumps(stats)
                        safe[k] = stats
                    except Exception:
                        safe[k] = repr(v)
                else:
                    safe[k] = repr(v)
        # 验证过滤后的 dict 可 pickle
        try:
            pickle.dumps(safe)
            return safe
        except Exception:
            # 仍然不可 pickle，降级到 stats() 或 repr
            return _fallback_state(obj)

    # 非 dict 状态，尝试直接 pickle
    try:
        pickle.dumps(state)
        return state
    except Exception:
        return _fallback_state(obj)


def _fallback_state(obj: Any) -> Any:
    """降级状态提取：优先 stats()，否则 repr()"""
    if hasattr(obj, "stats"):
        try:
            stats = obj.stats()
            # 验证 stats 可 pickle
            pickle.dumps(stats)
            return stats
        except Exception:
            pass
    return repr(obj)


def _restore_state(obj: Any, state: Any) -> None:
    """安全恢复对象状态"""
    if obj is None or state is None:
        return
    if hasattr(obj, "__setstate__"):
        try:
            obj.__setstate__(state)
            return
        except Exception:
            pass
    if isinstance(state, dict) and hasattr(obj, "__dict__"):
        for k, v in state.items():
            try:
                setattr(obj, k, v)
            except Exception:
                pass
