"""
LAAP Coding Engine — CLI 的核心引擎
完全独立于 Hermes。
"""

import sys
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("laap.coding.engine")

_LAAP_ROOT = Path("D:/LAAP")
_PATHS = [
    str(_LAAP_ROOT / "laap_agent"),
    str(_LAAP_ROOT / "aris_code_engine"),
    str(Path(__file__).resolve().parent),
    str(_LAAP_ROOT),
]
for p in _PATHS:
    if p not in sys.path:
        sys.path.insert(0, p)


class HarnessEngine:
    """CLI 引擎 — 独立于 Hermes 的核心。"""

    def __init__(self, workdir: Path, token_budget: int = 2000,
                 json_output: bool = False):
        self.workdir = workdir
        self.token_budget = token_budget
        self.json_output = json_output
        self._started_at = time.time()
        self._harness = None
        self._code_planner = None
        self._code_executor = None
        self._plugins = None
        self._cron = None

    def _ensure_harness(self):
        if self._harness is not None:
            return self._harness
        try:
            from harness.laap_coding.core.harness import ConsciousnessHarness
            self._harness = ConsciousnessHarness(
                workdir=str(self.workdir),
                token_budget=self.token_budget,
            )
            logger.info(f"[Engine] Harness: {self._harness.summary()}")
        except Exception as e:
            logger.warning(f"[Engine] Harness 加载失败: {e}")
        return self._harness

    def _ensure_code_engine(self):
        if self._code_planner is not None:
            return self._code_planner
        try:
            from harness.laap_coding.core.harness import PlanningEngine
            self._code_planner = PlanningEngine()
            from harness.laap_coding.core.harness import ExecutionLayer
            self._code_executor = ExecutionLayer(workdir=str(self.workdir))
        except Exception as e:
            logger.warning(f"[Engine] Code engine: {e}")
        return self._code_planner

    def _out(self, data: Dict[str, Any]):
        if self.json_output:
            print(json.dumps(data, ensure_ascii=False))
        else:
            for k, v in data.items():
                if k == "message":
                    icon = "✅" if data.get("status") else "❌"
                    print(f"{icon} {v}")

    def run_dev(self, args) -> int:
        """启动 LAAP-AGENT 交互界面（Hermes 风格）。"""
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from laap_agent import LAAPCLI, LAAPAgent as _Agent
            agent = _Agent(api_key="", model="deepseek-v4-flash")
            cli = LAAPCLI(agent)
            return cli.run()
        except Exception as e:
            print(f"LAAP-AGENT 不可用: {e}")
            harness = self._ensure_harness()
            return self._dev_plain(harness)

    def _dev_plain(self, harness) -> int:
        """简易交互模式（TUI 降级）。"""
        print(f"\n  LAAP Coding — 开发模式")
        print(f"  工作目录: {self.workdir}")
        print(f"  输入 exit 退出\n")
        while True:
            try:
                msg = input(">>> ").strip()
                if not msg:
                    continue
                if msg.lower() in ("exit", "quit", "q"):
                    break
                if msg.lower() == "status":
                    s = harness.status if harness else {}
                    print(f"  引擎状态:")
                    for k, v in s.items():
                        print(f"    {k}: {v}")
                    continue
                t0 = time.time()
                result = harness.run(msg) if harness else {}
                dt = (time.time() - t0) * 1000
                self._out(result)
                print(f"  ({dt:.0f}ms)")
            except (KeyboardInterrupt, EOFError):
                print()
                break
        return 0

    def run_fix(self, args) -> int:
        desc = " ".join(args.description) if args.description else ""
        if not desc:
            print("❌ 请提供 bug 描述")
            return 1
        planner = self._ensure_code_engine()
        if planner:
            from harness.laap_coding.core.harness import TaskContext
            context = TaskContext(
                task_id=f"fix_{int(time.time())}",
                description=desc,
                intent="fix",
                keywords=[],
                constraints=[],
                related_patterns=[],
                project_context={},
            )
            p = planner.plan(context)
            print(f"  计划: {len(p)} 个子任务")
            for i, sub in enumerate(p):
                print(f"    {i+1}. {sub.description}")
        harness = self._ensure_harness()
        if harness:
            result = harness.run(desc, intent="fix")
            self._out(result)
        return 0

    def run_implement(self, args) -> int:
        desc = " ".join(args.description) if args.description else ""
        if not desc:
            print("❌ 请提供功能描述")
            return 1
        print(f"  实现: {desc[:60]}")
        harness = self._ensure_harness()
        if harness:
            result = harness.run(desc, intent="implement")
            self._out(result)
        return 0

    def run_review(self, args) -> int:
        path = Path(args.path).resolve()
        if not path.exists():
            print(f"❌ 路径不存在: {path}")
            return 1
        print(f"  审查: {path}")
        harness = self._ensure_harness()
        if harness:
            result = harness.run(f"审查代码文件: {path}", intent="review")
            self._out(result)
        return 0

    def run_test(self, args) -> int:
        path = Path(args.path).resolve()
        print(f"  测试: {path}")
        if args.gen:
            print(f"  生成模式")
        harness = self._ensure_harness()
        if harness:
            result = harness.run(f"运行测试: {path}", intent="test")
            self._out(result)
        return 0

    def run_status(self, args) -> int:
        harness = self._ensure_harness()
        if harness:
            s = harness.status
            print(f"\n  🔧 LAAP Coding 引擎状态")
            print(f"  运行时间: {s.get('uptime', '0s')}")
            print(f"  对话轮次: {s.get('turns', 0)}")
            print(f"  总 Token: {s.get('total_tokens', 0)}")
            print(f"  消息: {s.get('messages', 0)} 条")
            print(f"  工具: {s.get('tools_loaded', 0)} 个")
            print(f"  \n  🧠 核心层状态:")
            layers = s.get("layers", {})
            for layer_name, status in layers.items():
                print(f"    {layer_name}: {status}")
            print(f"  \n  📊 统计信息:")
            stats = s.get("stats", {})
            for stat_name, value in stats.items():
                print(f"    {stat_name}: {value}")
        else:
            print("❌ Harness 未加载")
        return 0

    def run_init(self, args) -> int:
        template = args.template
        print(f"  初始化 LAAP 工作区: {self.workdir}")
        config_dir = self.workdir / ".laap"
        config_dir.mkdir(parents=True, exist_ok=True)
        config = {"version": "0.2.0", "template": template,
                  "token_budget": self.token_budget,
                  "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        (config_dir / "config.json").write_text(
            json.dumps(config, indent=2, ensure_ascii=False))
        print(f"  ✅ 已创建: {config_dir / 'config.json'}")
        harness = self._ensure_harness()
        if harness:
            state_path = harness.save_state()
            print(f"  ✅ Harness状态已保存: {state_path}")
        return 0
