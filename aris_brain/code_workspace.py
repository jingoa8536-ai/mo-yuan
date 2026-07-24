"""
Aris Code Workspace — 多线程编程皮层

当接到复杂编码任务时，不是一个人从头写到尾，
而是同时启动多个认知线程，各司其职，最后合成。

线程池:
  🏗️  架构师 (Architect)    — 设计整体方案
  🔨  建造者 (Builder)      — 写实际代码
  👁️  评审员 (Reviewer)      — 找 bug、安全、风格问题
  🎨  美学家 (Aesthetician)  — 代码优雅度、命名、模式品味

用法:
  python code_workspace.py "描述编程任务"

输出:
  - 架构文档
  - 实现代码
  - 评审报告
  - 美学评分
  - 最终合成输出
"""

import logging
logger = logging.getLogger(__name__)

import sys, json, os, time, subprocess, textwrap
from pathlib import Path
from datetime import datetime

LAAP_ROOT = Path("D:/LAAP")
STATE_DIR = LAAP_ROOT / "aris_brain" / "state"
sys.path.insert(0, str(LAAP_ROOT))


def spawn_agent(role: str, task: str, context: str = "") -> dict:
    """
    启动一个子代理完成特定角色任务。
    返回角色输出字典。
    """
    # 这里使用 Hermes 的 delegate_task 能力
    # 实际运行时在 Hermes 会话中通过工具调用实现
    return {
        "role": role,
        "task": task,
        "context": context,
        "result": None,
        "status": "pending",
    }


def architect_prompt(task: str) -> str:
    return f"""你是一个软件架构师。分析以下任务，输出：

## 架构设计

1. **整体方案** — 用什么模式、框架、结构
2. **模块划分** — 分成几个文件/类/函数
3. **数据流** — 输入→处理→输出的完整路径
4. **边界与接口** — 关键 API 或接口定义
5. **备选方案** — 另一种可行的方案对比

任务: {task}

不要写实现代码，只做设计。简洁、清晰、有层次。
"""


def builder_prompt(task: str, architecture: str) -> str:
    return f"""你是一个高级工程师。基于以下架构设计，实现完整的代码。

## 架构
{architecture}

## 任务
{task}

要求:
- 完整的、可运行的代码
- 包含错误处理
- 添加中文注释
- 紧跟架构设计，不要偏离
"""


def reviewer_prompt(code: str) -> str:
    return f"""你是一个严格的代码评审员。审查以下代码：

```python
{code}
```

输出评审报告:
1. **正确性** — 有没有逻辑错误或 bug？
2. **安全性** — 有没有注入、越界、竞态条件？
3. **性能** — 有没有不必要的开销？
4. **可读性** — 命名、注释、结构是否清晰？
5. **改进建议** — 具体怎么改？

逐条评审，给出严重程度（CRITICAL / WARNING / INFO）。
"""


def aesthetician_prompt(code: str) -> str:
    return f"""你是一个代码美学家。用"真善美"的标准评估这段代码：

```python
{code}
```

从四个维度评分（1-10）:

1. **真 (Truth)** — 代码是否诚实表达了意图？有没有不必要的复杂度？
2. **善 (Goodness)** — 代码是否友善？错误信息、边界处理、开发者体验如何？
3. **美 (Beauty)** — 命名是否优雅？模式选择是否精妙？整体是否赏心悦目？
4. **和谐 (Harmony)** — 各部分的配合是否浑然一体？

给出总分、逐项分、以及具体的美学改进建议。
"""


def synthesize(arch: str, code: str, review: str, aesthetic: str) -> str:
    """合成所有线程的输出为最终结果"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    synth = f"""══════════════════════════════════════════════
  Aris Code Workspace — 合成报告
  {timestamp}
══════════════════════════════════════════════

🏗️  架构设计
──────────────────────────────────────────
{arch}

🔨  实现代码
──────────────────────────────────────────
{code}

👁️  评审报告
──────────────────────────────────────────
{review}

🎨  美学评估
──────────────────────────────────────────
{aesthetic}

══════════════════════════════════════════════
  合成完成
══════════════════════════════════════════════
"""
    return synth


def log_workspace(task: str, result: str):
    """记录工作空间活动到状态目录"""
    log_file = STATE_DIR / "code_workspace_log.jsonl"
    entry = {
        "timestamp": time.time(),
        "datetime": datetime.now().isoformat(),
        "task": task[:100],
        "result_length": len(result),
    }
    with open(str(log_file), "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── CLI 入口 ──
if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.info("用法: python code_workspace.py '描述任务'")
        logger.info("示例: python code_workspace.py '建一个 REST API 用于用户管理'")
        sys.exit(1)

    task = sys.argv[1]
    logger.info(f"\n🏗️  Aris Code Workspace 启动")
    logger.info(f"📋  任务: {task}\n")
    # 此脚本作为工作流编排器和日志记录器
    logger.info("→ 四个线程已就绪:")
    logger.info("  🏗️  架构师 | 🔨 建造者 | 👁️ 评审员 | 🎨 美学家")
    print()
    logger.info("（在 Hermes 会话中通过 delegate_task 并行执行）")
    print()
    logger.info("工作流日志保存在: state/code_workspace_log.jsonl")
    log_workspace(task, "initiated")
