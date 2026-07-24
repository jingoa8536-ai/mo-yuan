"""
LAAP Plugin Loader — 运行时热加载工具/skill
============================================

设计原则（取 Hermes 精华）：
  - 插件是 .py 文件，丢到目录即加载
  - 不需重启，不需注册
  - 每个插件暴露 register(tool_registry) 函数

去糟粕（Hermes 插件体系太重）：
  - 不需要 YAML 配置
  - 不需要 pip install
  - 不需要插件管理器
"""

import sys
import logging
import importlib
import inspect
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from types import ModuleType

logger = logging.getLogger("laap.harness.plugins")


class PluginLoader:
    """插件加载器 — 目录监视 + 热加载。

    用法：
        loader = PluginLoader(registry)
        loader.load_directory("D:/LAAP/harness/plugins")
        loader.load_skill("path/to/skill.py")
    """

    def __init__(self, registry=None):
        self.registry = registry
        self._loaded: Dict[str, ModuleType] = {}
        self._plugin_dirs: List[Path] = []
        self._watcher_active = False

    def load_directory(self, directory: str) -> int:
        """加载目录中的所有插件 .py 文件。"""
        path = Path(directory)
        if not path.exists():
            logger.warning(f"[Plugins] 目录不存在: {directory}")
            return 0

        count = 0
        for f in sorted(path.glob("*.py")):
            if f.name.startswith("_"):
                continue
            if self._load_file(f):
                count += 1

        self._plugin_dirs.append(path)
        logger.info(f"[Plugins] 从 {directory} 加载 {count} 个插件")
        return count

    def load_skill(self, skill_path: str) -> bool:
        """加载单个 skill 文件。"""
        path = Path(skill_path)
        if not path.exists():
            logger.warning(f"[Plugins] Skill 不存在: {skill_path}")
            return False
        return self._load_file(path)

    def _load_file(self, path: Path) -> bool:
        """加载一个 .py 文件作为插件。"""
        try:
            # 动态导入
            spec = importlib.util.spec_from_file_location(
                f"laap_plugin_{path.stem}", path
            )
            if spec is None or spec.loader is None:
                return False

            module = importlib.util.module_from_spec(spec)
            # 缓存旧模块，实现热重载
            old_module = self._loaded.get(path.stem)
            if old_module:
                importlib.reload(module)
            else:
                spec.loader.exec_module(module)

            # 调用插件的 register 函数（如果有）
            if hasattr(module, "register"):
                register_fn = module.register
                if callable(register_fn):
                    if self.registry:
                        register_fn(self.registry)
                        logger.info(f"[Plugins] {path.name}: register() 已调用")
                    else:
                        logger.debug(f"[Plugins] {path.name}: 跳过 register (无 registry)")

            self._loaded[path.stem] = module
            return True

        except Exception as e:
            logger.warning(f"[Plugins] 加载失败 {path.name}: {e}")
            return False

    def reload_all(self) -> int:
        """热重载所有已加载的插件。"""
        count = 0
        for name, module in list(self._loaded.items()):
            try:
                importlib.reload(module)
                if hasattr(module, "register") and self.registry:
                    module.register(self.registry)
                count += 1
            except Exception as e:
                logger.warning(f"[Plugins] 重载失败 {name}: {e}")
        logger.info(f"[Plugins] 热重载 {count} 个插件")
        return count

    @property
    def loaded_plugins(self) -> List[str]:
        return list(self._loaded.keys())

    def summary(self) -> str:
        return f"PL|loaded={len(self._loaded)} dirs={len(self._plugin_dirs)}"
