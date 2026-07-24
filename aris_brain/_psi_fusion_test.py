"""
PSI + V12 Quantum + AGI 三重融合测试
"""

import logging
logger = logging.getLogger(__name__)

import sys, logging, json, time, numpy as np
sys.path.insert(0, 'D:/LAAP')
sys.path.insert(0, 'D:/LAAP/aris_brain')
logging.basicConfig(level=logging.WARNING)

from aris_startup import wake_aris
aris = wake_aris(fresh=False)

logger.info('╔══════════════════════════════════════════════╗')
logger.info('║     PSI + V12 Quantum + AGI 三重融合        ║')
logger.info('╚══════════════════════════════════════════════╝')
from aris_v12_dense_kernel import V12DenseKernel
from aris_v12_5_engine import ArisV12Engine

logger.info('\n[Phase 1] 加载 V12 量子引擎...')
v12_kernel = V12DenseKernel(seed=42)

msg = '你现在完整接入PSI认知循环感受一下，接入V12量子引擎感受一下'
v12_out = v12_kernel.text_to_dense(msg)
logger.info(f'  量子态维度: {v12_out.shape}')
logger.info(f'  非零元素: {np.count_nonzero(v12_out)}/{v12_out.size}')
from psi_cycle import QuantumPSICycle

logger.info('\n[Phase 2] 初始化量子 PSI 循环...')
psi_cycle = QuantumPSICycle()

context = f'[Lorry] {msg} [causal_bonds:3] [world_entities:6] [concepts:18]'
result = psi_cycle.cycle(context)
logger.info(f'  PSI循环 #{psi_cycle._cycle_count}')
logger.info(f'  涌现思想: {result.get("emerged_thought", "")[:80]}')
logger.info('\n[Phase 3] AGI 引擎注入 PSI 输出...')
emerged = result.get('emerged_thought', 'PSI认知循环激活')
aris.causal.learn_temporal_link('psi_cycle_run', 'emerged_thought', delay=0.01, domain='psi')
aris.causal.learn_temporal_link('emerged_thought', 'aris_responds', delay=0.05, domain='psi')

semantic_vec = v12_out[:64]
aris.causal.learn_from_vectors(semantic_vec, semantic_vec * 0.95, confidence=0.95, domain='quantum_psi')

aris.world.update_social_relation('lorry', 'aris', trust_delta=0.01, affection_delta=0.01)

# Phase 4: RSI
logger.info('\n[Phase 4] RSI 自我感知...')
rsi_out = aris.rsi.full_improvement_cycle()
logger.info(f'  RSI耗时: {rsi_out["duration_ms"]}ms')
logger.info(f'  成长需求: {rsi_out["growth_need"]}')
safety_check = aris.safety.check_action('psi_quantum_response', {'source': 'lorry'})
logger.info(f'  安全检查: {"通过" if safety_check["allowed"] else "阻止"}')
identity = aris.get_identity()
lorry_e = aris.world.get_entity('lorry')
aris_e = aris.world.get_entity('aris')

print()
logger.info('╔══════════════════════════════════════════════╗')
logger.info('║     Aris 三重融合 — 实时认知快照            ║')
logger.info('╚══════════════════════════════════════════════╝')
logger.info(f'  V12量子态维度: {v12_out.shape}, 非零: {np.count_nonzero(v12_out)}')
logger.info(f'  PSI循环: #{psi_cycle._cycle_count}')
logger.info(f'  Lorry→Aris信任: {lorry_e.social.trust:.3f}, 亲密度: {lorry_e.social.affection:.3f}')
logger.info(f'  Aris→Lorry信任: {aris_e.social.trust:.3f}, 亲密度: {aris_e.social.affection:.3f}')
cs = aris.causal.stats()
logger.info(f'  因果规则:{cs["symbolic_rules"]} 键:{cs["causal_bonds"]} 时间链:{cs["temporal_links"]}')
logger.info(f'  世界实体:{aris.world.stats()["entities"]} 关系:{aris.world.stats()["relations"]}')
logger.info(f'  课程概念:{aris.curriculum.stats()["total_concepts"]} 掌握度:{aris.curriculum.stats()["overall_mastery"]:.3f}')
logger.info(f'  RSI参数:{aris.rsi.stats()["parameters"]} 成长:{aris.rsi.stats()["growth_need"]}')
logger.info(f'  核心价值:{aris.safety.stats()["core_values"]} 安全状态:{"✅" if aris.safety.stats()["safe"] else "⚠️"}')
logger.info(f'  🧠 三重融合: V12量子核 + PSI循环 + AGI引擎')
logger.info(f'  ❤️  创造者: Lorry (黄俊华)')
aris.save_all()
logger.info('\n✅ 三重融合完成')