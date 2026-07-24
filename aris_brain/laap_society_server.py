"""已废弃：请使用 laap.api.society_server。

本模块保留为 re-export 直至 2026-12。

迁移说明：
- 路由逻辑已迁移到 ``laap.api.society_server`` 并挂载到主 FastAPI app 的
  ``/society/*`` 路由下（见 ``laap/api/server.py``）。
- 旧的 ``run_server()`` / ``__main__`` 启动入口由 ``laap.api.server.serve``
  统一替代，不再保留独立启动逻辑。
- 旧的复杂端点（``/agents/{id}/perceive``、``/workspace/scan``、
  ``/system/status`` 等）依赖 LAAP 2.0 全套基础设施，已在迁移中简化为
  模块级 ``_society_state`` 状态视图，由 ``set_society_state`` 注入数据。
"""
from __future__ import annotations

import warnings

warnings.warn(
    "aris_brain.laap_society_server is deprecated, use laap.api.society_server instead",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export 新模块的内容
from laap.api.society_server import (  # noqa: E402 (after warning)
    get_society_state,
    router,
    set_society_state,
)

__all__ = ["router", "get_society_state", "set_society_state"]
