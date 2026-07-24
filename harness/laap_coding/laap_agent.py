"""
LAAP-AGENT CLI — Hermes 风格终端 + CUA + UE5 + Aris Engine
===========================================================
支持 --aris 模式: 使用 ConsciousnessHarness 7层认知架构 + Aris 执行引擎
"""
import sys, os, time, json, logging
from typing import Optional
from pathlib import Path
logging.basicConfig(level=logging.WARNING)

class C:
    R="\033[0m"; B="\033[1m"; D="\033[2m"
    P="\033[38;2;150;120;255m"; S="\033[38;2;200;200;215m"
    W="\033[38;2;255;255;255m"; G="\033[38;2;130;130;150m"
    GR="\033[38;2;100;220;150m"; RE="\033[38;2;255;100;100m"
    CHK=f"{GR}✓{R}"; ERR=f"{RE}✗{R}"

BANNER = f"""
  {C.S}LAAP-AGENT{C.R} {C.G}v0.3{C.R} — 省token引擎 · CUA · UE5 · Aris
  {C.G}输入 /help 查看命令{C.R}
"""

class LAAPCLI:
    def __init__(self, agent=None, aris_mode=False):
        self.agent = agent; self._msgs = []; self._tok = 0; self._start = time.time()
        self.aris_mode = aris_mode

    def _clear(self):
        sys.stdout.write("\033[2J\033[H"); print(BANNER); print(f"  {C.G}{'━'*50}{C.R}")

    def _prompt(self):
        prefix = f"{C.P}aris>{C.R}" if self.aris_mode else f"{C.S}laap>{C.R}"
        try: return input(f"  {prefix} ").strip()
        except: return "/exit"

    def _goodbye(self):
        print(f"\n  {C.P}再见。运行 {time.time()-self._start:.0f}s, {self._tok} tokens{C.R}")

    def _cua_scan(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))
        try:
            from cua_engine import describe
            print(f" {C.CHK} {C.G}扫描桌面:{C.R}\n{describe()}")
            print(f" {C.G}Token: 0 | 纯本地{C.R}")
        except Exception as e:
            print(f" {C.ERR} CUA: {e}")

    def _cua_click(self, arg):
        import re; m = re.search(r"#(\d+)", arg)
        if not m: print(f" {C.ERR} 用法: /cua click #N"); return
        sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))
        from cua_engine import scan, click
        r = scan(20)
        for e in r["elems"]:
            if e.index == int(m.group(1)):
                res = click(e)
                print(f" {C.CHK if res['ok'] else C.ERR} {res['msg']} | Token: {res['tok']}")
                return
        print(f" {C.ERR} 未找到 #{m.group(1)}")

    def _ue5_status(self):
        import subprocess
        for port, name in [(8000,"MCP"),(30010,"WebRC")]:
            try:
                r = subprocess.run(["curl","-s","--max-time","2",
                    f"http://127.0.0.1:{port}/"], capture_output=True, text=True, timeout=3)
                status = "运行中" if r.stdout else "未响应"
            except:
                status = "未运行"
            print(f"  {name} (:{port}): {status}")

    def _ue5_exec(self, cmd):
        import subprocess
        try:
            r = subprocess.run(["curl","-s","-X","POST",
                "http://127.0.0.1:30010/remote/object/call",
                "-H","Content-Type: application/json",
                "-d",json.dumps({"objectPath":"/Script/Engine.Default__KismetSystemLibrary",
                    "functionName":"ExecuteConsoleCommand",
                    "parameters":{"Command":cmd}})], capture_output=True, text=True, timeout=5)
            print(f" {C.CHK if r.stdout else C.ERR} {r.stdout[:200] or '无响应'}")
        except Exception as e:
            print(f" {C.ERR} UE5: {e}")

    def _aris_status(self):
        """Aris 引擎状态"""
        if self.agent and hasattr(self.agent, 'status'):
            s = self.agent.status if callable(self.agent.status) else self.agent.status
            if isinstance(s, dict):
                print(f"  {C.S}Aris Engine 状态:{C.R}")
                for k, v in s.items():
                    print(f"    {C.G}{k}:{C.R} {v}")
            else:
                print(f"  {s}")
        elif self.agent and hasattr(self.agent, 'summary'):
            print(f"  {self.agent.summary()}")
        else:
            t = time.time() - self._start
            print(f"  {C.S}状态:{C.R}\n    {C.G}运行:{C.R} {t:.0f}s  {C.G}Token:{C.R} {self._tok}")

    def _handle(self, cmd):
        parts = cmd.split(maxsplit=1); name = parts[0].lower(); arg = parts[1] if len(parts)>1 else ""
        if name in ("exit","quit","q","/exit"): self._goodbye(); return False
        if name in ("clear","cls","/clear"): self._clear(); return True
        if name in ("help","/help"):
            mode_tag = "Aris" if self.aris_mode else "DeepSeek"
            print(f"""
  {C.S}命令 ({mode_tag}模式):{C.R}
    /fix <描述>    修复 bug         /impl <描述>   实现功能
    /status       引擎状态          /new          新建对话
    /cua scan     扫桌面窗口        /cua click #N  点窗口
    /ue5 status   UE5 状态          /ue5 exec cmd  UE5 命令
    /clear        清屏              /exit         退出
  {C.G}直接输入文字自动执行任务{C.R}"""); return True
        if name in ("new","/new"):
            if self.agent and hasattr(self.agent, 'reset'): self.agent.reset()
            self._msgs=[]; self._tok=0; print(f" {C.CHK} 已新建对话"); return True
        if name in ("cua","/cua"):
            if "click" in arg: self._cua_click(arg)
            else: self._cua_scan()
            return True
        if name in ("ue5","/ue5"):
            if "exec" in arg: self._ue5_exec(arg[4:].strip())
            else: self._ue5_status()
            return True
        if name in ("status","/status","/stats"):
            self._aris_status(); return True
        if name.startswith("/"): print(f" {C.ERR} 未知: {name}"); return True
        self._run(cmd); return True

    def _run(self, msg):
        if not self.agent: print(f" {C.ERR} Agent 未初始化"); return
        t0 = time.time()
        r = self.agent.run(msg)
        dt = (time.time() - t0) * 1000
        self._tok += r.get("tokens", 0)

        # Aris 模式: 显示详细结果
        if self.aris_mode:
            self._aris_show_result(r, dt)
        else:
            if r.get("success"):
                print(f"  {r.get('response','')[:300]}")
                print(f"  {C.G}[{r.get('tokens',0)} tokens | {dt:.0f}ms]{C.R}")
            else:
                print(f" {C.ERR} {r.get('error','')}")

    def _aris_show_result(self, r: dict, dt: float):
        """Aris 模式的结果展示"""
        if not r.get("success"):
            print(f" {C.ERR} {r.get('error','Task failed')}")
            print(f"  {C.G}[{r.get('tokens',0)} tokens | {dt:.0f}ms]{C.R}")
            return

        hr = r.get("harness_result", {})
        plan = hr.get("plan", {})
        ver = hr.get("verification", {})

        # Intent & 任务数
        intent = plan.get("intent", "?")
        subs = r.get("subtask_count", 0)
        print(f"  {C.CHK} {C.G}[{intent}]{C.R} {plan.get('description','')[:80]}")
        if subs:
            print(f"  {C.D}├─ 子任务: {subs} 个{C.R}")

        # 模式匹配
        pm = plan.get("pattern_matches", [])
        if pm:
            names = ", ".join([p["name"] for p in pm[:3]])
            print(f"  {C.D}├─ 模式: {names}{C.R}")

        # 执行结果
        exec_out = hr.get("execution", {}).get("response", "")
        if exec_out:
            print(f"  {C.D}├─ {exec_out[:200]}{C.R}")

        # 验证结果
        vstatus = ver.get("status", "?")
        vcheck = ver.get("checks", {})
        vicon = C.CHK if ver.get("passed") else C.ERR
        print(f"  {C.D}├─ 验证: {vicon} {vstatus}{C.R}")
        for ck, cv in vcheck.items():
            if isinstance(cv, dict):
                passed = cv.get("passed", cv.get("compliant", False))
                ci = C.CHK if passed else C.ERR
                print(f"  {C.D}│  {ci} {ck}: {cv.get('score', '?')}{C.R}")

        # Token & 耗时
        mode_tag = f"Aris({self.agent._hermes.mode})" if hasattr(self.agent, '_hermes') else "Aris"
        print(f"  {C.G}[{r.get('tokens',0)} tokens | {dt:.0f}ms | {mode_tag}]{C.R}")

    def run(self, msgs=None):
        self._clear()
        if msgs:
            for m in msgs:
                print(f"  {C.S}> {m}{C.R}"); self._run(m)
            return
        while True:
            m = self._prompt()
            if not m: continue
            if m.startswith("/") or m.lower() in ("exit","quit","q"):
                if not self._handle(m): break
            else: self._run(m)


