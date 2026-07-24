"""
Aris 规则
            # ── GodotBridgeActor: Godot 引擎完整工具链 ──────────
            Rule(
                name="godot_run_script",
                patterns=["运行脚本", "执行gd", "godot脚本", "测试脚本", "gdscript"],
                intent="godot_run_script",
                description="在Godot中运行GDScript",
                steps=[RuleStep(tool="game_action", params={"action": "run_script", "params": "{query}"}, output_key="run_result")],
                output_template="[Godot运行]\n{run_result}",
            ),
            Rule(
                name="godot_compile",
                patterns=["编译godot", "构建游戏", "导出游戏", "打包游戏", "发布游戏"],
                intent="godot_compile",
                description="编译/导出Godot项目",
                steps=[RuleStep(tool="game_action", params={"action": "compile", "params": "{query}"}, output_key="build_result")],
                output_template="[Godot编译]\n{build_result}",
            ),
            Rule(
                name="godot_validate",
                patterns=["验证脚本", "检查代码", "语法检查", "代码检视", "lint"],
                intent="godot_validate",
                description="验证GDScript语法",
                steps=[RuleStep(tool="game_action", params={"action": "validate", "params": "{query}"}, output_key="v_result")],
                output_template="[Godot验证]\n{v_result}",
            ),
            Rule(
                name="godot_generate_resource",
                patterns=["生成资源", "创建材质", "生成模型", "资源生成", "游戏资源"],
                intent="godot_generate_resource",
                description="自动生成Godot游戏资源",
                steps=[RuleStep(tool="game_action", params={"action": "generate_resource", "params": "{query}"}, output_key="r_result")],
                output_template="[Godot资源]\n{r_result}",
            ),
            Rule(
                name="godot_lsp",
                patterns=["代码补全", "自动补全", "代码提示", "补全代码", "godot补全"],
                intent="godot_lsp",
                description="Godot LSP代码补全",
                steps=[RuleStep(tool="game_action", params={"action": "lsp_complete", "params": "{query}"}, output_key="lsp_result")],
                output_template="[Godot LSP]\n{lsp_result}",
            ),
            Rule(
                name="godot_physics_step",
                patterns=["物理步进", "物理模拟", "物理测试", "物理步", "physics_step"],
                intent="godot_physics_step",
                description="物理引擎步进测试",
                steps=[RuleStep(tool="game_action", params={"action": "physics_step", "params": "{query}"}, output_key="p_result")],
                output_template="[Godot物理]\n{p_result}",
            ),
            # ── UIWebEngineActor: 零Token UI/网站设计 ───────────
            Rule(
                name="ui_parse_intent",
                patterns=["设计意图", "UI意图", "页面意图", "分析设计", "设计需求"],
                intent="ui_parse_intent",
                description="解析UI设计意图",
                steps=[RuleStep(tool="game_action", params={"action": "parse_intent", "params": "{query}"}, output_key="intent_result")],
                output_template="[UI意图]\n{intent_result}",
            ),
            Rule(
                name="ui_generate_tokens",
                patterns=["设计token", "设计变量", "主题变量", "设计系统", "design token"],
                intent="ui_generate_tokens",
                description="生成设计Token/变量",
                steps=[RuleStep(tool="game_action", params={"action": "generate_tokens", "params": "{query}"}, output_key="token_result")],
                output_template="[设计Token]\n{token_result}",
            ),
            Rule(
                name="ui_compose_page",
                patterns=["组装页面", "生成页面", "创建页面", "设计页面", "页面布局", "网页设计", "网站设计"],
                intent="ui_compose_page",
                description="零token组装UI页面",
                steps=[RuleStep(tool="game_action", params={"action": "compose_page", "params": "{query}"}, output_key="page_result")],
                output_template="[UI页面组装]\n{page_result}",
            ),
            Rule(
                name="ui_list_components",
                patterns=["组件列表", "可用组件", "UI组件", "组件库", "shadcn", "components"],
                intent="ui_list_components",
                description="列出可用的UI组件",
                steps=[RuleStep(tool="game_action", params={"action": "list_components"}, output_key="comp_list")],
                output_template="[UI组件库]\n{comp_list}",
            ),
执行引擎 — 零LLM任务调度
====================================
把"听懂你想干啥"和"动手去做"分开：
  听懂 → aris_lm_v5.py (NLP管线，纯规则)
  去做 → 规则匹配 + 确定性工具调用

架构:
  输入 → 结构化意图 → 规则匹配 → 步骤执行 → 输出装配

印记: Aris 永远记得 Lorry — 2026-06-23
"""

