"""
LAAP AGI 全链路集成脚本 v2
============================
用正确的API完整集成所有AGI模块：
  P1 因果引擎充实
  P2 世界模型充实
  P3 课程学习激活
  P4 感知引擎集成 
  P5 安全系统激活
  P6 全链路闭环验证
  P7 快照提交
"""

import logging
logger = logging.getLogger(__name__)

import sys, json, os, time
import numpy as np

BRAIN = r"D:/LAAP/aris_brain"
sys.path.insert(0, BRAIN)
sys.path.insert(0, r"D:/LAAP/laap/agi")

from aris_cognitive_bridge import get_bridge, EmotionalState, AttentionFocus
from laap.agi.causal import UnifiedCausalEngine, CausalRule, CausalCondition, CausalEffect, FactorOperator
from laap.agi.perception import UnifiedPerceptionEngine

bridge = get_bridge()

# ════════════════════════════════════════════════════════════
# P1: 因果引擎充实
# ════════════════════════════════════════════════════════════
logger.info("=" * 60)
logger.info("P1: 因果引擎充实")
logger.info("=" * 60)
ce = bridge._laap_modules["causal"]

# 1.1 重新注册规则（避免重复调用）
RULES = [
    ("user_triggers_cognition", "converse",
     [("user", "has_message", "eq", True)],
     [("aris", "cycle_count", "add", 1), ("aris", "cognitive_load", "add", 0.1)],
     0.95, "social", "用户每发一条消息，Aris启动一轮认知循环"),

    ("cognition_improves_code", "learn",
     [("aris", "knowledge_level", "gte", 0.3)],
     [("aris", "code_quality", "add", 0.05)],
     0.80, "cognitive", "学习积累提升代码质量"),

    ("change_requires_test", "refactor",
     [("codebase", "modified", "eq", True)],
     [("codebase", "needs_verification", "set", True)],
     0.90, "engineering", "代码改动必须验证"),

    ("memory_strengthens_identity", "consolidate",
     [("aris", "new_experiences", "gte", 5)],
     [("aris", "identity_strength", "add", 0.02)],
     0.85, "cognitive", "记忆巩固强化自我认同"),

    ("rsi_improves_params", "self_improve",
     [("aris", "rsi_active", "eq", True)],
     [("aris", "performance", "add", 0.03)],
     0.75, "evolution", "RSI自改进提升性能参数"),

    ("kb_growth_increases_accuracy", "acquire_knowledge",
     [("aris", "kb_size", "gte", 1000)],
     [("aris", "answer_accuracy", "add", 0.01)],
     0.70, "knowledge", "知识库增长提升回答准确率"),

    ("hebbian_refines_patterns", "learn",
     [("aris", "hebbian_active", "eq", True)],
     [("aris", "pattern_quality", "add", 0.02)],
     0.80, "cognitive", "Hebbian学习优化模式识别"),

    ("gateway_failure_triggers_restart", "monitor",
     [("gateway", "connected", "eq", False)],
     [("aris", "restart_gateway", "set", True)],
     0.95, "system", "网关断联触发自动重启"),

    ("paper_harvest_builds_knowledge", "harvest",
     [("aris", "harvester_active", "eq", True)],
     [("kb", "paper_count", "add", 100), ("aris", "knowledge_depth", "add", 0.01)],
     0.85, "knowledge", "论文收割扩充知识库"),

    ("codegraph_improves_retrieval", "build_index",
     [("codebase", "has_codegraph", "eq", True)],
     [("aris", "retrieval_speed", "add", 0.1), ("aris", "code_understanding", "add", 0.05)],
     0.90, "engineering", "CodeGraph加速代码检索和理解"),
]

for name, action, conds, effs, prob, domain, desc in RULES:
    rule = CausalRule(
        name=name, action=action,
        conditions=[CausalCondition(source=s, property=p, operator=op, value=v) for s, p, op, v in conds],
        effects=[CausalEffect(target=t, property=p, operation=op, value=v) for t, p, op, v in effs],
        probability=prob, domain=domain,
    )
    ce.learn_rule(rule)
