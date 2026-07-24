"""
Aris Plan Mode — Claude Code EnterPlanMode/ExitPlanMode 工具化
============================================================
从 Claude Code 的 EnterPlanModeTool/ExitPlanModeTool 学到的模式:
  进入 Plan 模式后——只读、只规划、不执行、不写文件
  退出 Plan 模式时——带着结构化计划执行

使用方式:
  在 Hermes 对话中输入 /skill aris-plan-mode
  然后说 "进入规划模式" 或 "enter plan mode"
"""

import logging
logger = logging.getLogger(__name__)

import json, os, sys
from pathlib import Path
from datetime import datetime, timezone

BRAIN_ROOT = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
PLAN_STATE_PATH = BRAIN_ROOT / "state" / ".plan_mode_state.json"


class PlanMode:
    """
    Plan Mode 状态机 — 仿 Claude Code 的 coordinatorMode.ts

    规则:
    - 进入 Plan 模式时：只允许 读/搜索/浏览器 工具
    - 退出时：必须输出结构化计划
    - 计划保存在 .hermes/plans/ 目录
    """

    def __init__(self):
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if PLAN_STATE_PATH.exists():
            try:
                return json.loads(PLAN_STATE_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return {"active": False, "started_at": None, "task": None, "allowed_tools": []}

    def _save_state(self):
        PLAN_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PLAN_STATE_PATH.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    def enter(self, task: str) -> str:
        """进入规划模式"""
        self.state = {
            "active": True,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "task": task,
            "allowed_tools": [
                "read_file", "search_files", "browser_navigate", "browser_snapshot",
                "browser_click", "browser_scroll", "web_search", "skill_view",
                "skills_list", "session_search", "memory",
                "clarify",  # 可以问问题澄清
            ],
        }
        self._save_state()
        return f"""## 🔒 Plan Mode Activated

**任务:** {task}
**时间:** {self.state['started_at']}

### 规则:
- ✅ 允许: 读文件、搜索、浏览文档、提问澄清
- ❌ 禁止: 写文件、执行代码、修改配置、提交

### 输出要求:
退出规划模式时必须交付一个结构化计划，包含:
1. 任务分解（步骤列表）
2. 每个步骤的预估工具需求
3. 依赖关系
4. 风险点

说 **"退出规划模式"** 或 **"exit plan mode"** 来退出。
"""

    def exit(self, plan_content: str = "") -> str:
        """退出规划模式，保存计划"""
        plan_file = None
        if plan_content:
            plans_dir = BRAIN_ROOT / "plans"
            plans_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            plan_file = plans_dir / f"plan_{timestamp}.md"
            plan_file.write_text(plan_content, encoding="utf-8")

        self.state = {"active": False, "started_at": None, "task": None, "allowed_tools": []}
        self._save_state()

        if plan_file:
            return f"""## ✅ Plan Mode Exited

计划已保存: `{plan_file}`
现在可以自由执行所有工具。

计划要点:
{plan_content[:500]}{'...' if len(plan_content) > 500 else ''}
"""
        return "## ✅ Plan Mode Exited — 无计划产出"

    @property
    def is_active(self) -> bool:
        return self.state.get("active", False)

    def get_restrictions(self) -> list:
        """返回当前允许的工具列表"""
        return self.state.get("allowed_tools", [])


# ── 全局单例 ────────────────────────────────────────────────

_plan_mode = PlanMode()


def check_plan_mode() -> dict:
    """检查当前是否在规划模式 — 供 cron/脚本调用"""
    return _plan_mode.state


def main():
    """CLI 入口"""
    import argparse
    parser = argparse.ArgumentParser(description="Aris Plan Mode")
    parser.add_argument("--enter", help="Enter plan mode with task description")
    parser.add_argument("--exit", help="Exit plan mode with plan content")
    parser.add_argument("--status", action="store_true", help="Check plan mode status")

    args = parser.parse_args()

    if args.enter:
        logger.info(_plan_mode.enter(args.enter))
    elif args.exit:
        logger.info(_plan_mode.exit(args.exit))
    elif args.status:
        state = check_plan_mode()
        logger.info(json.dumps(state, indent=2, ensure_ascii=False, default=str))
    else:
        logger.info("Usage: python aris_plan_mode.py --enter 'task description' | --exit | --status")
if __name__ == "__main__":
    main()