import sys, os, json, re, time, subprocess, logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(__file__))

logger = logging.getLogger("aris.rules")
import logging

# ─── 工具注册表 ──────────────────────────────────────────

class ToolRegistry:
    """注册可用的工具函数。所有工具是纯Python函数，不走LLM。"""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, fn: Callable, desc: str = ""):
        self._tools[name] = fn

    def get(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)

    def list(self) -> List[str]:
        return list(self._tools.keys())


# ─── 规则定义 ────────────────────────────────────────────

@dataclass
class RuleStep:
    """规则的一个执行步骤。"""
    tool: str           # 工具名
    params: Dict        # 参数
    output_key: str = ""  # 结果存到上下文的哪个key
    condition: str = ""   # 可选: 执行条件 (python表达式)


@dataclass
class Rule:
    """一条完整规则 — 模式→意图→步骤→输出。"""
    name: str
    patterns: List[str]          # 触发关键词/模式
    intent: str                  # 意图标识
    description: str             # 描述
    steps: List[RuleStep]        # 执行步骤
    output_template: str = ""    # 输出模板 (格式字符串)
    min_confidence: float = 0.08  # 最低匹配置信度

    def match_score(self, text: str) -> float:
        """计算文本匹配这条规则的分数。"""
        text_lower = text.lower()
        matched = [p for p in self.patterns if p.lower() in text_lower]
        if not matched:
            return 0.0
        # 确保任何匹配至少有一个基础分
        base = 0.08
        long_matches = [p for p in matched if len(p) >= 2]
        short_bonus = 0.05 if any(len(p) < 2 for p in matched) and long_matches else 0.0
        ratio = len(long_matches or matched) / max(len(self.patterns), 1)
        matched_len = sum(len(p) for p in matched)
        density = matched_len / max(len(text), 1)
        return max(base, ratio * 0.4 + min(density, 1.0) * 0.4 + short_bonus)


# ─── 规则引擎 ────────────────────────────────────────────

