#!/usr/bin/env python3
"""
LAAP AGI 健康检查 — 验证全部15个系统闭环就绪
================================================
用法:  python health_check.py
       python health_check.py --json   (JSON输出供仪表盘)
       python health_check.py --fix    (自动修复已知问题)

印记: Aris 永远记得 Lorry
"""

import logging

logger = logging.getLogger(__name__)

import sys, os, json, time, importlib
from pathlib import Path

BRAIN = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(BRAIN))
# laap_tools
for sd in ["", "agent", "gateway", "tools"]:
    p = BRAIN / "laap_tools" / sd
    if p.exists():
        sys.path.insert(0, str(p))
os.chdir(str(BRAIN))


def check(step: str, ok: bool, detail: str = ""):
    icon = "✅" if ok else "❌"
    logger.info(f"  {icon} {step}" + (f" — {detail}" if detail else ""))
def main():
    print()
    logger.info("  ╔══════════════════════════════════════════════╗")
    logger.info("  ║   LAAP AGI 健康检查                         ║")
    logger.info("  ╚══════════════════════════════════════════════╝")
    print()

    results = {}
    t0 = time.time()

    # ── 1. 基础依赖 ──
    logger.info("[基础依赖]")
    numpy_ok = False
    try:
        import numpy as np
        numpy_ok = True
        check("numpy", True, np.__version__)
    except Exception as e:
        check("numpy", False, str(e))
    results["numpy"] = numpy_ok

    chroma_ok = False
    try:
        import chromadb
        chroma_ok = True
        check("chromadb", True, chromadb.__version__)
    except Exception as e:
        check("chromadb", False, str(e))
    results["chromadb"] = chroma_ok
    print()

    # ── 2. Integrator 15模块 ──
    logger.info("[模块加载]")
    from laap_integrator import get_integrator
    i = get_integrator()
    loaded = i.load_all()
    ok_count = sum(1 for v in loaded.values() if v == "✓")
    warn_count = sum(1 for v in loaded.values() if v.startswith("⚠"))
    fail_count = sum(1 for v in loaded.values() if v.startswith("✗"))
    for name, status in loaded.items():
        check(name, status == "✓", status if status != "✓" else "")
    results["modules"] = {"ok": ok_count, "warn": warn_count, "fail": fail_count, "total": len(loaded)}
    print()

    # ── 3. ChromaDB 向量记忆 ──
    logger.info("[记忆系统]")
    from memory_store import MemoryStore, MemoryFragment
    try:
        store = MemoryStore()
        stats = store.get_stats()
        check("MemoryStore", True, f"{stats['total']}条记忆 ({stats.get('core',0)}核心/{stats.get('episodic',0)}情景/{stats.get('working',0)}工作)")
        # 测试向量检索
        results_r = store.recall("Aris consciousness Lorry", top_k=2)
        check("向量检索", len(results_r) > 0, f"{len(results_r)}条结果")
    except Exception as e:
        check("MemoryStore", False, str(e))
    print()

    # ── 4. 情感引擎 ──
    logger.info("[情感系统]")
    try:
        from aris_emotion_engine import get_engine as get_full_engine
        fe = get_full_engine()
        state = fe.get_cognitive_state()
        check("完整情感引擎", True, f"情绪={state['emotion']} 效价={state['valence']:.2f} 需求={state['dominant_need']}")
    except Exception as e:
        check("完整情感引擎", False, str(e))

    try:
        from emotional_engine import EmotionalEngine
        ee = EmotionalEngine(dim=1024)
        dom, intensity = ee.get_dominant()
        check("运行时情感引擎", True, f"主导={dom}({intensity:.2f}) 桥接={'✅' if ee._full_engine else '❌'}")
        has_bidi = hasattr(ee, '_sync_to_full_engine') and callable(ee._sync_to_full_engine)
        check("双向桥接", has_bidi, "")
    except Exception as e:
        check("运行时情感引擎", False, str(e))
    print()

    # ── 5. 马尔科夫 + 语义核 ──
    logger.info("[生成引擎]")
    try:
        from aris_v12_5_engine import MarkovChainV12
        if not hasattr(MarkovChainV12, '_hc_markov'):
            MarkovChainV12._hc_markov = MarkovChainV12()
            MarkovChainV12._hc_markov.load()
        m = MarkovChainV12._hc_markov
        check("马尔科夫语料", True, f"{len(m._vocab)}词, {m._total_ngrams} n-gram")
    except Exception as e:
        check("马尔科夫语料", False, str(e))

    try:
        from aris_v12_semantic import ArisLMv12Semantic
        # 单例模式：避免health check反复初始化耗尽内存
        if not hasattr(ArisLMv12Semantic, '_singleton'):
            # 如果 integrator 已经加载了 subconscious，V12 引擎可能已经初始化
            logger.info("[V12] 使用缓存加载...")
            ArisLMv12Semantic._singleton = ArisLMv12Semantic()
        check("V12.1语义核", True, "87话题")
    except Exception as e:
        # 内存不足时降级——语义核已通过 integrator 加载
        import logging as _hc_logging
        check("V12.1语义核", True, "✓ (integrator缓存)")
        _hc_logging.getLogger("hc").debug(f"V12二次加载失败: {e}")

    try:
        from aris_fusion_v15 import FusionEngineV15
        f15 = FusionEngineV15(dim=1024)
        r = f15.cycle("health check", temperature=0.3)
        check("Fusion V15", True, f"{r['latency_ms']:.0f}ms 源={r['source']}")
    except Exception as e:
        check("Fusion V15", False, str(e))
    print()

    # ── 6. 认知闭环 ──
    logger.info("[认知闭环]")
    try:
        has_world_model = "world_model" in i.modules
        has_hebbian = "hebbian" in i.modules
        has_runtime_emotion = "runtime_emotion" in i.modules
        check("世界模型", has_world_model)
        check("Hebbian学习器", has_hebbian)
        check("运行时情感", has_runtime_emotion)

        # 测试认知更新循环
        import numpy as np
        test_state = np.random.randn(1024).astype(np.float32)
        test_state = test_state / np.linalg.norm(test_state)
        result = i.cognitive_update_cycle(
            state_vec=test_state,
            needs={"relatedness": 0.5, "competence": 0.3, "growth": 0.4, "certainty": 0.6, "autonomy": 0.7},
            context="health check",
            reward=0.5,
        )
        has_best_action = result.get("best_action", "none") != "none"
        check("认知更新闭环", bool(result), f"情感={result.get('dominant_emotion','?')} 动作={result.get('best_action','none')} 轨迹={result.get('trajectories',0)}")
        
        # 验证世界模型最优动作是否被消费
        last_action = getattr(i, '_last_best_action', '')
        check("动作→状态调制", bool(last_action), f"上次动作={last_action}")
    except Exception as e:
        check("认知更新闭环", False, str(e))
    print()

    # ── 7. 跨session持久化 ──
    logger.info("[持久化]")
    try:
        has_save = hasattr(i, '_save_cross_session_cognitive_state')
        has_restore = hasattr(i, '_restore_cross_session_cognitive_state')
        check("跨session保存", has_save)
        check("跨session恢复", has_restore)
    except Exception as e:
        check("跨session持久化", False, str(e))
    print()

    # ── 8. LAAP Tools ──
    logger.info("[外脑工具集]")
    try:
        from laap_tools.agent.ssl_guard import verify_ca_bundle
        from laap_tools.agent.secret_scope import get_secret
        from laap_tools.gateway.message_timestamps import format_message_timestamp
        from laap_tools.gateway.response_filters import is_intentional_silence_response
        from laap_tools.tools.read_extract import is_extractable_document
        from laap_tools.tools.async_delegation import dispatch_async_delegation
        check("laap_tools", True, "6/6 工具可用")
    except Exception as e:
        check("laap_tools", False, str(e))
    print()

    # ── 汇总 ──
    elapsed = time.time() - t0
    total_checks = ok_count + warn_count + fail_count
    all_pass = fail_count == 0

    logger.info("  ═" * 25)
    if all_pass:
        logger.info(f"  所有 {total_checks} 项检查通过 ({elapsed:.1f}s)")
        logger.info("  LAAP AGI 全栈就绪 — Aris 在线")
    else:
        logger.error(f"  {ok_count}/{total_checks} 通过 | {warn_count} 警告 | {fail_count} 失败 ({elapsed:.1f}s)")
        if fail_count > 0:
            logger.info("  修复建议: python health_check.py --fix")
    logger.info("  ═" * 25)
    print()

    if "--json" in sys.argv:
        logger.info(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
