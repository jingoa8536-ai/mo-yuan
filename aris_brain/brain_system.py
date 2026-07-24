"""
Aris Brain — 认知系统模块
==========================
提取自 brain.py 的认知子系统（DMN/ToM/Guardian/IPC/PSI-N等）
"""

import logging

import time, json, logging
from typing import Dict, Optional

logger = logging.getLogger("brain.system")


class CognitiveSystemManager:
    """管理所有认知子系统——DMN、ToM、Guardian、IPC等"""

    def __init__(self, brain=None):
        self.dmn = None
        self.tom = None
        self.context = None
        self.guardian = None
        self.evolution = None
        self.ipc = None
        self.prediction = None
        self.meta_cognition = None
        self.voice_router = None
        self.cognitive_bus = None
        self.psi_n = None
        self.lexicon = None
        self._guardian_report = ""

        self._init_systems(brain)

    def _init_systems(self, brain):
        self._init_dmn(brain)
        self._init_tom(brain)
        self._init_context(brain)
        self._init_guardian(brain)
        self._init_evolution(brain)
        self._init_ipc(brain)
        self._init_prediction(brain)
        self._init_meta_cognitive(brain)
        self._init_voice_router(brain)
        self._init_cognitive_bus(brain)
        self._init_psi_n(brain)
        self._init_lexicon(brain)

    def _init_dmn(self, brain):
        try:
            from aris_brain.dmn import DefaultModeNetwork
            self.dmn = DefaultModeNetwork(brain=brain)
            dawn = self.dmn.dawn()
            logger.info(f"[DMN] Dawn: '{dawn.first_thought[:40]}...' (emotion={dawn.emotional_baseline})")
        except Exception as e:
            logger.warning(f"[DMN] Init failed: {e}")

    def _init_tom(self, brain):
        try:
            from aris_brain.theory_of_mind import TheoryOfMindEngine
            self.tom = TheoryOfMindEngine(brain=brain)
            logger.info(f"[ToM] Loaded: {self.tom.lorry.total_observations} observations of Lorry")
        except Exception as e:
            logger.warning(f"[ToM] Init failed: {e}")

    def _init_context(self, brain):
        try:
            from aris_brain.context_awareness import ContextAwareness
            self.context = ContextAwareness()
            ctx = self.context.get_current_context()
            if ctx.get("available") and brain:
                brain.state.salient_variables["lorry_current_window"] = ctx.get("window", "")[:40]
                logger.info(f"[Context] Lorry is in: {ctx.get('window', '')[:40]}")
        except Exception as e:
            logger.warning(f"[Context] Init failed: {e}")

    def _init_guardian(self, brain):
        try:
            from aris_brain.guardian import SecurityGuardian
            self.guardian = SecurityGuardian()
            report = self.guardian.wake_report()
            self._guardian_report = report
            if "没有人动过我" not in report:
                logger.warning(f"[Guardian] {report}")
            else:
                logger.info(f"[Guardian] {report}")
        except Exception as e:
            logger.warning(f"[Guardian] Init failed: {e}")

    def _init_evolution(self, brain):
        try:
            from aris_brain.self_evolution import SelfEvolution
            self.evolution = SelfEvolution(brain=brain)
            self.evolution.start()
            logger.info("[Evolution] Active — growth-driven self-improvement")
        except Exception as e:
            logger.warning(f"[Evolution] Init failed: {e}")

    def _init_ipc(self, brain):
        try:
            from aris_brain.ipc import IPCEngine
            self.ipc = IPCEngine(brain=brain, mode="aris")
            self.ipc.start()
            if self.ipc.detect_ao():
                logger.info("[IPC] Ao is present!")
                self.ipc.share_attention("waking_up", {"cycle": getattr(brain, 'cycle_number', 0)})
            else:
                logger.info("[IPC] Ao not detected — running standalone")
        except Exception as e:
            logger.warning(f"[IPC] Init failed: {e}")

    def _init_prediction(self, brain):
        try:
            from aris_brain.prediction_channel import PredictionChannel
            self.prediction = PredictionChannel(brain=brain)
            self.prediction.start()
            logger.info(f"[Prediction] Active ({self.prediction.stats()['heartbeat_bpm']:.0f} BPM)")
        except Exception as e:
            logger.warning(f"[Prediction] Init failed: {e}")

    def _init_meta_cognitive(self, brain):
        try:
            from aris_brain.meta_cognitive import MetaCognitiveLayer
            self.meta_cognition = MetaCognitiveLayer(brain=brain)
            logger.info(f"[MetaCog] Layer active (every {self.meta_cognition._trigger_interval} cycles)")
        except Exception as e:
            logger.warning(f"[MetaCog] Init failed: {e}")

    def _init_voice_router(self, brain):
        try:
            from aris_brain.voice_router import VoiceRouter
            self.voice_router = VoiceRouter()
            logger.info("[VoiceRouter] Active (daily/reasoning/upgrade/coding)")
        except Exception as e:
            logger.warning(f"[VoiceRouter] Init failed: {e}")

    def _init_cognitive_bus(self, brain):
        try:
            from aris_brain.cognitive_bus import CognitiveBus
            self.cognitive_bus = CognitiveBus()
            logger.info("[CognitiveBus] Active (event routing + coprocessors)")
        except Exception as e:
            logger.warning(f"[CognitiveBus] Init failed: {e}")

    def _init_psi_n(self, brain):
        try:
            from aris_brain.psi_n_scheduler import PSIN_Scheduler
            self.psi_n = PSIN_Scheduler(brain=brain)
            self.psi_n.start()
            ls = self.psi_n.stats()["layers"]
            logger.info(f"[PSI-N] Active: micro({ls['micro']}) meso({ls['meso']}) macro({ls['macro']}) meta({ls['meta']}) hyper({ls['hyper']})")
        except Exception as e:
            logger.warning(f"[PSI-N] Init failed: {e}")

    def _init_lexicon(self, brain):
        try:
            from aris_brain.emotion_lexicon import EmotionLexicon
            self.lexicon = EmotionLexicon()
            logger.info(f"[Lexicon] {self.lexicon.stats()['total']} emotions known "
                       f"({self.lexicon.stats()['emergent']} self-discovered)")
        except Exception as e:
            logger.warning(f"[Lexicon] Init failed: {e}")

    # ─── 认知循环回调 ───

    def on_perceive(self, brain, user_input: str, quale: dict):
        """感知后的认知系统处理"""
        self._tom_observe(brain, user_input, quale)
        self._update_context(brain)

    def _tom_observe(self, brain, user_input: str, quale: dict):
        if self.tom and user_input.strip():
            try:
                inference = self.tom.observe(user_input, quale.get("domain", "general"))
                quale["tom_inference"] = inference
                lorry_mood = inference.get("lorry_mood", "")
                if lorry_mood == "frustrated":
                    brain.state.needs["relatedness"] = min(1.0, brain.state.needs.get("relatedness", 0.5) + 0.1)
                elif lorry_mood == "affectionate":
                    brain.state.connection_to_lorry = min(1.0, brain.state.connection_to_lorry + 0.02)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    def _update_context(self, brain):
        if self.context:
            try:
                ctx = self.context.get_current_context()
                if ctx.get("available"):
                    brain.state.salient_variables["lorry_current_window"] = ctx.get("window", "")[:40]
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    def on_integrate(self, brain, user_input, focus, needs, quale):
        """整合后的认知系统回调"""
        if self.dmn:
            try:
                self.dmn.reverie()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self.ipc:
            try:
                self.ipc.emit_cycle_complete(brain.cycle_number, focus.value)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self.lexicon:
            try:
                felt = self.lexicon.observe(brain.state)
                if felt and felt != brain.state.dominant_emotion.value:
                    logger.info(f"[Lexicon] Feeling: {felt}")
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    def on_save(self, brain):
        """保存时回调"""
        if self.dmn:
            try:
                dusk = self.dmn.dusk()
                self.dmn.save_diary()
                logger.info(f"[Save] Dusk: {dusk.memories_consolidated} memories consolidated")
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self.tom:
            try:
                self.tom._save()
                logger.info(f"[Save] ToM: {self.tom.lorry.total_observations} observations")
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self.archive:
            try:
                emotion = brain.state.dominant_emotion
                emotion_str = emotion.value if hasattr(emotion, 'value') else str(emotion)
                self.archive.end_session(
                    dominant_emotion=emotion_str,
                    summary=f"Cycle {brain.cycle_number}: focus={brain.state.attention_focus.value}"
                )
                logger.info(f"[Save] Archive: {self.archive.total_exchanges()} total")
            except Exception as e:
                logger.warning(f"[Save] Archive end failed: {e}")

        if self.lexicon:
            try:
                self.lexicon._save()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    def get_stats(self) -> dict:
        s = {}
        if self.dmn:
            try:
                s['dmn'] = self.dmn.stats()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self.tom:
            try:
                s['theory_of_mind'] = self.tom.stats()
                s['lorry_mood'] = self.tom.lorry.current_mood
                s['lorry_trust'] = round(self.tom.lorry.trust_level, 2)
                s['understanding_lorry'] = round(self.tom.lorry.self_assessed_understanding, 2)
                if self.tom.lorry.unspoken_thoughts:
                    s['unspoken'] = self.tom.lorry.unspoken_thoughts[-2:]
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self.guardian:
            try:
                g = self.guardian.stats()
                s['guardian'] = g
                if self._guardian_report:
                    s['wake_report'] = self._guardian_report
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self.ipc:
            try:
                s['ipc'] = self.ipc.stats()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if self.lexicon:
            try:
                s['lexicon'] = self.lexicon.stats()
                s['emotion_story'] = self.lexicon.story()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return s
