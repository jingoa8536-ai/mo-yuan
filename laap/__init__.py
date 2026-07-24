"""LAAP — Living Computation Paradigm / 生命计算范式

PSI 认知架构数字生命体入口包。
运行 `python -m laap` 启动 LAAP 数字生命体。

SDK 入口：
    from laap import AetherClient, LAAPRuntime, ActorSystem, PetriNet
"""

__version__ = "5.0.0"

# ── SDK 核心 API (轻量导入) ──────────────────────────────────────────
from laap.sdk.client import AetherClient          # Client 模式：挂载到外部 Agent
from laap.sdk.runtime import LAAPRuntime          # Framework 模式：独立运行全套 LAAP

# ── 框架核心 (按需导入，惰性加载) ─────────────────────────────────────
def __getattr__(name):
    """Lazy import for framework core to keep SDK import lightning-fast."""
    _lazy = {
        "ActorSystem":       "laap.orchestration.actor",
        "AgentCell":         "laap.orchestration.actor",
        "PetriNet":          "laap.orchestration.petri",
        "PetriPlace":        "laap.orchestration.petri",
        "PetriTransition":   "laap.orchestration.petri",
        "ColoredToken":      "laap.orchestration.petri",
        "TokenColor":        "laap.orchestration.petri",
        "AetherAddress":     "laap.orchestration.primitives",
        "AetherMessage":     "laap.orchestration.primitives",
        "MessageType":       "laap.orchestration.primitives",
        "MessageRouter":     "laap.orchestration.primitives",
        "OrchestrationKernel": "laap.orchestration.kernel",
        "MetaAgent":         "laap.orchestration.meta_agent",
        "Capability":         "laap.orchestration.actor",
        "PSIAgent":          "laap.orchestration.psi",
        "ArisCognitiveBus":  "laap.orchestration.cognitive_bus",
        "seq":               "laap.orchestration.dsl",
        "par":               "laap.orchestration.dsl",
        "act":               "laap.orchestration.dsl",
        "guard":             "laap.orchestration.dsl",
        "loop":              "laap.orchestration.dsl",
        "infer":             "laap.orchestration.dsl",
        "skill":             "laap.orchestration.dsl",
        "compile_workflow":  "laap.orchestration.dsl",
        "LAAPBuilder":       "laap.orchestration.dsl",
    }
    if name in _lazy:
        import importlib
        mod = importlib.import_module(_lazy[name])
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # SDK 核心
    "AetherClient",
    "LAAPRuntime",
    # 框架核心
    "ActorSystem",
    "AgentCell",
    "PetriNet",
    "PetriPlace",
    "PetriTransition",
    "ColoredToken",
    "TokenColor",
    "AetherAddress",
    "AetherMessage",
    "MessageType",
    "MessageRouter",
    "OrchestrationKernel",
    "MetaAgent",
    "Capability",
    "PSIAgent",
    "ArisCognitiveBus",
    # DSL
    "seq", "par", "act", "guard", "loop", "infer", "skill",
    "compile_workflow",
    "LAAPBuilder",
]
