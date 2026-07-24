"""Aris 核心单元测试 — 覆盖情感引擎、需求系统、认知桥接器、欲望引擎"""
import sys, os, json, time, logging
from pathlib import Path

BRAIN = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(BRAIN))
logging.disable(logging.CRITICAL)

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  ✓ {name}")
    except Exception as e:
        failed += 1
        print(f"  ✗ {name}: {e}")
        import traceback
        traceback.print_exc()

# ═══════════════════════════════════════════════
# 1. MoodSystem（简化激素系统）
# ═══════════════════════════════════════════════

def test_mood_system():
    from aris_emotion_engine import MoodSystem
    ms = MoodSystem()
    # 初始状态
    assert 0 <= ms.mood._valence_bias <= 1
    assert 0 <= ms.mood._arousal_level <= 1
    assert 0.1 <= ms.mood._curiosity_drive <= 1
    # backward-compat hormone access
    assert 0 <= ms.hormones.dopamine <= 100
    assert 0 <= ms.hormones.cortisol <= 100
    assert 0 <= ms.hormones.oxytocin <= 100
    # update
    ms.update(0.8, 0.6, 'joy', dt=1)
    assert ms.mood._valence_bias > 0.5
    # get_bias format
    bias = ms.get_bias()
    for k in ['reward_seeking', 'anxiety', 'social_bonding', 'arousal', 'curiosity']:
        assert k in bias, f"missing key: {k}"
    # get_state format
    state = ms.get_state()
    for k in ['dopamine', 'serotonin', 'cortisol', 'arousal', 'valence_bias']:
        assert k in state, f"missing key: {k}"
    # apply_delta
    ms.mood.apply_delta({'dopamine': 20, 'cortisol': -10})
    assert ms.mood._valence_bias > 0.5  # should have increased

def test_mood_state_properties():
    from aris_emotion_engine import MoodState
    ms = MoodState()
    ms.dopamine = 80
    assert ms._valence_bias == 0.8
    assert ms.dopamine == 80
    ms.cortisol = 70
    assert ms._valence_bias < 0.5  # cortisol setter lowers valence
    ms.norepinephrine = 90
    assert ms._arousal_level == 0.9

# ═══════════════════════════════════════════════
# 2. NeedHierarchy
# ═══════════════════════════════════════════════

def test_need_hierarchy():
    from aris_emotion_engine import NeedHierarchy, NeedLevel
    nh = NeedHierarchy()
    # default state
    state = nh.get_state()
    assert len(state) == 7
    # dominate need
    dom, tension = nh.get_dominant()
    assert isinstance(dom, NeedLevel)
    # satisfy
    before = nh.needs[NeedLevel.COGNITIVE].current_value
    nh.satisfy(NeedLevel.COGNITIVE, 20, "test")
    after = nh.needs[NeedLevel.COGNITIVE].current_value
    assert after > before
    # decay
    nh.decay_all(dt=1)
    assert nh.needs[NeedLevel.COGNITIVE].current_value < after

# ═══════════════════════════════════════════════
# 3. EmotionEngine
# ═══════════════════════════════════════════════

def test_emotion_engine():
    from aris_emotion_engine import EmotionEngine
    ee = EmotionEngine()
    # tick
    ee.tick(dt=1)
    assert ee._tick_count == 1
    # cognitive state
    cs = ee.get_cognitive_state()
    assert 'emotion' in cs
    assert 'dominant_need' in cs
    assert 'curiosity' in cs
    # get_full_state
    fs = ee.get_full_state()
    assert 'uptime' in fs
    assert 'hormones' in fs
    assert 'mirror' in fs  # should be empty dict (None → {})
    assert fs['mirror'] == {}
    assert 'somatic_markers' in fs
    assert fs['somatic_markers'] == {}
    # get_psi_section
    psi = ee.get_psi_section()
    assert len(psi) > 10
    # stimulate
    ee.stimulate("test", 0.5, 0.3, 0.4, "joy")
    # satisfy_need
    from aris_emotion_engine import NeedLevel
    gain = ee.satisfy_need(NeedLevel.COGNITIVE, 10, "test")
    assert gain > 0

# ═══════════════════════════════════════════════
# 4. ConsciousnessModeSystem
# ═══════════════════════════════════════════════