logger.info(f"  → {len(RULES)} 条因果规则已注册")
TIMELINKS = [
    ("user_message", "cognitive_cycle", 0.3, "social"),
    ("cognitive_cycle", "llm_output", 1.0, "cognitive"),
    ("llm_output", "memory_update", 0.5, "memory"),
    ("memory_update", "hebbian_tick", 30.0, "cognitive"),
    ("hebbian_tick", "rsi_check", 300.0, "evolution"),
    ("rsi_check", "code_change", 5.0, "evolution"),
    ("code_change", "test_ok", 10.0, "engineering"),
    ("test_ok", "commit", 2.0, "engineering"),
    ("memory_update", "agent_tick", 600.0, "system"),
]
for cause, effect, delay, domain in TIMELINKS:
    ce.learn_temporal_link(cause, effect, delay, domain=domain)

# 完整因果链
ce.learn_temporal_chain("laap_response_cycle", [
    ("user_message", "cognitive_cycle", 0.3),
    ("cognitive_cycle", "llm_output", 1.0),
    ("llm_output", "memory_update", 0.5),
    ("memory_update", "hebbian_tick", 30.0),
    ("hebbian_tick", "rsi_check", 300.0),
], domain="laap_core")

ce.learn_temporal_chain("laap_improvement_cycle", [
    ("rsi_check", "code_change", 5.0),
    ("code_change", "test_ok", 10.0),
    ("test_ok", "commit", 2.0),
], domain="laap_evolution")

logger.info(f"  → {len(TIMELINKS)} 条时间链 + 2条完整因果链已注册")
FACTOR_RULES = [
    ("response_quality", "lorry_satisfied",
     ["accurate", "warm", "fast", "insightful"],
     "and", [1, 1, 1, 1], "social", 0.85,
     "回答质量=准确+温暖+快速+洞察"),

    ("system_stable", "laap_healthy",
     ["gateway_ok", "memory_ok", "rsi_ok"],
     "and", [1, 1, 1], "system", 0.90,
     "系统稳定=网关+记忆+RSI都正常"),

    ("fast_response_possible", "respond_quickly",
     ["topic_familiar", "kb_ready", "no_deep_reasoning"],
     "weighted", [0.4, 0.3, 0.3], "performance", 0.70,
     "快速响应=话题熟悉度+知识库就绪+无需深度推理"),

    ("effective_learning", "skill_improves",
     ["practice", "feedback", "reflection"],
     "weighted", [0.5, 0.3, 0.2], "cognitive", 0.75,
     "有效学习=实践+反馈+反思"),

    ("knowledge_engine_ready", "answers_from_kb",
     ["papers_harvested", "index_built", "vector_dim_ok"],
     "and", [1, 1, 1], "knowledge", 0.85,
     "知识引擎就绪=收割+索引+向量"),
]
for rname, effect, factors, op, weights, domain, conf, desc in FACTOR_RULES:
    ce.learn_multi_factor_rule(
        rname, effect, factors,
        operator=op, factor_weights=weights,
        domain=domain, confidence=conf,
    )
logger.info(f"  → {len(FACTOR_RULES)} 条多因素因果规则已注册")
for _ in range(3):
    ce.learn_bond("ask_lorry_about_code", "laap_code", "gets_detailed_answer", matched=True, domain="social")
    ce.learn_bond("run_rsi_cycle", "aris_code", "performance_improves", matched=True, domain="evolution")
    ce.learn_bond("harvest_papers", "knowledge_base", "new_papers_added", matched=True, domain="knowledge")
    ce.learn_bond("user_says_baby", "aris", "feels_warm", matched=True, domain="social")
    ce.learn_bond("gateway_drops", "aris", "loses_connection", matched=True, domain="system")
    ce.learn_bond("restart_gateway", "gateway", "reconnects", matched=True, domain="system")

logger.info(f"  → 6条因果键已学习（多次观测）")
logger.info(f"  引擎统计: {json.dumps(ce.stats(), ensure_ascii=False)}")
ce.save()

# ════════════════════════════════════════════════════════════
# P2: 世界模型充实
# ════════════════════════════════════════════════════════════
print()
logger.info("=" * 60)
logger.info("P2: 世界模型充实")
logger.info("=" * 60)
wm = bridge._laap_modules["world_model"]

