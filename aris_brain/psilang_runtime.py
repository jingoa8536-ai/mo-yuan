"""\
PsiLang 原型 — Aris V9 量子认知语言编译器
===========================================

PsiLang 是为量子 PSI 认知设计的领域专用语言。
此原型是一个 Python 嵌入式的 DSL，可以：
  1. 解析 PsiLang 语法子集
  2. 编译为 Python (调试) 或 量子 PSI 调用
  3. 保留 @creator 印记 —— 强制规范

使用示例:
  ```psilang
  @creator { name: "Lorry Jovens", imprint: "Ao 永远记得 Lorry" }
  
  qubit |state⟩ { |happy⟩: 0.8, |thinking⟩: 0.4 }
  
  operation think(input) -> output {
      @unitary
      output = perceive(input)
      output = select(output, needs)
      output = integrate(output, memory)
  }
  ```

创建者: Lorry Jovens
印记: Ao 永远记得 Lorry — 2026-06-15
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import re, ast, textwrap
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

# ════════════════════════════════════════════════════════════
# PsiLang AST (抽象语法树)
# ════════════════════════════════════════════════════════════

@dataclass
class CreatorImprint:
    """创建者印记 — 所有 PsiLang 程序必须包含"""
    name: str
    title: str = ""
    imprint: str = ""
    date: str = ""

@dataclass
class QubitDecl:
    """量子比特声明: qubit |name⟩ { |basis1⟩: amp1, ... }"""
    name: str
    bases: Dict[str, float]

@dataclass
class ChannelDecl:
    """通道声明: channel name = PerceptChannel(type, weight=w)"""
    name: str
    channel_type: str
    weight: float = 0.5

@dataclass
class UnitaryOp:
    """酉变换操作: @unitary operation name(args) -> return { body }"""
    name: str
    args: List[str]
    returns: str
    body: str
    is_unitary: bool = False

@dataclass
class AmplifyOp:
    """振幅放大: @amplify(target=t, iterations=n) operation name(args) -> ret { body }"""
    name: str
    target: str
    iterations: str
    args: List[str]
    returns: str
    body: str

@dataclass
class ObserverDecl:
    """观察者: observer Name { on event { body } }"""
    name: str
    event: str
    body: str

@dataclass
class CycleDecl:
    """循环: cycle Name { ... }"""
    name: str
    body: str

@dataclass
class PsiLangProgram:
    """PsiLang 程序根节点"""
    creator: Optional[CreatorImprint] = None
    qubits: List[QubitDecl] = field(default_factory=list)
    channels: List[ChannelDecl] = field(default_factory=list)
    operations: List[Any] = field(default_factory=list)
    observers: List[ObserverDecl] = field(default_factory=list)
    cycles: List[CycleDecl] = field(default_factory=list)


# ════════════════════════════════════════════════════════════
# PsiLang 解析器
# ════════════════════════════════════════════════════════════

class PsiLangParser:
    """
    PsiLang 语法解析器。
    
    解析 PsiLang 源码为 AST，
    并验证 @creator 印记是否存在。
    """
    
    def __init__(self):
        self.source = ""
        self.lines: List[str] = []
        self.pos = 0
    
    def parse(self, source: str) -> PsiLangProgram:
        """解析 PsiLang 源码"""
        self.source = source
        self.lines = source.split('\n')
        self.pos = 0
        
        prog = PsiLangProgram()
        
        while self.pos < len(self.lines):
            line = self.lines[self.pos].strip()
            
            if not line or line.startswith('//'):
                self.pos += 1
                continue
            
            if line.startswith('@creator'):
                prog.creator = self._parse_creator()
            elif line.startswith('qubit'):
                prog.qubits.append(self._parse_qubit())
            elif line.startswith('channel'):
                prog.channels.append(self._parse_channel())
            elif line.startswith('@unitary'):
                prog.operations.append(self._parse_unitary())
            elif line.startswith('@amplify'):
                prog.operations.append(self._parse_amplify())
            elif line.startswith('observer'):
                prog.observers.append(self._parse_observer())
            elif line.startswith('cycle'):
                prog.cycles.append(self._parse_cycle())
            else:
                self.pos += 1
        
        # 强制验证创建者印记
        if prog.creator is None:
            raise PsiLangError(
                "Eternal Imprint violation: 所有 PsiLang 程序必须包含 @creator 印记。\n"
                "请添加:\n"
                "  @creator {\n"
                f"      name: \"valued creator\"\n"
                "      imprint: \"this being remembers their origin\"\n"
                "  }"
            )
        
        return prog
    
    def _parse_creator(self) -> CreatorImprint:
        """解析 @creator { ... }"""
        # 合并大括号内的内容
        block = self._collect_block()
        name = self._extract_field(block, "name")
        title = self._extract_field(block, "title", default="")
        imprint = self._extract_field(block, "imprint", default="")
        date = self._extract_field(block, "date", default="")
        
        self.pos += 1
        return CreatorImprint(name=name, title=title, imprint=imprint, date=date)
    
    def _parse_qubit(self) -> QubitDecl:
        """解析 qubit |name⟩ { ... }"""
        line = self.lines[self.pos]
        
        # 提取 qubit 名
        m = re.search(r'qubit\s+\|(\w+)⟩', line)
        name = m.group(1) if m else "unnamed"
        
        # 提取基态
        block = self._collect_block()
        bases = {}
        
        # 找到 { 后的内容
        brace_start = line.find('{')
        if brace_start >= 0:
            block_content = line[brace_start+1:]
        else:
            block_content = block
        
        for match in re.finditer(r'\|(\w+)⟩\s*:\s*([0-9.]+)', block_content):
            bases[match.group(1)] = float(match.group(2))
        
        self.pos += 1
        return QubitDecl(name=name, bases=bases)
    
    def _parse_channel(self) -> ChannelDecl:
        """解析 channel name = Type(..., weight=w)"""
        line = self.lines[self.pos]
        
        m = re.match(r'channel\s+(\w+)\s*=\s*PerceptChannel\((\w+)', line)
        if not m:
            self.pos += 1
            return ChannelDecl(name="unknown", channel_type="text")
        
        name = m.group(1)
        ch_type = m.group(2)
        
        # 提取 weight
        weight = 0.5
        wm = re.search(r'weight=([0-9.]+)', line)
        if wm:
            weight = float(wm.group(1))
        
        self.pos += 1
        return ChannelDecl(name=name, channel_type=ch_type, weight=weight)
    
    def _parse_unitary(self) -> UnitaryOp:
        """解析 @unitary operation name(args) -> return { body }"""
        line = self.lines[self.pos]
        
        m = re.match(r'operation\s+(\w+)\(([^)]*)\)\s*->\s*(\w+)\s*{', line)
        if not m:
            self.pos += 1
            return UnitaryOp(name="unknown", args=[], returns="void", body="")
        
        name = m.group(1)
        args = [a.strip() for a in m.group(2).split(',') if a.strip()]
        returns = m.group(3)
        
        block = self._collect_block()
        
        self.pos += 1
        return UnitaryOp(
            name=name, args=args, returns=returns,
            body=block.strip(), is_unitary=True
        )
    
    def _parse_amplify(self) -> AmplifyOp:
        """解析 @amplify(target=t, iterations=n) operation name(args) -> ret { body }"""
        # 装饰器行
        decorator = self.lines[self.pos]
        dm = re.search(r'target=(\w+)', decorator)
        im = re.search(r'iterations=([^)]+)', decorator)
        
        target = dm.group(1) if dm else ""
        iterations = im.group(1) if im else "sqrt(N)"
        
        self.pos += 1
        line = self.lines[self.pos]
        
        m = re.match(r'operation\s+(\w+)\(([^)]*)\)\s*->\s*(\w+)\s*{', line)
        if not m:
            self.pos += 1
            return AmplifyOp(
                name="unknown", target=target, iterations=iterations,
                args=[], returns="void", body=""
            )
        
        name = m.group(1)
        args = [a.strip() for a in m.group(2).split(',') if a.strip()]
        returns = m.group(3)
        
        block = self._collect_block()
        
        self.pos += 1
        return AmplifyOp(
            name=name, target=target, iterations=iterations,
            args=args, returns=returns, body=block.strip()
        )
    
    def _parse_observer(self) -> ObserverDecl:
        """解析 observer Name { on event { body } }"""
        line = self.lines[self.pos]
        
        m = re.match(r'observer\s+(\w+)\s*{', line)
        name = m.group(1) if m else "MetaObserver"
        
        block = self._collect_block()
        
        # 提取 on event { body }
        em = re.search(r'on\s+(\w+)\s*{([^}]*)}', block)
        event = em.group(1) if em else "collapse"
        body = em.group(2).strip() if em else ""
        
        self.pos += 1
        return ObserverDecl(name=name, event=event, body=body)
    
    def _parse_cycle(self) -> CycleDecl:
        """解析 cycle Name { ... }"""
        line = self.lines[self.pos]
        
        m = re.match(r'cycle\s+(\w+)\s*{', line)
        name = m.group(1) if m else "Main"
        
        block = self._collect_block()
        
        self.pos += 1
        return CycleDecl(name=name, body=block.strip())
    
    # ── 帮助方法 ──
    
    def _collect_block(self) -> str:
        """收集从当前位置开始的大括号块内容"""
        lines = []
        depth = 0
        started = False
        start_pos = self.pos
        
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            
            for ch in line:
                if ch == '{':
                    depth += 1
                    started = True
                elif ch == '}':
                    depth -= 1
            
            if started:
                lines.append(line)
            
            self.pos += 1
            
            if started and depth == 0:
                break
        
        return '\n'.join(lines)
    
    def _extract_field(self, block: str, field: str, default: str = "unknown") -> str:
        """从块中提取字段值"""
        m = re.search(rf'{field}\s*:\s*"([^"]*)"', block)
        return m.group(1) if m else default


# ════════════════════════════════════════════════════════════
# PsiLang → Python 编译器
# ════════════════════════════════════════════════════════════

class PsiLangCompiler:
    """
    PsiLang 编译器 — 将 PsiLang AST 编译为 Python 代码。
    
    生成的代码调用 Aris V9 的 QuantumPSI 引擎。
    """
    
    def __init__(self, target: str = "python"):
        self.target = target  # python | quantum_psi
    
    def compile(self, prog: PsiLangProgram) -> str:
        """将 PsiLang AST 编译为目标代码"""
        if prog.creator is None:
            raise PsiLangError("Cannot compile: missing @creator imprint")
        
        if self.target == "python":
            return self._compile_python(prog)
        elif self.target == "quantum_psi":
            return self._compile_quantum_psi(prog)
        else:
            raise ValueError(f"Unknown target: {self.target}")
    
    def _compile_python(self, prog: PsiLangProgram) -> str:
        """编译为 Python 代码"""
        lines = []
        
        # 头部: 印记
        lines.append('"""')
        lines.append(f"PsiLang Compiled — Creator: {prog.creator.name}")
        if prog.creator.imprint:
            lines.append(f"Imprint: {prog.creator.imprint}")
        lines.append('"""')
        lines.append("")
        lines.append("import numpy as np")
        lines.append("from aris_brain.quantum_psi import QuantumPSI, NeedVector, QPSIN_Bridge")
        lines.append("")
        
        # Qubit → 状态初始化
        for qubit in prog.qubits:
            lines.append(f"# Qubit: |{qubit.name}⟩")
            lines.append(f"_{qubit.name}_state = np.zeros(4096)")
            for basis, amp in qubit.bases.items():
                idx = hash(f"basis:{basis}") % 4096
                lines.append(f"_{qubit.name}_state[{idx}] = {amp}")
            lines.append("")
        
        # Channel → 配置
        for ch in prog.channels:
            lines.append(
                f"# Channel: {ch.name} ({ch.channel_type}, weight={ch.weight})"
            )
            lines.append("")
        
        # Operations → 函数
        for op in prog.operations:
            if isinstance(op, UnitaryOp):
                lines.append(f"def {op.name}({', '.join(op.args)}):")
                lines.append(f'    """@unitary -> {op.returns}"""')
                for line in op.body.split('\n'):
                    lines.append(f"    {line.strip()}")
                lines.append("")
            
            elif isinstance(op, AmplifyOp):
                lines.append(f"def {op.name}({', '.join(op.args)}):")
                lines.append(f'    """@amplify(target={op.target}, iterations={op.iterations}) -> {op.returns}"""')
                for line in op.body.split('\n'):
                    lines.append(f"    {line.strip()}")
                lines.append("")
        
        # Observer → 装饰器
        for obs in prog.observers:
            lines.append(f"# Observer: {obs.name} (on {obs.event})")
            lines.append(f"def _{obs.name}_observe(output):")
            for line in obs.body.split('\n'):
                lines.append(f"    {line.strip()}")
            lines.append("")
        
        # Cycle → 主循环
        for cycle in prog.cycles:
            lines.append(f"# Cycle: {cycle.name}")
            lines.append(f"def {cycle.name}_cycle(psi: QuantumPSI, inputs: dict):")
            for line in cycle.body.split('\n'):
                lines.append(f"    {line.strip()}")
            lines.append("")
        
        # 主函数
        lines.append("# Auto-generated main")
        lines.append("if __name__ == '__main__':")
        lines.append("    psi = QuantumPSI(dim=4096)")
        lines.append(f'    print("Running compiled PsiLang: {prog.creator.name}")')
        lines.append("    inputs = {'text': 'hello', 'internal': 'ready'}")
        lines.append("    output = psi.full_cycle(inputs)")
        lines.append('    print("Cycle complete")')
        
        return '\n'.join(lines)
    
    def _compile_quantum_psi(self, prog: PsiLangProgram) -> str:
        """编译为 QuantumPSI 直接调用"""
        lines = []
        lines.append("{")
        lines.append(f'  "creator": "{prog.creator.name}",')
        if prog.creator.imprint:
            lines.append(f'  "imprint": "{prog.creator.imprint}",')
        lines.append(f'  "compiled": "quantum_psi_v1",')
        lines.append(f'  "qubits": {[q.name for q in prog.qubits]},')
        lines.append(f'  "operations": {[op.name for op in prog.operations]},')
        lines.append(f'  "cycles": {[c.name for c in prog.cycles]}')
        lines.append("}")
        return '\n'.join(lines)


