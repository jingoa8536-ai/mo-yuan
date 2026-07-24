"""UI Harness Core — 核心模块入口。"""
from .intent_engine import IntentEngine, IntentResult
from .component_registry import ComponentRegistry, ComponentMeta, get_registry
from .design_token_engine import DesignTokenEngine, DesignTokens, get_engine