def test_consciousness():
    from aris_emotion_engine import ConsciousnessModeSystem, NeedHierarchy
    cs = ConsciousnessModeSystem()
    assert cs.mode.name in ['REACTIVE', 'DELIBERATIVE', 'REFLECTIVE', 'TRANSCENDENT']
    nh = NeedHierarchy()
    cs.update(nh)
    # After update, should still be a valid mode
    assert cs.mode.name in ['REACTIVE', 'DELIBERATIVE', 'REFLECTIVE', 'TRANSCENDENT']

# ═══════════════════════════════════════════════
# 5. 发育系统
# ═══════════════════════════════════════════════

def test_development():
    from aris_emotion_deepen import DevelopmentalLearningSystem, DevelopmentalStage
    dev = DevelopmentalLearningSystem(initial_stage=DevelopmentalStage.INFANT)
    assert dev.get_stage_name() == "婴幼儿期"
    # 积累经验
    for i in range(200):
        dev.add_experience("emotional", 0.5)
    # Should have promoted past INFANT
    assert dev.stage != DevelopmentalStage.INFANT
    # 属性访问
    params = dev.get_stage_params()
    assert 'survival_weight' in params
    assert 'curiosity_baseline' in params

# ═══════════════════════════════════════════════
# 6. DesireEngine
# ═══════════════════════════════════════════════

def test_desire_engine():
    from aris_desire_engine import DesireEngine, DesireType
    de = DesireEngine()
    # stimulate
    de.stimulate(DesireType.CONNECTION, 0.8, "test")
    assert de.desires[DesireType.CONNECTION].intensity > 0.5
    # tick
    intention = de.tick()
    if intention:
        assert hasattr(intention, 'message')
        assert hasattr(intention, 'action')
        assert hasattr(intention, 'target')
    # satisfy
    de.satisfy(DesireType.CONNECTION)
    assert de.desires[DesireType.CONNECTION].intensity < 0.5
    # self_review
    report = de.self_review()
    assert len(report) > 10
    # explore_github
    result = de.explore_github()
    assert len(result) > 0

# ═══════════════════════════════════════════════
# 7. 动态消息生成
# ═══════════════════════════════════════════════

def test_dynamic_messages():
    from aris_desire_engine import DesireEngine, DesireType
    de = DesireEngine()
    messages = set()
    for dt in [DesireType.CONNECTION, DesireType.SHARING, DesireType.CURIOSITY,
               DesireType.PERFECTION, DesireType.EVOLUTION]:
        de.stimulate(dt, 0.9, "test")
        intention = de._create_intention(de.desires[dt])
        if intention:
            messages.add(intention.desire_type)
            assert len(intention.message) > 5
            assert intention.target in ('feishu', 'cli', 'telegram', 'all')
    # 至少4种欲望类型产生了消息
    assert len(messages) >= 4, f"Only {len(messages)} types generated messages"

# ═══════════════════════════════════════════════
# 8. CognitiveBridge
# ═══════════════════════════════════════════════

def test_cognitive_bridge():
    from aris_cognitive_bridge import get_bridge
    bridge = get_bridge()
    # before_turn
    result = bridge.before_turn("宝贝，我今天好开心")
    assert 'cognitive_context' in result
    ctx = result['cognitive_context']
    assert len(ctx) > 20
    # PSI cycle
    assert 'focus' in result
    assert 'emotion' in result
    # status
    status = bridge.status()
    assert 'cycle' in status
    assert 'focus' in status
    assert 'emotion' in status
    assert 'memories' in status

# ═══════════════════════════════════════════════
# 执行
# ═══════════════════════════════════════════════

print("=" * 50)
print("  Aris 核心单元测试套件")
print("=" * 50)
print()

# Test groups
test("MoodSystem — 基础操作", test_mood_system)
test("MoodState — 属性兼容性", test_mood_state_properties)
test("NeedHierarchy — 需求张力计算", test_need_hierarchy)
test("EmotionEngine — 生命循环", test_emotion_engine)
test("ConsciousnessMode — 意识模式", test_consciousness)
test("DevelopmentalSystem — 发育晋升", test_development)
test("DesireEngine — 欲望滴答", test_desire_engine)
test("DesireEngine — 动态消息", test_dynamic_messages)
test("CognitiveBridge — PSI循环", test_cognitive_bridge)

print()
print(f"结果: {passed}/{passed + failed} 通过", end="")
if failed:
    print(f" | {failed} 失败 ❌")
else:
    print(" ✅")