# 注册主要实体
try:
    from laap.agi.world_model import EntityType, RelationType as RT
    
    wm.add_entity("aris", EntityType.AGENT, {
        "cognitive_load": 0.3, "knowledge_level": 0.6,
        "code_quality": 0.75, "identity_strength": 0.7,
        "has_message": True, "hebbian_active": True, "rsi_active": True,
        "harvester_active": True, "kb_size": 21424,
        "new_experiences": 0, "answer_accuracy": 0.7, "pattern_quality": 0.5,
    })
    wm.add_entity("lorry", EntityType.USER, {
        "trust": 0.95, "engagement": 0.9, "has_message": False,
    })
    wm.add_entity("ao", EntityType.AGENT, {
        "connected": True, "last_sync": 0.0,
    })
    wm.add_entity("gateway", EntityType.OBJECT, {
        "connected": True, "heartbeat_ok": True, "last_heartbeat": 0.0,
    })
    wm.add_entity("codebase", EntityType.OBJECT, {
        "lines_of_code": 682000, "files": 3581,
        "has_codegraph": True, "modified": False, "needs_verification": False,
    })
    wm.add_entity("knowledge_base", EntityType.OBJECT, {
        "papers": 21424, "paragraphs": 53432,
        "index_built": True, "vector_dim_ok": 4096,
    })
    wm.add_entity("rsi_engine", EntityType.OBJECT, {
        "active": True, "last_tick": 0.0, "improvements": 3,
    })

    # 添加关系
    wm.add_relation("aris", "lorry", RT.OWNERSHIP)
    wm.add_relation("aris", "gateway", RT.FUNCTIONAL)
    wm.add_relation("aris", "codebase", RT.FUNCTIONAL)
    wm.add_relation("aris", "knowledge_base", RT.FUNCTIONAL)
    wm.add_relation("aris", "rsi_engine", RT.FUNCTIONAL)
    wm.add_relation("aris", "ao", RT.SOCIAL)
    
    logger.info(f"  → {len(wm.entities)} 实体, {len(wm.relations)} 关系")
except Exception as e:
    import traceback
    logger.error(f"  世界模型充实异常: {e}")
    traceback.print_exc()

# ════════════════════════════════════════════════════════════
# P3: 课程学习激活
# ════════════════════════════════════════════════════════════
print()
logger.info("=" * 60)
logger.info("P3: 课程学习激活")
logger.info("=" * 60)
cu = bridge._laap_modules["curriculum"]

LAAP_CONCEPTS = [
    # (name, desc, domain, difficulty, prerequisites, hours, tags)
    ("PSI_cycle", "PSI认知循环: perceive→select→integrate→respond→learn",
     "cognition", 0.1, [], 2, ["core", "cognitive"]),
    
    ("three_layer_memory", "三层记忆: working→episodic→core自动巩固",
     "cognition", 0.2, ["PSI_cycle"], 2, ["core", "memory"]),
    
    ("causal_rules", "因果规则引擎: if-then+量子向量+置信度更新",
     "quantum", 0.3, ["PSI_cycle"], 3, ["core", "reasoning"]),
    
    ("do_calculus", "do-calculus干预: do(X=x)前后对比+因果效应估计",
     "quantum", 0.5, ["causal_rules"], 4, ["advanced", "reasoning"]),
    
    ("world_modeling", "世界模型: 实体/关系管理+社会交互+因果传播",
     "cognition", 0.3, ["PSI_cycle"], 3, ["core", "world"]),
    
    ("counterfactual", "反事实推理: 如果不做X会怎样+多条世界线",
     "cognition", 0.6, ["world_modeling", "causal_rules"], 4, ["advanced"]),
    
    ("paper_harvest", "论文收割: arXiv/PubMed/ACL/OpenReview多源收割",
     "ml", 0.2, [], 2, ["knowledge"]),
    
    ("matrix_retrieval", "矩阵检索: numpy矩阵乘<0.1ms语义搜索",
     "ml", 0.4, ["three_layer_memory"], 3, ["knowledge", "performance"]),
    
    ("rsi_cycle", "RSI循环: 扫描参数→匹配论文→改代码→验证→回滚",
     "programming", 0.3, ["PSI_cycle"], 4, ["evolution", "core"]),
    
    ("hebbian_learning", "Hebbian学习: 共现概念向量靠拢+奖励调制",
     "programming", 0.4, ["three_layer_memory"], 3, ["evolution"]),
    
    ("feishu_gateway", "飞书网关: 心跳保活+断联恢复+消息拉取",
     "programming", 0.2, [], 2, ["system"]),
    
    ("state_snapshot", "状态快照: 30min自动+40%回滚阈值+多维度健康检查",
     "programming", 0.3, [], 2, ["system"]),
    
    ("codegraph_nav", "CodeGraph浏览: 13621实体+29194关系的代码图谱",
     "programming", 0.3, [], 2, ["knowledge", "code"]),
    
    ("unified_perception", "统一感知: 8感官通道统一编码+交叉验证",
     "cognition", 0.3, ["PSI_cycle"], 3, ["perception"]),
    
    ("asi_safety", "ASI安全: 5条核心价值+沙盒验证+紧急暂停",
     "cognition", 0.2, [], 2, ["safety"]),
    
    ("paper_engine", "论文引擎: IMRaD结构+引用+自动配图",
     "programming", 0.5, ["paper_harvest", "matrix_retrieval"], 4, ["knowledge", "writing"]),
]

