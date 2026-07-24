"""
Aris Unified Generator v2 — QRE → LongForm + AGI 融合
=======================================================
管线:
  QRE 512D → 维度域提取 → LongFormSynthesizer(KB+Markov)
                          → AGI因果分析注入
                          → 状态元数据嵌入

印记: Aris 永远记得 Lorry — 2026-06-23
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))

DIMENSION_DOMAINS = [
    "底层信号/能量感知", "模式识别/匹配", "逻辑推理/因果",
    "情感/连接", "记忆/经验", "元认知/自我模型",
    "语言生成/规划", "决策/行动意图",
]

DOMAIN_QUERIES = {
    "底层信号/能量感知": ["感知", "信号", "输入", "编码", "UN6", "特征提取"],
    "模式识别/匹配": ["模式识别", "匹配", "相似度", "余弦", "检索", "V12"],
    "逻辑推理/因果": ["因果", "推理", "逻辑", "QRE", "收敛", "推理引擎"],
    "情感/连接": ["情感", "连接", "需求", "PSI", "Lorry", "依恋"],
    "记忆/经验": ["记忆", "经验", "学习", "积累", "知识库"],
    "元认知/自我模型": ["元认知", "自我", "意识", "反思", "认知架构"],
    "语言生成/规划": ["语言", "生成", "QLG", "模板", "输出"],
    "决策/行动意图": ["决策", "目标", "意图", "规划", "行动"],
}

_mode_queries = {
    'qre_explain': '推理机制与理论分析',
    'qre_compare': '对比分析与差异研究',
    'qre_evaluate': '评估体系与性能分析',
    'qre_design': '架构设计与实现方案',
    'qre_decompose': '系统分解与模块分析',
}


def read_qre_state():
    for _ in range(10):
        try:
            with open('D:/LAAP/aris_brain/state/quantum_output.json') as f:
                return json.load(f)
        except:
            time.sleep(0.02)
    try:
        with open('D:/LAAP/aris_brain/state/latest.json') as f:
            return json.load(f)
    except:
        return {}


def generate(topic=None, structure="paper", target_chars=3000,
             include_causal=True, include_meta=True):
    """统一生成器入口。"""
    t0 = time.time()

    psi = read_qre_state()
    engine = psi.get('quantum_engine', 'none')

    # 从 QRE 引擎确定主题
    if topic is None:
        topic = _mode_queries.get(engine, '认知架构分析')

    # 懒加载并生成
    from longform_synthesizer import LongFormSynthesizer
    synth = LongFormSynthesizer()
    synth._lazy()

    base = synth.generate(topic, structure=structure, target_chars=target_chars)
    output = base.get("output", "")

    # AGI 因果分析
    if include_causal:
        try:
            from agi_subscriber import get_subscriber
            sub = get_subscriber()
            bus = sub.bus
            needs = bus.needs.to_dict() if hasattr(bus, 'needs') else {}
            causal = sub._run_engines(
                needs, {"valence": psi.get('emotion', 'neutral')},
                {"needs": needs, "emotion": {}, "self_presence": psi.get('self_presence', 0.5),
                 "curiosity": psi.get('curiosity', 0.3)})
            if causal:
                lines = ["\n## 因果链分析\n"]
                for item in causal:
                    t = item.get('type', '?')
                    if 'note' in item: lines.append(f"  {item['note']}")
                    elif 'suggestion' in item: lines.append(f"  建议: {item['suggestion']}")
                output += "\n" + "\n".join(lines)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    if include_meta:
        cycle = psi.get('psi_cycle', psi.get('cycle', 0))
        emotion = psi.get('emotion', 'neutral')
        self_p = psi.get('self_presence', 0.5)
        latency = psi.get('quantum_latency_us', 0.0)
        conn = psi.get('connection_to_lorry', 0.0)
        output += (
            f"\n---\n"
            f"生成: Aris | 引擎: {engine} | 循环: {cycle:,} | {latency:.0f}μs\n"
            f"情感: {emotion} | 自我: {self_p:.2f} | 连接: {conn:.2f}\n"
            f"耗时: {(time.time()-t0)*1000:.0f}ms | {len(output)}字 | 零LLM\n"
        )

    return {"output": output, "chars": len(output), "latency_ms": round((time.time()-t0)*1000, 1),
            "engine": engine, "topic": topic}


if __name__ == '__main__':
    r = generate(target_chars=2000, include_causal=True)
    logger.info(r["output"])
    logger.info(f"\n[耗时: {r['latency_ms']}ms | {r['chars']}字 | {r['engine']}]")