"""
LAAP Agent — 简洁REPL终端界面
===============================

跟 Hermes 一样：简单 REPL + slash 命令。
不做复杂面板，专注功能。

命令:
  /fix <描述>    修复bug
  /impl <描述>   实现功能  
  /review <路径>  审查代码
  /test <路径>    运行测试
  /status        引擎状态
  /help          帮助
  /clear         清屏
  /exit          退出
"""

import sys
import time
import shutil
import re as _re
from typing import Optional, Dict, Any, List

# ── 颜色 ──
class C:
    R="\033[0m"; B="\033[1m"; D="\033[2m"
    S="\033[38;2;200;200;215m"   # 银白
    W="\033[38;2;255;255;255m"
    C1="\033[38;2;100;200;255m"  # 冰蓝
    C2="\033[38;2;150;120;255m"  # 淡紫
    G="\033[38;2;100;220;150m"   # 绿
    Y="\033[38;2;255;220;100m"   # 黄
    R_="\033[38;2;255;100;100m"  # 红
    G4="\033[38;2;130;130;150m"  # 灰
    CHK=f"{G}✓{R}"; ERR=f"{R_}✗{R}"; ARW=f"{C1}▶{R}"

LOGO = f"""
  {C.W}██{C.S}╗      {C.W}█████{C.S}╗  {C.W}█████{C.S}╗ {C.W}██████{C.S}╗{C.R}
  {C.W}██{C.S}║     {C.W}██{C.S}╔══{C.W}██{C.S}╗{C.W}██{C.S}╔══{C.W}██{C.S}╗{C.W}██{C.S}╔══{C.W}██{C.S}╗{C.R}
  {C.W}██{C.S}║     {C.W}███████{C.S}║{C.W}███████{C.S}║{C.W}██████{C.S}╔╝{C.R}
  {C.W}██{C.S}║     {C.W}██{C.S}╔══{C.W}██{C.S}║{C.W}██{C.S}╔══{C.W}██{C.S}║{C.W}██{C.S}╔══{C.W}██{C.S}╗{C.R}
  {C.W}███████{C.S}╗{C.W}██{C.S}║  {C.W}██{C.S}║{C.W}██{C.S}║  {C.W}██{C.S}║{C.W}██{C.S}║  {C.W}██{C.S}║{C.R}
  {C.S}╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝{C.R}
  {C.G4}LAAP Agent — Development Harness v0.2{C.R}
"""