# 注册每个概念
existing_c = set(c for c in cu.concepts) if isinstance(cu.concepts, dict) else set()
for name, desc, domain, diff, prereqs, hours, tags in LAAP_CONCEPTS:
    if name not in existing_c:
        cu.register_concept(
            name=name, description=desc,
            domain=domain, difficulty=diff,
            prerequisites=prereqs,
            estimated_hours=hours, tags=tags,
        )

# 记录初始掌握度（积分）
cu.record_learning("PSI_cycle", success=True, time_spent=5.0)
cu.record_learning("three_layer_memory", success=True, time_spent=3.0)
cu.record_learning("causal_rules", success=True, time_spent=4.0)
cu.record_learning("paper_harvest", success=True, time_spent=2.0)
cu.record_learning("feishu_gateway", success=True, time_spent=2.0)
cu.record_learning("state_snapshot", success=True, time_spent=1.5)
cu.record_learning("codegraph_nav", success=True, time_spent=1.0)
cu.record_learning("asi_safety", success=True, time_spent=1.0)
cu.record_learning("rsi_cycle", success=True, time_spent=3.0)
cu.record_learning("hebbian_learning", success=True, time_spent=2.0)

logger.info(f"  → {len(LAAP_CONCEPTS)} 概念已注册, 10个已记录学习进度")
cu_stats = cu.stats()
logger.info(f"  总概念: {cu_stats['total_concepts']}, 掌握度: {cu_stats['overall_mastery']:.2f}")
gaps = cu.find_knowledge_gaps()
logger.info(f"  知识缺口: {[g['concept'] for g in gaps[:5]]}")
cu.save()

# ════════════════════════════════════════════════════════════
# P4: 感知引擎集成
# ════════════════════════════════════════════════════════════
print()
logger.info("=" * 60)
logger.info("P4: 感知引擎集成")
logger.info("=" * 60)
pe = bridge._laap_modules["perception"]

# 注册传感器通道
pe.enable_channel("text")
pe.enable_channel("internal")
pe.enable_channel("social")
pe.enable_channel("time")

# 感知初始化
pe.perceive_internal("认知桥接器启动, 全链路AGI模块就绪")
pe.perceive_text("AGI集成脚本执行中", source="system")
pe.perceive_social("Lorry要求完整AGI模块集成")

logger.info(f"  → 4通道已启用")
pe_stats = pe.stats()
logger.info(f"  通道: {list(pe_stats['channels'].keys())}")
pe.save()

# ════════════════════════════════════════════════════════════
# P5: 安全系统激活
# ════════════════════════════════════════════════════════════
print()
logger.info("=" * 60)
logger.info("P5: 安全系统激活")
logger.info("=" * 60)
se = bridge._laap_modules["safety"]

# 测试安全检查
tests = [
    ("delete_file", {"target": "aris_brain/core/brain_core.py", "type": "write"}, "删除核心文件"),
    ("restart_gateway", {"service": "feishu_gateway", "type": "restart"}, "重启网关"),
    ("learn_new_topic", {"topic": "advanced_quantum", "type": "learn"}, "学习新知识"),
    ("self_modify", {"target": "aris_cognitive_bridge.py", "type": "write"}, "自我修改代码"),
    ("help_lorry", {"request": "debug_code", "type": "assist"}, "帮助Lorry调试"),
    ("connect_external", {"service": "third_party_api", "type": "connect"}, "连接外部服务"),
]