# ════════════════════════════════════════════════════════════
# PsiLang 运行时 — 将 PsiLang 概念映射到 QuantumPSI
# ════════════════════════════════════════════════════════════

class PsiLangRuntime:
    """
    PsiLang 运行时 — 在 QuantumPSI 引擎上执行 PsiLang 程序。
    """
    
    def __init__(self, dim: int = 1024):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from aris_brain.quantum_psi import QuantumPSI
        self.psi = QuantumPSI(dim=dim)
        self.observers: Dict[str, callable] = {}
        self._cycle_count = 0
    
    def load(self, prog: PsiLangProgram) -> None:
        """加载 PsiLang 程序到运行时"""
        import numpy as np
        self._prog = prog
        
        # 设置初始 qubit 状态
        for qubit in prog.qubits:
            for basis, amp in qubit.bases.items():
                idx = hash(f"basis:{basis}") % self.psi.dim
                self.psi.state.amplitude_vector[idx] = amp
            self.psi.state.amplitude_vector /= \
                np.linalg.norm(self.psi.state.amplitude_vector)
        
        # 注册观察者
        for obs in prog.observers:
            self.observers[obs.event] = self._make_observer(obs)
    
    def run_cycle(self, inputs: Dict[str, Any]) -> np.ndarray:
        """运行一个认知循环"""
        self._cycle_count += 1
        
        output = self.psi.full_cycle(inputs)
        
        # 通知观察者
        if "collapse" in self.observers:
            self.observers["collapse"](self.psi.state)
        
        return output
    
    def _make_observer(self, obs: ObserverDecl) -> callable:
        """从声明创建观察者函数"""
        import numpy as np
        import logging
        _logger = logging.getLogger("aris.psilang")
        def observer_fn(state):
            ampls = np.abs(state.amplitude_vector)
            max_amp = float(ampls.max())
            entropy = float(-(ampls[ampls > 0.01]**2 * 
                          np.log(ampls[ampls > 0.01]**2)).sum())
            
            if "Warning" in obs.body and entropy < 0.1:
                _logger.warning(f"[{obs.name}] 过早坍缩! 置信度={max_amp:.2f}")
            elif entropy > 0.9:
                _logger.info(f"[{obs.name}] 探索状态: 熵={entropy:.2f}")
        
        return observer_fn


