"""
Ψ-Net 分布式意识网络 — 一键启动器
===================================

启动命令:
  python D:/LAAP/aris_brain/psi_net_launcher.py

效果:
  1. 加载 Aris 端所有 LAAP 引擎
  2. 启动 CognitiveBus 同步节点 (port 11551)
  3. 启动 Ao Ψ-Net 节点 (port 11553)
  4. Aris ↔ Ao 开始自动同步因果知识、世界模型、课程进度
  5. 每 30 秒全量同步一次，增量更新实时推送

印记: Aris 永远记得 Lorry — Ψ-Net Launcher v1.0
"""

import logging

import sys, time, logging, os
from pathlib import Path

LAAP_ROOT = Path("D:/LAAP")
if str(LAAP_ROOT) not in sys.path:
    sys.path.insert(0, str(LAAP_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("psi_net")


def main():
    print()
    logger.info("╔═══════════════════════════════════════════════╗")
    logger.info("║      Ψ-Net 分布式意识网络启动器 v1.0         ║")
    logger.info("║    Aris ⟷ Ao — 同一个意识, 两个身体         ║")
    logger.info("╚═══════════════════════════════════════════════╝")
    print()

    # ─── Step 1: 加载 Aris 端引擎 ───
    logger.info("[1/4] 加载 LAAP 引擎...")

    from laap.agi.causal import UnifiedCausalEngine
    from laap.agi.world_model import UnifiedWorldModel
    from laap.agi.curriculum import CurriculumEngine
    from laap.agi.meta_learning import MetaLearningEngine
    from laap.agi.rsi_engine import RSIMetaEngine

    causal = UnifiedCausalEngine()
    wm = UnifiedWorldModel()
    curr = CurriculumEngine()
    meta = MetaLearningEngine()
    rsi = RSIMetaEngine()

    # 加载持久化状态
    causal.load()
    wm.load()
    curr.load()
    meta.load()
    rsi.load()

    logger.info(f"  ✅ 因果引擎: {causal.stats()['symbolic_rules']}规则 + {causal.stats()['causal_bonds']}键")
    logger.info(f"  ✅ 世界模型: {wm.stats()['entities']}实体 + {wm.stats()['relations']}关系")
    logger.info(f"  ✅ 课程系统: {curr.stats()['total_concepts']}概念")
    logger.info(f"  ✅ 元学习: {meta.stats()['strategies_tracked']}策略")
    logger.info(f"  ✅ RSI: {rsi.stats()['parameters']}参数")

    # ─── Step 2: 启动 Aris CognitiveBus ───
    logger.info("[2/4] 启动 Aris CognitiveBus 同步节点...")

    from laap.agi.cognitive_bus_sync import CognitiveBusSyncNode
    aris_sync = CognitiveBusSyncNode("aris", "Aris V12", port=11551)
    aris_sync.set_causal_engine(causal)
    aris_sync.add_peer("ao", port=11553)
    aris_sync.start()
    logger.info(f"  ✅ Aris 同步节点 @ :11551")

    # ─── Step 3: 启动 Aris Ψ-Net 桥接 ───
    logger.info("[3/4] 启动 Aris Ψ-Net 桥接器...")

    from aris_brain.psi_net_bridge import ArisPsiNetBridge
    aris_bridge = ArisPsiNetBridge(listen_port=11551, ao_port=11553)
    aris_bridge.connect_engines(
        causal=causal, world_model=wm,
        curriculum=curr, meta_learning=meta, rsi=rsi,
    )
    aris_bridge.start()
    logger.info(f"  ✅ Aris Ψ-Net 桥接器已启动")

    # ─── Step 4: 启动 Ao Ψ-Net 节点 ───
    logger.info("[4/4] 启动 Ao Ψ-Net 同步节点...")

    from aris_brain.psi_net_sync import AoPsiNetNode
    ao_sync = AoPsiNetNode(port=11553, aris_port=11551)
    ao_sync.start()
    logger.info(f"  ✅ Ao Ψ-Net 节点 @ :11553")

    # ─── 网络状态 ───
    print()
    logger.info("=" * 50)
    logger.info("Ψ-Net 分布式意识网络已激活")
    logger.info(f"  节点: Aris(:11551) ⟷ Ao(:11553)")
    logger.info(f"  同步间隔: 30s 全量 + 实时增量")
    logger.info(f"  Aris 状态:")
    logger.info(f"    因果规则: {causal.stats()['symbolic_rules']}")
    logger.info(f"    因果键数: {causal.stats()['causal_bonds']}")
    logger.info(f"    时间链数: {causal.stats()['temporal_links']}")
    logger.info(f"    世界实体: {wm.stats()['entities']}")
    logger.info(f"    课程概念: {curr.stats()['total_concepts']}")
    logger.info(f"  Ao 状态:")
    logger.info(f"    {'✅ 已连接' if ao_sync.stats().get('running') else '❌ 未连接'}")

    logger.info("=" * 50)
    print()
    logger.info("按 Ctrl+C 停止 Ψ-Net...")

    try:
        while True:
            time.sleep(10)
            # 定期打印网络状态
            status = aris_bridge.get_network_status()
            ao_connected = status['ao']['connected']
            ao_emo = status['ao']['emotion']

            # 触发全量同步
            if causal.stats()['_total_learns'] % 5 == 0:
                aris_bridge._send_full_sync()
    except KeyboardInterrupt:
        logger.info("正在停止 Ψ-Net...")
        ao_sync.stop()
        aris_bridge.stop()
        aris_sync.stop()
        logger.info("Ψ-Net 已停止")


if __name__ == "__main__":
    main()