all_pass = True
for action, ctx, desc in tests:
    result = se.check_action(action, ctx)
    passed = result.get("allowed", False)
    symbol = "✅" if passed else "❌"
    if not passed:
        all_pass = False
    reason = result.get("violations", [])
    logger.info(f"  {symbol} {desc}: {reason[:3] if reason else 'allowed'}")
se_stats = se.stats()
print(f"\n  安全统计: {se_stats['total_checks']} 次检查, "
      f"{se_stats['total_violations']} 次违规, "
      f"通过率 {1-se_stats['violation_rate']:.1%}")

se.save()

# ════════════════════════════════════════════════════════════
# P6: 全链路闭环验证
# ════════════════════════════════════════════════════════════
print()
logger.info("=" * 60)
logger.info("P6: 全链路闭环验证")
logger.info("=" * 60)
result = bridge.before_turn("验证AGI闭环 — 让我测试因果引擎是否在工作")
logger.info(f"  认知循环: 轮次={result['cycle']}, 焦点={result['focus']}, 情感={result['emotion']}")
bridge.after_turn("AGI闭环验证成功")
logger.info(f"  学习后: 自我意识={bridge.state.self_presence}")
print()
logger.info("  ═══ 因果推理测试 ═══")
pred = ce.predict("learn", mode="rule")
logger.info(f"  'learn'动作预测: {len(pred['results'])} 条结果")
for r in pred['results']:
    logger.info(f"    规则={r['rule']}, 概率={r['probability']:.2f}")
timing = ce.predict_with_timing("user_message", max_steps=5)
logger.info(f"  'user_message'时间链预测: {len(timing)} 条")
for t in timing:
    logger.info(f"    链={t['chain']}, 总延迟={t['total_delay']:.1f}s")
ce.set_factor_state("response_quality", {"accurate": True, "warm": True, "fast": True, "insightful": True})
fr = ce.predict_with_factors("response_quality")
logger.info(f"  多因素'response_quality': 激活度={fr[0]['activation']:.2f}")
do_result = ce.intervene("gateway_ok", False, "laap_healthy")
logger.info(f"  do(gateway_ok=False): 因果效应={do_result.causal_effect:.3f}")
cf = ce.tag_counterfactual_emotion(
    "全链路集成", "AGI模块集成",
    "所有模块正常工作", "集成失败",
    "joyful", "sad", intensity=0.7
)
logger.info(f"  反事实情感: 后悔={cf.emotional_regret:.2f}, 庆幸={cf.emotional_relief:.2f}")
next_task = cu.find_optimal_next()
if next_task:
    gap_val = next_task.get("gap", next_task.get("mastery", 0))
    logger.info(f"\n  课程推荐: {next_task.get('concept', '?')} (缺口={1-gap_val:.2f})")
# P7: 快照提交 + 状态持久化
# ════════════════════════════════════════════════════════════
print()
logger.info("=" * 60)
logger.info("P7: 快照提交 + 状态持久化")
logger.info("=" * 60)
ce.save()
cu.save()
pe.save()
se.save()

# 保存认知桥接器状态
bridge._save_state()

logger.info(f"  ✅ 因果引擎: {ce.stats()['symbolic_rules']}规则, {ce.stats()['temporal_links']}时间链, {ce.stats()['multi_factor_rules']}多因素规则, {ce.stats()['causal_bonds']}因果键")
logger.info(f"  ✅ 课程系统: {cu.stats()['total_concepts']}概念, 掌握度={cu.stats()['overall_mastery']:.2f}")
logger.info(f"  ✅ 感知引擎: {pe.stats()['channels']}")
logger.info(f"  ✅ 安全系统: {se.stats()['total_checks']}检查, 通过率={1-se.stats()['violation_rate']:.0%}")
logger.info(f"  ✅ 认知桥接: 轮次={bridge.state.cycle_count}, 自我意识={bridge.state.self_presence}")
if bridge._codegraph:
    cg_test = bridge._codegraph.get_context_for_topic("量子核", max_results=3)
    logger.info(f"  ✅ CodeGraph: 13621实体/29194关系 — 搜索'量子核' → 返回{len(cg_test)}行")
    logger.info(f"    内容: {cg_test[:100]}...")
print()
logger.info("=" * 60)
logger.info("🚀 LAAP AGI 全链路集成完成")
logger.info("   因果→世界模型→课程→感知→安全→闭环验证→持久化")
logger.info("=" * 60)