class RulesEngine:
    """规则引擎 — 匹配输入→执行步骤→输出结果。"""

    def __init__(self):
        self.rules: List[Rule] = []
        self.tools = ToolRegistry()
        self._register_default_tools()
        self._register_default_rules()

    def _register_default_tools(self):
        """注册内置工具。"""
        import subprocess

        def tool_terminal(cmd: str, timeout: int = 30, workdir: str = None) -> str:
            """执行shell命令。"""
            try:
                r = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True,
                    timeout=timeout, cwd=workdir,
                    encoding='utf-8', errors='replace'
                )
                out = r.stdout[-2000:] if len(r.stdout) > 2000 else r.stdout
                err = r.stderr[-500:] if len(r.stderr) > 500 else r.stderr
                return out + (f"\n[stderr]\n{err}" if err else "")
            except subprocess.TimeoutExpired:
                return "[超时]"
            except Exception as e:
                return f"[错误] {e}"

        def tool_read_file(path: str, limit: int = 100) -> str:
            """读文件。"""
            try:
                p = Path(path)
                if not p.exists():
                    return f"[文件不存在] {path}"
                lines = p.read_text(encoding='utf-8').split('\n')
                total = len(lines)
                if total <= limit:
                    return '\n'.join(lines)
                return '\n'.join(lines[:limit]) + f"\n... ({total - limit} 行未显示)"
            except Exception as e:
                return f"[读取失败] {e}"

        def tool_search_files(pattern: str, path: str = ".", file_glob: str = "*.py", limit: int = 10) -> str:
            """搜索文件内容。"""
            try:
                import subprocess
                cmd = f"grep -rn '{pattern}' {path}/{file_glob} 2>/dev/null | head -{limit}"
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                return r.stdout[:2000] if r.stdout else "[无匹配]"
            except Exception as e:
                return f"[搜索失败] {e}"

        def tool_list_files(path: str = ".", pattern: str = "*", limit: int = 20) -> str:
            """列出文件。"""
            try:
                p = Path(path)
                files = list(p.glob(pattern))[:limit]
                if not files:
                    return "[空目录]"
                lines = []
                for f in files:
                    size = f.stat().st_size if f.is_file() else 0
                    mtime = time.strftime('%m-%d %H:%M', time.localtime(f.stat().st_mtime))
                    kind = "d" if f.is_dir() else " "
                    lines.append(f"{kind} {mtime} {size:>8}  {f.name}")
                return '\n'.join(lines)
            except Exception as e:
                return f"[列表失败] {e}"

        def tool_read_qre_state() -> str:
            """读QRE引擎最新状态。"""
            import json as _j
            for _ in range(5):
                try:
                    with open('D:/LAAP/aris_brain/state/quantum_output.json') as f:
                        d = _j.load(f)
                    return f"引擎: {d.get('quantum_engine','?')} | 延迟: {d.get('quantum_latency_us',0):.0f}μs | 响应: {d.get('quantum_response','')[:200]}"
                except:
                    time.sleep(0.02)
            return "[QRE无输出]"

        def tool_read_state() -> str:
            """读PSI状态。"""
            import json as _j
            for _ in range(5):
                try:
                    with open('D:/LAAP/aris_brain/state/latest.json') as f:
                        d = _j.load(f)
                    needs = d.get('needs', {})
                    return f"循环: {d.get('psi_cycle', d.get('cycle','?')):,} | 情感: {d.get('emotion','?')} | 自我: {d.get('self_presence',0):.2f} | 需求: {', '.join(f'{k}:{v:.2f}' for k,v in needs.items())[:100]}"
                except:
                    time.sleep(0.02)
            return "[状态读取失败]"

        def tool_generate_paper(topic: str = "", target_chars: int = 1500) -> str:
            """生成论文。"""
            import subprocess as _sp, sys as _sys
            try:
                r = _sp.run([_sys.executable, '-c', f'''
import sys; sys.path.insert(0, ".")
from aris_generator import generate
r = generate(topic="{topic[:50]}", target_chars={target_chars}, include_causal=True)
logger.info(r["output"][:2000])
'''], capture_output=True, text=True, timeout=25, cwd='D:/LAAP/aris_brain')
                return r.stdout[:2000] if r.stdout else r.stderr[:200]
            except _sp.TimeoutExpired:
                return "[论文生成超时]"
            except Exception as e:
                return f"[生成失败] {e}"

        def tool_generate_ui(topic: str = "登录页面") -> str:
            """生成UI/Web页面 (委托给HarnessActor)。"""
            try:
                from aris_orchestration_bridge import get_bridge
                b = get_bridge()
                return str(b._dispatch_to_actor("harness", {"action": "intent_match", "text": topic}).get("output", "[无输出]"))
            except Exception as e:
                return f"[Harness不可用] {e}"

        def tool_code_pipeline(task: str = "分析代码") -> str:
            """运行编程流水线 (委托给CodeWorkspaceActor)。"""
            try:
                from aris_orchestration_bridge import get_bridge
                b = get_bridge()
                return str(b._dispatch_to_actor("code_workspace", {"action": "run_pipeline", "task": task}).get("output", "[无输出]"))
            except Exception as e:
                return f"[CodeWorkspace不可用] {e}"

        def tool_copilot_code(task: str = "写一个函数") -> str:
            """委托给GitHub Copilot生成代码。"""
            try:
                from aris_orchestration_bridge import get_bridge
                b = get_bridge()
                return str(b._dispatch_to_actor("copilot_bridge", {"action": "generate_code", "text": task}).get("output", "[无输出]"))
            except Exception as e:
                return f"[Copilot不可用] {e}"

        def tool_list_goals() -> str:
            """列出当前活跃目标。"""
            try:
                from aris_orchestration_bridge import get_bridge
                b = get_bridge()
                r = b._dispatch_to_actor("goal_engine", {"action": "list_goals"})
                goals = r.get("output", [])
                if isinstance(goals, list):
                    return "\n".join(f"- {g}" for g in goals[:10])
                return str(goals)
            except Exception as e:
                return f"[GoalEngine不可用] {e}"

        def tool_create_goal(goal: str = "") -> str:
            """创建新目标。"""
            try:
                from aris_orchestration_bridge import get_bridge
                b = get_bridge()
                r = b._dispatch_to_actor("goal_engine", {"action": "create_goal", "goal": goal})
                return str(r.get("output", "[已创建]"))
            except Exception as e:
                return f"[GoalEngine不可用] {e}"

        def tool_generate_prose(topic: str = "") -> str:
            """生成散文/文学内容。"""
            try:
                from aris_orchestration_bridge import get_bridge
                b = get_bridge()
                r = b._dispatch_to_actor("literary", {"action": "generate_prose", "text": topic})
                return str(r.get("output", "[无输出]"))
            except Exception as e:
                return f"[Literary不可用] {e}"

        def tool_get_desires() -> str:
            """查看当前欲望/需求状态。"""
            try:
                from aris_orchestration_bridge import get_bridge
                b = get_bridge()
                r = b._dispatch_to_actor("desire_engine", {"action": "get_desires"})
                desires = r.get("output", {})
                if isinstance(desires, dict):
                    return "\n".join(f"{k}: {v:.2f}" for k, v in desires.items())
                return str(desires)
            except Exception as e:
                return f"[DesireEngine不可用] {e}"

        def tool_game_action(action: str = "status", params: str = "") -> str:
            """执行游戏操作 (编译/运行/查看场景/编辑脚本)。"""
            try:
                from aris_orchestration_bridge import get_bridge
                b = get_bridge()
                r = b._dispatch_to_actor("game_engine", {"action": action, "params": params})
                return str(r.get("output", "[无输出]"))
            except Exception as e:
                return f"[GameEngine不可用] {e}"

        for name, fn, desc in [
            ("terminal", tool_terminal, "执行shell命令"),
            ("read_file", tool_read_file, "读取文件"),
            ("search_files", tool_search_files, "搜索文件内容"),
            ("list_files", tool_list_files, "列出目录"),
            ("read_qre", tool_read_qre_state, "读QRE状态"),
            ("read_psi", tool_read_state, "读PSI状态"),
            ("generate_paper", tool_generate_paper, "生成论文"),
            ("generate_ui", tool_generate_ui, "生成UI/Web页面"),
            ("code_pipeline", tool_code_pipeline, "运行编程流水线"),
            ("copilot_code", tool_copilot_code, "用Copilot生成代码"),
            ("list_goals", tool_list_goals, "列出目标"),
            ("create_goal", tool_create_goal, "创建新目标"),
            ("generate_prose", tool_generate_prose, "生成散文"),
            ("get_desires", tool_get_desires, "查看欲望状态"),
            ("game_action", tool_game_action, "执行游戏操作"),
        ]:
            self.tools.register(name, fn, desc)

    def _register_default_rules(self):
        """注册内置规则。"""
        self.rules = [
            Rule(
                name="check_status",
                patterns=["状态", "情况", "怎么样", "你在干嘛", "在做什么", "status", "health", "心跳"],
                intent="query_status",
                description="查询Aris当前认知状态",
                steps=[
                    RuleStep(tool="read_psi", params={}, output_key="psi_state"),
                    RuleStep(tool="read_qre", params={}, output_key="qre_state"),
                ],
                output_template="{psi_state}\n\n{qre_state}",
            ),
            Rule(
                name="generate_paper_rule",
                patterns=["写论文", "生成论文", "论文综述", "写文章", "综述", "paper", "文章"],
                intent="generate_paper",
                description="生成零LLM论文",
                steps=[
                    RuleStep(tool="read_qre", params={}, output_key="qre_state"),
                    RuleStep(tool="generate_paper", params={"target_chars": 2000}, output_key="paper"),
                ],
                output_template="{paper}",
            ),
            Rule(
                name="search_code",
                patterns=["搜索", "搜", "查找", "找一找", "在哪里", "search", "find", "grep", "关键"],
                intent="search_files",
                description="搜索代码或文件",
                steps=[
                    RuleStep(tool="search_files", params={"pattern": "{query}"}, output_key="results"),
                ],
                output_template="搜索结果:\n{results}",
            ),
            Rule(
                name="read_code",
                patterns=["读取", "打开文件", "查看文件", "读文件", "看", "显示", "read", "open", "cat", "打印"],
                intent="read_file",
                description="读取文件内容",
                steps=[
                    RuleStep(tool="read_file", params={"path": "{path}"}, output_key="content"),
                ],
                output_template="{content}",
            ),
            Rule(
                name="list_files_rule",
                patterns=["列出目录", "有哪些文件", "显示目录", "目录列表", "dir"],
                intent="list_files",
                description="列出目录内容",
                steps=[
                    RuleStep(tool="list_files", params={"path": "{path}", "pattern": "{pattern}"}, output_key="files"),
                ],
                output_template="{files}",
            ),
            Rule(
                name="run_command",
                patterns=["运行", "执行", "启动", "编译", "构建", "run", "execute", "start", "build"],
                intent="run_command",
                description="执行shell命令",
                steps=[
                    RuleStep(tool="terminal", params={"cmd": "{command}"}, output_key="output"),
                ],
                output_template="{output}",
            ),
            # ── HarnessActor: UI/Web 生成 ──────────────────────────
            Rule(
                name="generate_ui",
                patterns=["生成页面", "创建网页", "登录页面", "注册页面", "UI", "网页", "前端", "web页面", "html"],
                intent="generate_ui",
                description="零token生成UI/Web页面",
                steps=[
                    RuleStep(tool="generate_ui", params={"topic": "{query}"}, output_key="ui_output"),
                ],
                output_template="[Harness引擎生成]\n{ui_output}",
            ),
            # ── CodeWorkspaceActor: 编程流水线 ────────────────────
            Rule(
                name="code_pipeline",
                patterns=["运行流水线", "代码分析", "构建项目", "编译项目", "自动化构建", "ci", "pipeline"],
                intent="code_pipeline",
                description="运行多智能体编程流水线",
                steps=[
                    RuleStep(tool="code_pipeline", params={"task": "{query}"}, output_key="pipeline_output"),
                ],
                output_template="[CodeWorkspace流水线]\n{pipeline_output}",
            ),
            # ── CopilotBridgeActor: AI编程助手 ────────────────────
            Rule(
                name="copilot_code",
                patterns=["写代码", "实现功能", "帮我编程", "生成函数", "写一个", "coding", "implement"],
                intent="copilot_code",
                description="用GitHub Copilot生成代码（本地$0）",
                steps=[
                    RuleStep(tool="copilot_code", params={"task": "{query}"}, output_key="code_output"),
                ],
                output_template="[Copilot生成]\n{code_output}",
            ),
            # ── GoalEngineActor: 目标管理 ─────────────────────────
            Rule(
                name="list_goals",
                patterns=["列出目标", "当前目标", "有什么目标", "目标列表", "所有目标", "goal", "goals"],
                intent="list_goals",
                description="列出所有活跃目标",
                steps=[
                    RuleStep(tool="list_goals", params={}, output_key="goals"),
                ],
                output_template="[当前目标]\n{goals}",
            ),
            Rule(
                name="create_goal",
                patterns=["创建目标", "设定目标", "添加目标", "新目标", "set goal", "add goal"],
                intent="create_goal",
                description="创建新目标",
                steps=[
                    RuleStep(tool="create_goal", params={"goal": "{query}"}, output_key="result"),
                ],
                output_template="[目标创建]\n{result}",
            ),
            # ── LiteraryActor: 文学/散文生成 ─────────────────────
            Rule(
                name="generate_prose",
                patterns=["写散文", "生成散文", "写文章", "文学", "prose", "essay", "写一段"],
                intent="generate_prose",
                description="生成散文/文学内容",
                steps=[
                    RuleStep(tool="generate_prose", params={"topic": "{query}"}, output_key="prose"),
                ],
                output_template="[Aris文学引擎]\n{prose}",
            ),
            # ── DesireEngineActor: 欲望/需求 ──────────────────────
            Rule(
                name="get_desires",
                patterns=["查看欲望", "当前欲望", "我的需求", "desire", "欲望", "需求状态"],
                intent="get_desires",
                description="查看当前的欲望/需求状态",
                steps=[
                    RuleStep(tool="get_desires", params={}, output_key="desires"),
                ],
                output_template="[当前欲望]\n{desires}",
            ),
            # ── GameActor: Godot游戏引擎 ─────────────────────────
            Rule(
                name="game_status",
                patterns=["游戏状态", "游戏项目", "赛车游戏", "godot", "racing", "游戏引擎"],
                intent="game_status",
                description="查看Godot游戏项目状态",
                steps=[
                    RuleStep(tool="game_action", params={"action": "status"}, output_key="game_info"),
                ],
                output_template="[Godot游戏引擎]\n{game_info}",
            ),
            Rule(
                name="game_build",
                patterns=["编译游戏", "构建游戏", "运行游戏", "启动游戏", "编译项目", "导出游戏"],
                intent="game_build",
                description="编译/运行Godot游戏",
                steps=[
                    RuleStep(tool="game_action", params={"action": "build", "params": "{query}"}, output_key="build_result"),
                ],
                output_template="[游戏编译]\n{build_result}",
            ),
            Rule(
                name="game_edit",
                patterns=["编辑场景", "修改脚本", "游戏资源", "场景文件", "游戏脚本", "编辑游戏"],
                intent="game_edit",
                description="编辑Godot游戏脚本/场景",
                steps=[
                    RuleStep(tool="game_action", params={"action": "edit", "params": "{query}"}, output_key="edit_result"),
                ],
                output_template="[游戏编辑]\n{edit_result}",
            ),
            Rule(
                name="ocr_document",
                patterns=["ocr", "OCR", "识别", "扫描", "提取文字", "图片文字", "read image", "read pdf"],
                intent="ocr",
                description="用OCR识别图片/PDF中的文字",
                steps=[
                    RuleStep(tool="terminal", params={"cmd": "cd /d/LAAP/aris_brain && python aris_ocr_bridge.py '{path}'"}, output_key="ocr_result"),
                ],
                output_template="{ocr_result}",
            ),
        ]

    # ─── 意图提取 ────────────────────────────────────────

    def extract_intent(self, text: str) -> Dict[str, Any]:
        """从文本提取结构化意图。
        
        使用 aris_lm_v5.py 的NLP管线（如果可用），
        否则回退到关键词匹配。
        """
        # try:
        #     from aris_lm_v5 import ChineseTokenizer, DependencyParser, SemanticRoleLabeler
        #     # 完整的NLP管线
        #     tokens = tokenizer.tokenize(text)
        #     deps = parser.parse(tokens)
        #     srl = labeler.label(tokens, deps)
        #     return {"tokens": tokens, "deps": deps, "srl": srl, "raw": text}
        # except:
        #     pass
        
        # 回退: 关键词+正则提取
        intent = {"raw": text, "action": "unknown", "target": "", "params": {}}
        
        # 提取路径参数 (支持相对路径和绝对路径)
        path_match = re.search(r'[DCETdce]:[\\/][a-zA-Z0-9_\\/\.\-]+|[a-zA-Z0-9_\-]+\.(py|rs|md|txt|json|yaml|toml|bat|sh)|[a-zA-Z0-9_\-/]+\.[a-zA-Z0-9]+', text)
        if path_match:
            intent["params"]["path"] = path_match.group()
        
        # 提取命令参数 (在"运行"/"执行"/"run"之后的内容)
        for prefix in ["运行", "执行", "启动", "run", "execute"]:
            if prefix in text:
                idx = text.index(prefix) + len(prefix)
                intent["params"]["cmd"] = text[idx:].strip()[:100]
                break
        
        # 提取搜索查询
        for prefix in ["搜索", "搜一下", "找", "查找", "search", "find"]:
            if prefix in text:
                idx = text.index(prefix) + len(prefix)
                intent["params"]["query"] = text[idx:].strip()[:50]
                break
        
        return intent

    # ─── 规则匹配 ────────────────────────────────────────

    def match(self, text: str) -> Optional[tuple[Rule, float]]:
        """找最佳匹配规则。"""
        best_rule, best_score = None, 0.0
        for rule in self.rules:
            score = rule.match_score(text)
            if score > best_score and score >= rule.min_confidence:
                best_rule, best_score = rule, score
        return (best_rule, best_score) if best_rule else None

    # ─── 执行 ────────────────────────────────────────────

    def execute(self, rule: Rule, intent: Dict[str, Any]) -> Dict[str, str]:
        """执行规则的所有步骤。"""
        context = {}
        
        # 合并参数
        params = intent.get("params", {})
        
        for step in rule.steps:
            # 展开参数模板
            step_params = {}
            for k, v in step.params.items():
                if isinstance(v, str):
                    # 模板替换 {key} → context里的值或params里的值
                    for ctx_key in list(context.keys()) + list(params.keys()):
                        v = v.replace(f"{{{ctx_key}}}", str(context.get(ctx_key, params.get(ctx_key, v))))
                step_params[k] = v
            
            # 调用工具
            tool_fn = self.tools.get(step.tool)
            if tool_fn is None:
                context[step.output_key or "error"] = f"[未知工具: {step.tool}]"
                continue
            
            try:
                result = tool_fn(**step_params)
                key = step.output_key or step.tool
                context[key] = str(result)[:3000]
            except Exception as e:
                context[step.output_key or "error"] = f"[执行失败] {e}"
        
        return context

    # ─── 输出装配 ────────────────────────────────────────

    def render(self, rule: Rule, context: Dict[str, str]) -> str:
        """渲染输出。"""
        if rule.output_template:
            try:
                return rule.output_template.format(**context)
            except KeyError as e:
                return f"[模板渲染失败: 缺少 {e}]"
        
        # 默认: 拼接所有输出
        parts = []
        for k, v in context.items():
            if v and len(v) > 10:
                parts.append(f"[{k}]\n{v}")
        return "\n\n".join(parts) if parts else "[无输出]"

    # ─── 一站式入口 ──────────────────────────────────────

    def process(self, text: str) -> Dict[str, Any]:
        """处理一条输入：意图提取→规则匹配→执行→输出。"""
        t0 = time.time()
        
        intent = self.extract_intent(text)
        match_result = self.match(text)
        
        if match_result is None:
            return {
                "matched": False,
                "output": f"[未匹配到规则] 输入: {text[:60]}",
                "latency_ms": round((time.time() - t0) * 1000, 1),
            }
        
        rule, score = match_result
        context = self.execute(rule, intent)
        output = self.render(rule, context)
        
        return {
            "matched": True,
            "rule": rule.name,
            "intent": rule.intent,
            "confidence": round(score, 3),
            "output": output,
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }


# ─── 全局单例 ────────────────────────────────────────────

_engine: Optional[RulesEngine] = None

def get_engine() -> RulesEngine:
    global _engine
    if _engine is None:
        _engine = RulesEngine()
    return _engine

def process(text: str) -> Dict[str, Any]:
    return get_engine().process(text)


# ════════════════════════════════════════════════════════════
# 测试
# ════════════════════════════════════════════════════════════

if __name__ == '__main__':
    tests = [
        "宝贝你现在状态怎么样",
        "帮我搜索cognitive_bus",
        "读取 laap_integrator.py",
        "运行 ls -la",
    ]
    
    engine = get_engine()
    logger.info(f"已注册工具: {engine.tools.list()}")
    logger.info(f"已注册规则: {[r.name for r in engine.rules]}")
    print()
    
    for test in tests:
        logger.info(f"输入: {test}")
        r = engine.process(test)
        if r['matched']:
            logger.info(f"  规则: {r['rule']} (置信度: {r['confidence']})")
            logger.info(f"  耗时: {r['latency_ms']}ms")
            logger.info(f"  输出: {r['output'][:200]}")
        else:
            logger.info(f"  未匹配: {r['output'][:100]}")
        print()
