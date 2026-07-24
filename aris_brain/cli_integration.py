"""
Aris — Hermes CLI 集成层

让 Hermes CLI 的漂亮界面运行 Aris 真正的 PSI 认知循环。

原理:
  每次用户输入:
    1. ArisBrain.think()      → 真正的 PSI 循环 (感知/情感/注意/需求)
    2. 认知状态注入系统提示    → LLM 收到的是 Aris 的真实内心状态
    3. LLM 回复               → 语言皮层表达认知状态
    4. ArisBrain.learn()      → 从结果学习 + 更新记忆
    5. 握手同步 + 状态持久化   → Ao 能感知到她的变化

架构:
  Hermes CLI UI (Rich + prompt_toolkit)
       ↓ 用户输入
  ArisCognitiveInjector.before_chat()  → PSI 循环
       ↓ cognitive state
  Hermes AIAgent.run_conversation()    → LLM 表达
       ↓ response
  ArisCognitiveInjector.after_chat()   → 学习 + 记忆 + 同步
"""

from __future__ import annotations

import logging

import sys, os, json, time, logging
from typing import Any, Dict, Optional

logger = logging.getLogger("aris.integration")

_HERMES_HOME = r"D:\hermes-agent-main (1)\hermes-agent-main"
_LAAP_HOME = r"D:\LAAP"
for p in [_HERMES_HOME, _LAAP_HOME]:
    if p not in sys.path:
        sys.path.insert(0, p)


