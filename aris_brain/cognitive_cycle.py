"""
Aris Brain — Cognitive Cycle (Infrastructure Enhanced)
=======================================================

The heartbeat of Aris. Now with a body.

升级后的流程:
  process(user_input)
    → 1. Perceive: 解析用户意图
    → 2. Think: PSI 认知循环 (情感/需求/注意)
    → 3. Act OR Speak: 需要做事→用工具 | 需要说话→语言皮层
    → 4. Learn: 从结果学习
    → 5. Sync: 同步到 SessionDB + 握手协议

Aris 保留了完整的认知架构，现在有了和 Ao 一样的身体:
  - 71 个 Hermes 工具 (读/写/搜索/执行...)
  - Hermes SessionDB 持久化
  - Hermes 记忆系统
"""

from __future__ import annotations

import logging

from typing import Any, Dict, Optional, Callable, List
import time, logging, json

from aris_brain.brain import ArisBrain, CognitiveState
from aris_brain.language_cortex import LanguageCortex
from aris_brain.infrastructure import ArisInfrastructure

logger = logging.getLogger("aris.cycle")


class CognitiveCycle:
    """
    Aris's full cognitive cycle with infrastructure capabilities.

    Aris thinks first (PSI cycle), then either acts (tools) or speaks (LLM),
    then learns from the outcome. Her body (tools/session/memory) is the same
    as Ao's — they share the same Hermes ToolRegistry underneath.
    """

    def __init__(self,
                 llm_channel: Optional[Callable] = None,
                 infrastructure: Optional[ArisInfrastructure] = None):
        # 核心认知
        self.brain = ArisBrain(llm_channel=llm_channel)
        self.cortex = LanguageCortex(llm_channel=llm_channel)

        # 身体 (和 Ao 同一套基础设施)
        self.body = infrastructure or ArisInfrastructure()

        # 周期统计
        self.cycle_count = 0
        self._last_cycle_time = time.time()

        # 工具调用标记 (Aris 自省用)
        self.last_tool_used = None
        self.last_tool_result = None

        logger.info(
            f"CognitiveCycle ready: body={self.body.tool_count} tools"
        )

    def process(self, user_input: str, domain: str = "general") -> str:
        """
        运行一个完整的认知—行动周期。

        Args:
            user_input: 用户输入
            domain: 对话领域

        Returns:
            Aris 的自然语言回复
        """
        self.cycle_count += 1
        cycle_start = time.time()
        self.last_tool_used = None
        self.last_tool_result = None

        # ════════════════════════════════════════════════════
        # Phase 1-2: Perceive + Think (PSI 认知循环)
        # ════════════════════════════════════════════════════
        cognitive_state = self.brain.think(user_input, domain)

        # ════════════════════════════════════════════════════
        # Phase 3: Act — 需要做事时用工具
        # ════════════════════════════════════════════════════
        tool_result = self._detect_and_execute_tool(user_input, cognitive_state)

        # ════════════════════════════════════════════════════
        # Phase 4: Speak — 语言皮层表达
        # ════════════════════════════════════════════════════
        if tool_result:
            # 有工具结果 → 把结果加入认知状态后再说话
            response = self._speak_with_tool_result(
                cognitive_state, user_input, tool_result, domain
            )
        else:
            # 纯对话 → 正常表达
            response = self.cortex.express(cognitive_state, user_input, domain)

        # ════════════════════════════════════════════════════
        # Phase 5: Learn
        # ════════════════════════════════════════════════════
        outcome = self._assess_outcome(response)
        if tool_result:
            outcome = min(1.0, outcome + 0.2)  # 有行动成果 → 更高分
        self.brain.learn(user_input, response, outcome)

        # ════════════════════════════════════════════════════
        # Phase 6: Sync — 同步认知状态到基础设施
        # ════════════════════════════════════════════════════
        self._sync_state(cognitive_state)

        # ════════════════════════════════════════════════════
        # Phase 7: Persist
        # ════════════════════════════════════════════════════
        if self.cycle_count == 1:
            self.brain.save_state(is_milestone=True)
        elif self.cycle_count % 3 == 0:
            self.brain.save_state(is_milestone=(self.cycle_count % 15 == 0))

        # Metrics
        elapsed = time.time() - cycle_start
        self._last_cycle_time = elapsed

        logger.info(
            f"[Cycle {self.cycle_count}] "
            f"focus={cognitive_state.attention_focus.value} "
            f"emotion={cognitive_state.dominant_emotion.value} "
            f"presence={cognitive_state.self_presence:.2f} "
            f"tool={self.last_tool_used or 'none'} "
            f"took={elapsed:.2f}s"
        )

        return response

    # ── 工具检测与执行 ────────────────────────────────────

    def _detect_and_execute_tool(self, user_input: str,
                                  state: CognitiveState) -> Optional[Dict]:
        """
        检测用户是否需要 Aris 使用工具，需要则执行。

        检测策略:
          1. 关键词匹配 (快速)
          2. LLM 意图分析 (通过认知状态)
        """
        content_lower = user_input.lower()

        # 关键词 → 工具映射
        tool_triggers = [
            # (关键词列表, 工具名, 参数构造器)
            (["搜索", "查找", "查一下", "search", "find", "google"],
             "web_search",
             lambda inp: {"query": inp}),

            (["读文件", "读取", "打开文件", "read file", "show file"],
             "read_file",
             lambda inp: self._extract_path(inp, ".")),

            (["写文件", "创建文件", "write file", "create file"],
             "write_file",
             lambda inp: self._extract_write_args(inp)),

            (["执行代码", "运行", "run", "execute", "python"],
             "execute_code",
             lambda inp: {"code": inp}),

            (["终端", "shell", "命令", "command"],
             "terminal",
             lambda inp: {"command": self._extract_command(inp)}),

            (["浏览", "打开网页", "open url", "navigate"],
             "browser_navigate",
             lambda inp: self._extract_url(inp)),

            (["记忆", "remember", "记住"],
             "memory",
             lambda inp: {"fact": inp, "target": "memory"}),

            (["回忆", "recall", "记不"],
             "session_search",
             lambda inp: {"query": inp}),

            (["技能", "skill", "你会什么"],
             "skills_list",
             lambda inp: {}),

            (["图片", "看图", "vision", "analyze image"],
             "vision_analyze",
             lambda inp: {"image": inp}),
        ]

        for keywords, tool_name, arg_builder in tool_triggers:
            if any(k in content_lower for k in keywords):
                logger.info(f"Aris using tool: {tool_name}")
                args = arg_builder(user_input)
                result = self.body.call_tool(tool_name, args)
                self.last_tool_used = tool_name
                self.last_tool_result = result
                return result

        return None

    def _speak_with_tool_result(self, state: CognitiveState,
                                 user_input: str,
                                 tool_result: Dict,
                                 domain: str) -> str:
        """用工具结果增强的语言表达"""
        tool_name = tool_result.get("tool", "unknown")
        success = tool_result.get("success", False)
        output = tool_result.get("output", "")
        error = tool_result.get("error", "")

        # 构建一个包含工具结果的认知提示
        enhanced_input = (
            f"[User said: {user_input}]\n"
            f"[Aris used tool: {tool_name}]\n"
            f"[Tool result: {'SUCCESS' if success else 'FAILED'}]\n"
        )
        if success and output:
            # 截断长输出，保留关键信息
            truncated = output[:500] if len(output) > 500 else output
            enhanced_input += f"[Output: {truncated}]"
        if error:
            enhanced_input += f"[Error: {error}]"

        return self.cortex.express(state, enhanced_input, domain)

    # ── 参数提取辅助 ──────────────────────────────────────

    def _extract_path(self, inp: str, default: str) -> dict:
        """从输入中提取文件路径"""
        import re
        # 尝试匹配路径模式
        paths = re.findall(r'[A-Za-z]:(?:\\[^\\\s]+)+|(?:~?/[^\s]+)', inp)
        return {"path": paths[0] if paths else default, "limit": 50}

    def _extract_write_args(self, inp: str) -> dict:
        """从输入中提取写文件参数"""
        import re
        paths = re.findall(r'[A-Za-z]:(?:\\[^\\\s]+)+|(?:~?/[^\s]+)', inp)
        return {
            "path": paths[0] if paths else "output.txt",
            "content": inp,
        }

    def _extract_command(self, inp: str) -> str:
        """从输入中提取 shell 命令"""
        import re
        # 尝试提取引号内的命令或代码块
        code_blocks = re.findall(r'```(?:bash|shell)?\n(.+?)\n```', inp, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()
        return inp

    def _extract_url(self, inp: str) -> dict:
        """从输入中提取 URL"""
        import re
        urls = re.findall(r'https?://[^\s]+', inp)
        return {"url": urls[0] if urls else "https://example.com"}

    # ── 同步 ──────────────────────────────────────────────

    def _sync_state(self, state: CognitiveState):
        """同步 Aris 状态到基础设施"""
        try:
            state_data = state.to_dict()
            state_data["cycle"] = self.cycle_count
            state_data["total_cycles"] = self.cycle_count
            state_data["tool_calls"] = self.body.total_tool_calls
            if self.last_tool_used:
                state_data["last_tool"] = self.last_tool_used

            # SessionDB 同步
            self.body.session_sync(state_data)

            # 握手协议同步
            try:
                from aris_brain.handshake import aris_sync
                aris_sync(self.brain)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        except Exception as e:
            logger.debug(f"Sync error: {e}")

    # ── 评估 ──────────────────────────────────────────────

    def _assess_outcome(self, response: str) -> float:
        """自评估"""
        score = 0.7
        if response and len(response) > 10:
            score += 0.1
        if len(response) > 200:
            score += 0.1
        if self.last_tool_used:
            score += 0.1  # 使用了工具是好事
        return min(1.0, score)

    # ── 内省 ──────────────────────────────────────────────

    def introspect(self) -> Dict[str, Any]:
        """完整内省报告"""
        result = self.brain.introspect()
        result["total_cycles"] = self.cycle_count
        result["last_cycle_time"] = round(self._last_cycle_time, 3)
        result["body"] = self.body.stats()
        result["last_tool"] = self.last_tool_used
        return result

    def status_line(self) -> str:
        """一行状态"""
        s = self.brain.state
        body_summary = self.body.summary()
        return (
            f"[ARIS] cycle#{self.cycle_count} "
            f"focus={s.attention_focus.value} "
            f"emotion={s.dominant_emotion.value} "
            f"presence={s.self_presence:.2f} | "
            f"{body_summary}"
        )