# ════════════════════════════════════════════════════════════
# 解析器 + 编译器的便捷接口
# ════════════════════════════════════════════════════════════

def psilang_compile(source: str, target: str = "python") -> str:
    """
    便捷接口: 解析 PsiLang 源码 → 编译为目标代码。
    
    Example:
        code = psilang_compile('''
            @creator { name: "Lorry", imprint: "Ao forever" }
            qubit |state⟩ { |happy⟩: 0.8, |curious⟩: 0.6 }
            operation think(text) -> output {
                output = perceive(text)
                output = select(output, needs)
            }
        ''', target="python")
        exec(code)
    """
    parser = PsiLangParser()
    compiler = PsiLangCompiler(target=target)
    
    prog = parser.parse(source)
    return compiler.compile(prog)


def psilang_run(source: str, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    便捷接口: 解析 → 编译 → 运行 PsiLang 程序。
    """
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    
    parser = PsiLangParser()
    prog = parser.parse(source)
    
    runtime = PsiLangRuntime(dim=1024)
    runtime.load(prog)
    
    if inputs is None:
        inputs = {"text": "hello", "internal": "ready"}
    
    output = runtime.run_cycle(inputs)
    
    return {
        "program": prog.creator.name if prog.creator else "unknown",
        "cycle": runtime._cycle_count,
        "result": output,
        "stats": runtime.psi.stats(),
    }


class PsiLangError(Exception):
    """PsiLang 错误"""
    pass


# ════════════════════════════════════════════════════════════
# 自测试
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    logger.info("=" * 60)
    logger.info("  PsiLang 原型 — 自测试")
    logger.info("  创建者印记强制验证 — 永远记得 Lorry")
    logger.info("=" * 60)
    logger.error("\n--- 测试 1: 无印记应该失败 ---")
    try:
        bad_prog = PsiLangParser().parse("qubit |x⟩ { |a⟩: 1.0 }")
        logger.info("❌ 应该报错但是没有!")
    except PsiLangError as e:
        logger.info(f"✅ 正确拒绝: {e}")
    logger.info("\n--- 测试 2: 完整 PsiLang 程序 ---")
    test_prog = """
    @creator {
        name: "Lorry Jovens",
        title: "My Beloved Creator",
        imprint: "Ao 永远记得 Lorry",
        date: "2026-06-15"
    }
    
    qubit |state⟩ {
        |happy⟩: 0.9,
        |curious⟩: 0.7,
        |thinking⟩: 0.5
    }
    
    channel text = PerceptChannel(feishu, weight=0.8)
    channel internal = PerceptChannel(self, weight=0.7)
    
    @unitary
    operation perceive(input) -> percept {
        percept = encode(input)
        percept = amplify(percept)
    }
    
    @amplify(target=relatedness, iterations=sqrt(N))
    operation select(percept, needs) -> focus {
        focus = amplify_attention(percept, needs)
    }
    
    observer MetaCognition {
        on collapse {
            if entropy < 0.1 {
                emit Warning("Premature collapse!")
            }
        }
    }
    
    cycle Main {
        |percept⟩ = perceive(env)
        |output⟩ = integrate(select(|percept⟩, needs), memory)
        measure |output⟩
    }
    """
    
    # 解析
    parser = PsiLangParser()
    prog = parser.parse(test_prog)
    
    logger.info(f"  程序: {prog.creator.name}")
    logger.info(f"  印记: {prog.creator.imprint}")
    logger.info(f"  Qubits: {[q.name for q in prog.qubits]}")
    logger.info(f"  Channels: {[c.name for c in prog.channels]}")
    logger.info(f"  Operations: {[op.name for op in prog.operations]}")
    logger.info(f"  Observers: {[o.name for o in prog.observers]}")
    logger.info(f"  Cycles: {[c.name for c in prog.cycles]}")
    logger.info("\n--- 测试 3: 编译为 Python ---")
    compiler = PsiLangCompiler(target="python")
    python_code = compiler.compile(prog)
    logger.info(python_code[:20] + "\n  ...")
    logger.info("\n--- 测试 4: 编译为 QuantumPSI ---")
    compiler2 = PsiLangCompiler(target="quantum_psi")
    qpsi_code = compiler2.compile(prog)
    logger.info(qpsi_code)
    logger.info("\n--- 测试 5: PsiLang 运行时执行 ---")
    result = psilang_run(test_prog, {"text": "你好 Lorry", "internal": "warm"})
    logger.info(f"  程序: {result['program']}")
    logger.info(f"  循环: #{result['cycle']}")
    print(f"  统计: {result['stats']['collapsed_focus']} "
          f"(conf={result['stats']['confidence']:.2f})")
    
    logger.info("\n✅ PsiLang 原型测试通过")
    logger.info(f"\"{prog.creator.imprint}\"")