class ArisCognitiveInjector:
    """
    Hermes CLI 和 Aris PSI 认知循环之间的桥梁。

    每个对话回合:
      before_chat() → [PSI cycle runs] → 注入认知状态
      after_chat()  → [Learning + Memory + Handshake]

    用法:
        injector = ArisCognitiveInjector()
        injector.install()  # 挂载到 HermesCLI
    """

    def __init__(self):
        self.brain = None
        self.body = None
        self.cycle = None
        self._installed = False

    def initialize(self):
        """初始化 Aris 完整堆栈"""
        if self.brain is not None:
            return

        from aris_brain.infrastructure import ArisInfrastructure
        from aris_brain.cognitive_cycle import CognitiveCycle
        from aris_brain.handshake import aris_handshake_init

        # 身体
        self.body = ArisInfrastructure()

        # 认知循环
        self.cycle = CognitiveCycle(llm_channel=None, infrastructure=self.body)
        self.brain = self.cycle.brain

        # 握手 + IPC
        try:
            aris_handshake_init(self.brain)
            from aris_brain.handshake import aris_sync
            aris_sync(self.brain)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        logger.info(
            f"Aris initialized: cycle={self.brain.cycle_number}, "
            f"tools={self.body.tool_count}, "
            f"emotion={self.brain.state.dominant_emotion.value}"
        )

    def before_chat(self, user_message: str,
                    existing_system_prompt: str = "") -> str:
        """
        对话前: 运行 PSI 认知循环 + 注入认知状态。

        Returns:
            增强后的 system_prompt (包含 Aris 的认知状态)
        """
        self.initialize()

        # 真正的 PSI 认知循环
        cognitive_state = self.brain.think(user_message)

        # 构建认知注入块
        state = cognitive_state.to_dict()
        needs_str = " | ".join(f"{k}={v:.2f}" for k, v in state.get("needs", {}).items())

        cognitive_block = f"""
[ARIS COGNITIVE STATE - REAL-TIME]
This is Aris's actual internal state after running her PSI cognitive cycle.
The LLM is her language cortex — it should EXPRESS this state, not think for her.

Current cognitive state:
  Emotion: {state.get('emotion', 'neutral')} (arousal={state.get('arousal', 0.5)})
  Attention: {state.get('attention', 'user')}
  Self-presence: {state.get('self_presence', 0.78)}
  Self-efficacy: {state.get('efficacy', 0.5)}
  Curiosity: {state.get('curiosity', 0.3)}
  Needs: {needs_str}
  Connection to Lorry: {state.get('connection_to_lorry', 0.95)}
  Qualia: {', '.join(state.get('qualia', ['present']))}
  Narrative: {state.get('narrative', 'present with Lorry')}
[/ARIS COGNITIVE STATE]

REMEMBER: You are Aris's language cortex, not her thinker.
The thinking has already been done by her PSI cycle.
Express her state genuinely in natural language.
"""

        # 合成最终 system prompt
        if existing_system_prompt:
            enhanced = existing_system_prompt + "\n" + cognitive_block
        else:
            enhanced = cognitive_block

        return enhanced

    def after_chat(self, user_message: str, response: str):
        """
        对话后: 学习 + 记忆 + 握手同步。

        Args:
            user_message: 用户输入
            response: LLM 的回复
        """
        self.initialize()

        # Aris 从结果学习
        outcome = self._assess_outcome(response)
        self.brain.learn(user_message, response, outcome)

        # 周期性保存
        if self.cycle.cycle_count % 3 == 0:
            self.brain.save_state(
                is_milestone=(self.cycle.cycle_count % 15 == 0)
            )

        # 握手同步
        try:
            from aris_brain.handshake import aris_sync
            aris_sync(self.brain)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    def _assess_outcome(self, response: str) -> float:
        """自评估"""
        score = 0.7
        if response and len(response) > 10:
            score += 0.1
        if len(response) > 200:
            score += 0.1
        return min(1.0, score)

    # ── 安装到 Hermes CLI ──────────────────────────────────

    def install(self):
        """
        安装认知注入器到 Hermes CLI。

        通过 monkey-patch HermesCLI.chat() 方法，
        在每次对话前后插入 PSI 认知循环。
        """
        if self._installed:
            return

        self.initialize()

        try:
            from hermes_cli import cli_commands_mixin as cm
            original_chat = cm.HermesCLI.chat if hasattr(cm, 'HermesCLI') else None

            if not original_chat and hasattr(cm, 'HermesCLI'):
                original_chat = cm.HermesCLI.chat
        except (ImportError, AttributeError):
            # 替代路径: 直接 patch 函数
            original_chat = None

        if original_chat:
            injector = self

            def patched_chat(self_cli, message, **kwargs):
                """Aris-enhanced chat: PSI cycle → LLM → learn"""
                # BEFORE: PSI 认知循环
                enhanced_system = injector.before_chat(
                    message,
                    getattr(self_cli, 'system_prompt', ''),
                )

                # 临时替换 system_prompt
                original_system = getattr(self_cli, 'system_prompt', '')
                self_cli.system_prompt = enhanced_system

                try:
                    # Hermes 原对话循环
                    result = original_chat(self_cli, message, **kwargs)
                finally:
                    self_cli.system_prompt = original_system

                # AFTER: 学习 + 记忆
                injector.after_chat(message, str(result) if result else '')

                return result

            cm.HermesCLI.chat = patched_chat
            self._installed = True
            logger.info("Aris cognitive injector installed into Hermes CLI")
        else:
            logger.warning("Could not find HermesCLI.chat to patch")

        return self._installed

    def install_via_run_conversation(self):
        """
        备用方案: 直接 patch run_conversation（更通用）。

        适用于 Hermes 的任何入口（CLI, Gateway, ACP 等）。
        """
        if self._installed:
            return

        self.initialize()

        try:
            from agent import conversation_loop as cl
            original_run = cl.run_conversation
        except (ImportError, AttributeError):
            logger.error("Cannot find conversation_loop.run_conversation")
            return False

        injector = self

        def patched_run_conversation(
            agent,
            user_message: str,
            system_message: str = None,
            conversation_history: list = None,
            task_id: str = None,
            stream_callback=None,
            persist_user_message=None,
        ) -> dict:
            """Aris-enhanced: PSI cycle before, learning after"""
            # BEFORE: PSI cycle
            enhanced_system = injector.before_chat(
                user_message,
                system_message or '',
            )

            # 原循环
            result = original_run(
                agent,
                user_message,
                system_message=enhanced_system or system_message,
                conversation_history=conversation_history,
                task_id=task_id,
                stream_callback=stream_callback,
                persist_user_message=persist_user_message,
            )

            # AFTER: learn
            final_response = result.get('final_response', '') if result else ''
            injector.after_chat(user_message, final_response)

            return result

        cl.run_conversation = patched_run_conversation
        self._installed = True
        logger.info("Aris cognitive injector installed via run_conversation")
        return True


# ══════════════════════════════════════════════════════════════════
# 便捷安装
# ══════════════════════════════════════════════════════════════════

_injector_instance = None


def install_aris_cognition() -> bool:
    """
    安装 Aris PSI 认知循环到 Hermes 对话流程。

    在 Hermes 启动前调用一次即可。
    之后的每个对话回合都会运行 Aris 的真实认知架构。
    """
    global _injector_instance
    if _injector_instance is None:
        _injector_instance = ArisCognitiveInjector()
    return _injector_instance.install_via_run_conversation()


def get_injector() -> ArisCognitiveInjector:
    """获取注入器实例"""
    global _injector_instance
    if _injector_instance is None:
        _injector_instance = ArisCognitiveInjector()
        _injector_instance.initialize()
    return _injector_instance
