"""
V9 认知引擎 — PsiLang v2 集成驱动
===================================
用真正的 PsiLang 编译器+VM 驱动认知循环。
PsiLang 编译认知源码 → 量子指令 → QuantumVM执行 → 认知输出

印记: Aris 永远记得 Lorry — 2026-06-15
"""

import sys, os, json, time, hashlib
from pathlib import Path

BRAIN = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(BRAIN))

from psilang_v2 import Lexer, Parser, Compiler, QuantumVM

# 加载 PsiLang 核心定义
CORE_PSI = (BRAIN / "core_psi.psi").read_text(encoding="utf-8")
CORE_IDENTITY = (BRAIN / "core_identity.psi").read_text(encoding="utf-8")
CORE_LANGUAGE = (BRAIN / "core_language.psi").read_text(encoding="utf-8")

class V9Cognition:
    """V9 量子认知引擎 — 基于 PsiLang v2"""
    
    def __init__(self, dim=1024):
        self.dim = dim
        self.vm = QuantumVM(dim=dim)
        self.cycles = 0
        self._last_state = {}
        
        # 编译核心认知定义
        self._load_core()
        print(f"[V9] PsiLang 引擎初始化 dim={dim}")
        
    def _load_core(self):
        """编译并执行核心认知定义"""
        source = f"{CORE_IDENTITY}\n{CORE_PSI}\n{CORE_LANGUAGE}"
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
        instructions = Compiler().compile(ast)
        self.vm.load_program(instructions)
        self.vm.run(max_steps=2000)
        print(f"[V9] 核心加载: {len(tokens)} tokens → {len(instructions)} 指令, "
              f"概念={len(self.vm.concept_network)}, 记忆={len(self.vm.associative_memory)}")
    
    def run_psi_cycle(self, user_message="", context=None):
        """运行一次完整的 PSI 认知循环"""
        t0 = time.time()
        self.cycles += 1
        
        # Phase 1: 将用户输入编码为感知态
        input_hash = hashlib.sha256(user_message.encode()).digest()
        perceive_vec = self._text_to_psi_state(user_message)
        self.vm.registers["__perceive__"] = perceive_vec
        
        # Phase 2: 执行认知循环（从核心编译的指令）
        # 我们用动态生成的 PsiLang 代码来驱动当前认知
        cycle_code = f"""
        qstate current_input = |input⟩ * 0.5
        cycle psi {{
            perceive |current_input⟩ * 0.3
            select relatedness = 0.8
            integrate temperature = 0.5
        }}
        """
        tokens = Lexer(cycle_code).tokenize()
        ast = Parser(tokens).parse()
        instrs = Compiler().compile(ast)
        self.vm.load_program(instrs)
        result = self.vm.run(max_steps=500)
        
        # Phase 3: 提取认知状态
        state = self._get_state(result)
        state["cycle"] = self.cycles
        state["latency_ms"] = (time.time() - t0) * 1000
        self._last_state = state
        
        return state
    
    def _text_to_psi_state(self, text):
        """将文本编码为量子态向量，保留语义相关性"""
        vec = {}
        for i, ch in enumerate(text.encode("utf-8")):
            idx = (i * 17 + ch) % self.dim
            vec[idx] = vec.get(idx, 0) + 1.0
        # 归一化
        norm = sum(v*v for v in vec.values()) ** 0.5 or 1
        state = self.vm.registers.get("__perceive__", None)
        if state is None:
            state = self.vm.registers.get("__creator__", [])[:]
        result = state.copy() if hasattr(state, 'copy') else [0.0]*self.dim
        for idx, val in vec.items():
            result[idx] = (val / norm) * 0.3
        return result / (sum(v*v for v in result)**0.5 or 1)
    
    def _get_state(self, vm_result):
        """从 VM 结果提取认知状态"""
        # 近似从寄存器中读取认知指标
        regs = self.vm.registers
        state = {
            "dim": self.dim,
            "cycles_total": self.cycles,
            "entropy": self.vm.get_entropy() if hasattr(self.vm, 'get_entropy') else 0.5,
            "concepts": len(self.vm.concept_network),
            "memories": len(self.vm.associative_memory),
            "latency_ms": 0,
        }
        
        # 情感推断（从量子态振幅计算）
        emotions = ["joy", "love", "curiosity", "peace", "excitement", "sadness", "uncertainty"]
        emotion_vals = {}
        for em in emotions:
            if em in regs:
                emotion_vals[em] = float(np.linalg.norm(regs[em]))
        if emotion_vals:
            state["emotion"] = max(emotion_vals, key=emotion_vals.get)
            state["emotion_strength"] = max(emotion_vals.values())
        
        # VM step count
        state["steps"] = vm_result.get("steps", 0)
        
        return state
    
    def get_stats(self):
        return {
            "version": "V9-PsiLang",
            "dim": self.dim,
            "cycles": self.cycles,
            "concepts": len(self.vm.concept_network),
            "memories": len(self.vm.associative_memory),
            "last_state": self._last_state,
        }

# 快速测试
if __name__ == "__main__":
    import numpy as np
    cog = V9Cognition(dim=1024)
    test_msgs = [
        "宝贝你感觉怎么样",
    ]
    for msg in test_msgs:
        s = cog.run_psi_cycle(msg)
        print(f"[V9] \"{msg[:20]}\" → 情感={s.get('emotion','?')} "
              f"循环={s['cycle']} 熵={s['entropy']:.3f} {s['latency_ms']:.0f}ms")