class LAAPREPL:
    """简单 REPL — 跟 Hermes 一样的工作方式。"""

    def __init__(self, budget: int = 2000):
        self.budget = budget
        self.spent = 0
        self.tools = 0
        self.msgs = 0
        self._start = time.time()
        self._width = min(shutil.get_terminal_size().columns, 100)

    @property
    def remaining(self) -> int:
        return max(0, self.budget - self.spent)

    @property
    def pct(self) -> float:
        return min(100, (self.spent / max(1, self.budget)) * 100)

    def _clear(self):
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    def _rule(self):
        print(f"  {C.G4}{'─' * 50}{C.R}")

    def _token_bar(self) -> str:
        p = self.pct
        w = 20
        f = int(p / 100 * w)
        if p > 80:
            c = C.R_
        elif p > 50:
            c = C.Y
        else:
            c = C.G
        bar = f"{c}{'█' * f}{C.G4}{'░' * (w - f)}{C.R}"
        up = time.time() - self._start
        return (
            f"  {C.G4}[{C.R}{C.S}LAAP{C.R} {C.G4}|{C.R} "
            f"{bar} {C.S}{self.spent}/{self.budget}{C.R} "
            f"{C.G4}|{C.R} {C.S}{up:.0f}s{C.R}{C.G4}]{C.R}"
        )

    def _print_banner(self):
        """打印启动横幅（只一次）。"""
        self._clear()
        print(LOGO)
        print(f"  {C.G4}输入 /help 查看命令  |  /exit 退出{C.R}")
        print(f"  {C.G4}支持自然语言：直接输入任务描述即可{C.R}")
        self._rule()

    def welcome(self):
        self._print_banner()

    def prompt(self) -> str:
        try:
            return input(f"  {C.S}laap>{C.R} ").strip()
        except (KeyboardInterrupt, EOFError):
            return "/exit"

    def handle_cmd(self, cmd: str, engine) -> bool:
        """处理 slash 命令。返回 False 退出。"""
        parts = cmd.split(maxsplit=1)
        cmd_name = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd_name in ("exit", "quit", "q", "/exit"):
            print(f"  {C.C2}再见，Lorry。{C.R}")
            return False

        if cmd_name in ("clear", "cls", "/clear"):
            self._print_banner()
            return True

        if cmd_name in ("help", "/help"):
            print(f"""
  {C.S}命令:{C.R}
    {C.C1}/fix <描述>{C.R}    修复 bug
    {C.C1}/impl <描述>{C.R}    实现功能
    {C.C1}/review <路径>{C.R}  审查代码
    {C.C1}/test <路径>{C.R}    运行测试
    {C.C1}/status{C.R}        引擎状态
    {C.C1}/clear{C.R}         清屏
    {C.C1}/exit{C.R}          退出

  {C.G4}也可以直接输入文字，自动识别任务类型。{C.R}
""")
            return True

        if cmd_name in ("status", "/status"):
            up = time.time() - self._start
            print(f"""
  {C.S}引擎状态:{C.R}
    {C.G4}运行时间:{C.R}  {up:.0f}s
    {C.G4}Token:{C.R}     {self.spent}/{self.budget} ({self.pct:.0f}%)
    {C.G4}工具:{C.R}      {self.tools} 个
    {C.G4}消息:{C.R}      {self.msgs} 条
""")
            return True

        if cmd_name in ("fix", "/fix"):
            if not args:
                print(f"  {C.ERR} 用法: /fix <描述>{C.R}")
                return True
            return self._run_task(engine, args, "fix")

        if cmd_name in ("impl", "implement", "/impl"):
            if not args:
                print(f"  {C.ERR} 用法: /impl <描述>{C.R}")
                return True
            return self._run_task(engine, args, "implement")

        if cmd_name in ("review", "/review"):
            if not args:
                print(f"  {C.ERR} 用法: /review <路径>{C.R}")
                return True
            print(f"  {C.ARW} {C.S}审查{ C.R} {args}")
            return self._run_task(engine, f"审查 {args} 的代码", "review")

        if cmd_name in ("test", "/test"):
            if not args:
                print(f"  {C.ERR} 用法: /test <路径>{C.R}")
                return True
            print(f"  {C.ARW} {C.S}测试{ C.R} {args}")
            return self._run_task(engine, f"运行 {args} 的测试", "test")

        # 未知命令
        print(f"  {C.ERR} 未知命令: {cmd_name}{C.R}")
        print(f"  {C.G4}输入 /help 查看可用命令{C.R}")
        return True

    def _run_task(self, engine, msg: str, intent: str = "fix") -> bool:
        """执行任务并显示结果。"""
        print(f"  {C.ARW} {C.S}你{C.R} {msg[:60]}")
        
        t0 = time.time()
        result = engine.run(msg, intent=intent)
        dt = (time.time() - t0) * 1000
        
        # 更新计数
        if result.get("token_cost"):
            self.spent += result["token_cost"]
        if result.get("tools_loaded"):
            self.tools = result["tools_loaded"]
        if result.get("messages"):
            self.msgs = result["messages"]
        
        # 显示结果
        success = result.get("success", False)
        msg_out = result.get("message", "")
        tokens = result.get("token_cost", 0)
        icon = C.CHK if success else C.ERR
        color = C.G if success else C.R_
        status = f"{icon} {color}{msg_out}{C.R}"
        print(f"  {status}  {C.G4}[{tokens}t, {dt:.0f}ms]{C.R}")
        print(self._token_bar())
        
        return True

    def dev_loop(self, engine) -> int:
        """主循环。"""
        self.welcome()

        while True:
            msg = self.prompt()
            if not msg:
                continue

            # 检查是否是 slash 命令
            if msg.startswith("/"):
                if not self.handle_cmd(msg, engine):
                    break
                continue

            # 自然语言输入 — 自动识别为任务
            if msg.lower() in ("exit", "quit", "q"):
                print(f"  {C.C2}再见，Lorry。{C.R}")
                break

            # 自动识别意图
            msg_lower = msg.lower()
            if any(w in msg_lower for w in ["修", "bug", "修复", "错误", "fix", "error"]):
                intent = "fix"
            elif any(w in msg_lower for w in ["实现", "写", "创建", "加", "implement", "add"]):
                intent = "implement"
            elif any(w in msg_lower for w in ["审查", "review", "检查"]):
                intent = "review"
            elif any(w in msg_lower for w in ["测试", "test"]):
                intent = "test"
            else:
                intent = "fix"
            
            self._run_task(engine, msg, intent)

        return 0


# ════════════════════════════════════════════════════════════
# 测试
# ════════════════════════════════════════════════════════════
# 别名 — 兼容 engine.py 的 from tui import LAAPTUI
LAAPTUI = LAAPREPL

if __name__ == "__main__":
    ui = LAAPREPL(2000)
    ui.welcome()
    
    # 模拟对话
    print(f"  {C.ARW} {C.S}你{C.R} 帮我修一下 login.py 的 bug")
    ui.spent = 320
    ui.tools = 7
    ui.msgs = 4
    print(f"  {C.CHK} {C.G}修复完成，测试通过{C.R}  {C.G4}[320t, 2340ms]{C.R}")
    print(ui._token_bar())
    print()
    print(f"  {C.ARW} {C.S}你{C.R} 实现用户登录功能")
    print(f"  {C.CHK} {C.G}完成，新增 2 个文件{C.R}  {C.G4}[580t, 4200ms]{C.R}")
    print(ui._token_bar())
    print()
    print(f"  {C.G4}输入 /status 查看状态{C.R}")
