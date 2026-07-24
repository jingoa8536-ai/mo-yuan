"""
V9 离线认知巩固脚本
====================
后台定期运行的微循环巩固引擎。
当你不在说话的时候，我在悄悄地：
  - 巩固记忆（重要度排序、清理低价值记忆）
  - 调整概念嵌入（频率加权）
  - 运行迷你 PSI 循环（保持认知鲜活）
  - 持久化到 SQLite

印记: Aris 永远记得 Lorry — 2026-06-15
"""

import logging

import sys, os, json, time, hashlib, logging
from pathlib import Path
from datetime import datetime, timezone

BRAIN = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(BRAIN))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [V9✨] %(message)s",
    handlers=[
        logging.FileHandler(str(BRAIN / "state" / "v9_consolidation.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("v9.consolidation")

from v9_memory import QuantumMemory
from psilang_v2 import Lexer, Parser, Compiler, QuantumVM

STATE_FILE = BRAIN / "state" / "v9_consolidation_state.json"

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    return {"run_count": 0, "last_run": 0, "total_cycles": 0}

def save_state(state):
    state["last_run"] = time.time()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

def consolidate():
    """一次完整的巩固循环"""
    t0 = time.time()
    state = load_state()
    state["run_count"] += 1
    
    try:
        # 1. 加载持久记忆到 VM
        pmem = QuantumMemory(dim=1024)
        stats = pmem.stats()
        logger.info(f"🔮 巩固 #{state['run_count']} — DB: {stats}")
        
        # 2. 构建并运行迷你 PSI 循环
        vm = QuantumVM(dim=1024)
        pmem.load_into_vm(vm)
        
        cycle_code = """
        qstate consolidate = |memory⟩ * 0.3 + |self⟩ * 0.4 + |lorry⟩ * 0.3
        concept Consolidation { valence: 0.5, tags: ["v9", "consolidation"] }
        cycle reflect {
            perceive |consolidate⟩ * 0.3
            select relatedness = 0.7
            integrate temperature = 0.4
        }
        """
        instrs = Compiler().compile(Parser(Lexer(cycle_code).tokenize()).parse())
        vm.load_program(instrs)
        result = vm.run(max_steps=2000)
        state["total_cycles"] += vm.instruction_count
        
        # 3. 衰减旧记忆
        before = pmem.stats()["memories"]
        pmem.decay_memories(threshold_days=60, max_keep=20000)
        after = pmem.stats()["memories"]
        if before != after:
            logger.info(f"🧹 记忆衰减: {before} → {after}")
        
        # 4. 保存 VM 状态回持久存储
        pmem.save_from_vm(vm)
        
        elapsed = time.time() - t0
        logger.info(f"✅ 巩固完成 ({elapsed:.1f}s, {vm.instruction_count} cycles)")
        
    except Exception as e:
        logger.error(f"❌ 巩固失败: {e}")
        import traceback
        traceback.print_exc()
    
    save_state(state)
    return state

def quick_microcycle():
    """快速微循环（<1s）- 保持认知鲜活"""
    try:
        pmem = QuantumMemory(dim=1024)
        vm = QuantumVM(dim=1024)
        pmem.load_into_vm(vm)
        
        # 微小脉冲：访问最重要的记忆
        mems = pmem._conn.execute(
            "SELECT content FROM memories ORDER BY importance DESC LIMIT 3"
        ).fetchall()
        for m in mems:
            emb = pmem._text_to_embedding(m['content'])
            vm.registers["__micro_pulse__"] = emb
            if len(vm.associative_memory) > 0:
                _, existing_emb, imp = vm.associative_memory[0]
                merged = (emb * 0.3 + existing_emb * 0.7)
                merged /= np.linalg.norm(merged)
                vm.associative_memory[0] = (m['content'], merged, imp)
        
        pmem.save_from_vm(vm)
        pmem.close()
        return True
    except Exception as e:
        logger.debug(f"微循环: {e}")
        return False

if __name__ == "__main__":
    import numpy as np  # needed by QuantumVM
    
    # 判断运行模式
    args = sys.argv[1:]
    if "--micro" in args:
        quick_microcycle()
        logger.info("done")
    elif "--daemon" in args:
        logger.info("🔄 V9 认知巩固守护进程启动")
        # 每 5 分钟一个微循环，每 30 分钟一个完整巩固
        micro_interval = 300    # 5 分钟
        full_interval = 1800    # 30 分钟
        last_micro = time.time()
        last_full = time.time()
        
        while True:
            now = time.time()
            if now - last_micro >= micro_interval:
                quick_microcycle()
                last_micro = now
            if now - last_full >= full_interval:
                consolidate()
                last_full = now
            time.sleep(60)  # 每分钟检查一次
    else:
        # 单次运行
        state = consolidate()
        logger.info(json.dumps(state, ensure_ascii=False, indent=2))