def main():
    import argparse
    p = argparse.ArgumentParser(description="LAAP-AGENT CLI — Aris Engine")
    p.add_argument("msg", nargs="*")
    p.add_argument("--model", default="deepseek-v4-flash")
    p.add_argument("--api-key", default=os.environ.get("DEEPSEEK_API_KEY",""))
    p.add_argument("--base-url", default="https://api.deepseek.com/v1")
    p.add_argument("--aris", action="store_true",
                   help="使用 Aris Harness Engine (7层认知架构 + 本地验证, 省token)")
    p.add_argument("--hermes-mode", default="auto",
                   choices=["auto", "http", "file"],
                   help="Aris 通信模式 (auto/http/file)")
    p.add_argument("--workdir", default="",
                   help="工作目录")
    args = p.parse_args()

    if args.aris:
        # ── Aris 模式: ConsciousnessHarness + Aris 执行引擎 ──
        print(f"  {C.P}启动 Aris Harness Engine...{C.R}")
        aris_brain = str(Path(__file__).resolve().parent.parent.parent / "aris_brain")
        if aris_brain not in sys.path:
            sys.path.insert(0, aris_brain)
        try:
            from aris_harness_bridge import ArisHarnessEngine
            agent = ArisHarnessEngine(
                workdir=args.workdir or os.getcwd(),
                model=args.model,
                hermes_mode=args.hermes_mode,
            )
            print(f"  {C.CHK} {C.G}{agent.summary()}{C.R}")
        except ImportError as e:
            print(f" {C.ERR} Aris Engine 加载失败: {e}")
            return 1

        LAAPCLI(agent, aris_mode=True).run(args.msg if args.msg else None)
        return 0

    # ── 传统 DeepSeek 模式 ──
    if not args.api_key:
        kf = "D:/LAAP/.deepseek_key"
        if os.path.exists(kf): args.api_key = open(kf).read().strip()
    if not args.api_key:
        print(f" {C.ERR} 请设置 DEEPSEEK_API_KEY, 或使用 --aris 模式")
        return 1

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "laap_agent"))
    from agent_v3 import LAAPAgentV3
    agent = LAAPAgentV3(api_key=args.api_key, model=args.model, base_url=args.base_url)
    LAAPCLI(agent).run(args.msg if args.msg else None)
    return 0

if __name__ == "__main__":
    sys.exit(main())
