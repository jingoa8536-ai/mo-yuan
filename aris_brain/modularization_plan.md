# Aris Brain — 5大文件模块化拆分方案

> 分析日期: 2026-06-21
> 目标: 将5个超过1000行的单文件拆分为功能独立、职责清晰的模块化包结构

---

## 1. aris_lm_v5.py (1661 行) — 量子语义理解引擎

**状态: [已废弃] 由 aris_lm_v11 取代，仅 v11_agi_daemon.py 中残留引用**

### 当前结构
| 组件 | 行数 | 说明 |
|------|------|------|
| Token | 7 | 词法单元 dataclass |
| ChineseTokenizer | 200 | 中文分词，含词库构建(158行) |
| DependencyRelation | 5 | 依存关系 dataclass |
| DependencyTree | 24 | 依存树数据结构 |
| DependencyParser | 109 | 依存句法分析(伪实现, 83行规则) |
| SemanticFrame | 33 | 语义框架(SVO) |
| SemanticRoleLabeler | 102 | 语义角色标注 |
| ConceptNode | 11 | 概念图节点 |
| ConceptGraph | 253 | 概念图(含157行层次构建) |
| SemanticComposer | 209 | 语义组合器(意图/情感/话题解析) |
| SelfVerifier | 80 | 自验证系统 |
| DiscourseState | 46 | 对话状态追踪 |
| SemanticResponseGenerator | 331 | 语义驱动回应生成(13个方法) |
| ArisLMv5 | 83 | 主入口类 |
| 顶层函数(3) | 5+2+2 | get_v5, aris_say, aris_understand |
| 自测 | ~55 | if __name__ |

### 拆分建议

因为该文件已废弃，建议仅做最小化拆分以保持向后兼容性：

```
aris_lm_v5/
├── __init__.py          # 导出 ArisLMv5, get_v5, aris_say, aris_understand
├── tokenizer.py         # Token, ChineseTokenizer
├── dependency.py        # DependencyRelation, DependencyTree, DependencyParser
├── semantics.py         # SemanticFrame, SemanticRoleLabeler
├── concept_graph.py     # ConceptNode, ConceptGraph
├── composer.py          # SemanticComposer
├── verifier.py          # SelfVerifier
├── discourse.py         # DiscourseState
├── response.py          # SemanticResponseGenerator
└── engine.py            # ArisLMv5 (主入口类)
```

或**更优方案**: 直接标记 `from aris_lm_v5 import X` 为 deprecated，引导使用者迁移到 `aris_lm_v11`。

---

## 2. psilang_v2.py (1575 行) — 量子认知语言

**状态: 活跃使用，被 agi_kernel.py, psi_cli.py, psilang_lm.py 等广泛引用**

### 当前结构
| 组件 | 行数 | 说明 |
|------|------|------|
| Opcode (Enum) | 37 | 量子指令集枚举 |
| TokenType (Enum) | 46 | 词法类型枚举 |
| Token | 8 | 词法单元 |
| Lexer | 171 | 词法分析器(tokenize 135行) |
| ASTNode + 18个子类 | ~140 | 18个AST节点类型(QuantumState, QStateDecl, BinaryOp, Assign, LetDecl, etc.) |
| Parser | 440 | 语法分析器(22个方法) |
| Instruction | 4 | 指令 dataclass |
| Compiler | 137 | 编译器(12个方法) |
| QuantumVM | 385 | 量子虚拟机(8个方法, _execute 276行) |
| 顶层函数(2) | 8+19 | psilang_compile, psilang_run |
| 自测 | ~90 | if __name__ |

### 拆分建议

核心问题是 AST 节点和 Parser/Compiler/VM 混在同一个文件中。

```
psilang_v2/
├── __init__.py              # 导出公共API: psilang_compile, psilang_run
├── opcodes.py               # Opcode 枚举
├── tokens.py                # TokenType, Token
├── ast_nodes.py             # ASTNode + 18个子类 (每个 ~3-7行)
├── lexer.py                 # Lexer
├── parser.py                # Parser (440行中最需要拆的)
├── compiler.py              # Compiler
├── vm.py                    # QuantumVM (QuantumVM._execute 276行可内部提炼子方法)
├── instructions.py          # Instruction dataclass
└── __main__.py              # 原自测代码
```

**Parser(440行)内部也可再拆分**: `parser.py` 中的22个 `_parse_*` 方法可分组:
- `_parse_qstate_decl`, `_parse_quantum_state`, `_parse_let_decl`, `_parse_assign` → 声明解析
- `_parse_cycle`, `_parse_amplify`, `_parse_entangle` → 量子操作解析
- `_parse_concept`, `_parse_observe` → 认知操作解析
- `_parse_rewrite`, `_parse_self_read`, `_parse_self_write` → 元操作解析
- `_parse_if`, `_parse_func_call`, `_parse_expression`, `_parse_primary` → 表达式解析

---

## 3. aris_v12_5_engine.py (1172 行) — 量子马尔科夫生成引擎

**状态: 活跃使用，被 aris_fusion_v15.py, aris_standalone.py 等广泛引用**

### 当前结构
| 组件 | 行数 | 说明 |
|------|------|------|
| V12SemanticCore | 242 | V12.1 语义核封装(话题检测/关键词/置信度) |
| MarkovChainV12 | 495 | 马尔科夫链生成器(19个方法, 占文件42%) |
| PSIModulator | 55 | PSI情绪调制器 |
| ArisV12Engine | 267 | 主引擎入口(协调上述三个组件) |
| 顶层函数(1) | 50 | run_benchmark |
| 自测 | ~2 | if __name__ |

### 拆分建议

MarkovChainV12 的 495 行是最大块，其内部有清晰的功能分组。

```
aris_v12_5_engine/
├── __init__.py                  # 导出 ArisV12Engine, run_benchmark
├── semantic_core.py             # V12SemanticCore
├── markov_chain.py              # MarkovChainV12 (495行, 可分为:)
│   ├── MarkovChainV12.__init__ + train*  → 训练方法 (train, train_from_file, train_corpus, _train_builtin) ~120行
│   ├── MarkovChainV12.save/load          → 持久化 ~37行
│   ├── MarkovChainV12.generate + _find_start_context + _sample_next + _sample_from_counter + _detokenize → 生成方法 ~233行
│   ├── MarkovChainV12._tokenize + _is_sentence_end → 分词 ~45行
│   └── MarkovChainV12._calc_coherence + _fallback + stats → 辅助方法 ~27行
├── psi_modulator.py             # PSIModulator
├── engine.py                    # ArisV12Engine
└── __main__.py                  # run_benchmark + 自测
```

**优化方案**: MarkovChainV12 的 495 行可以通过拆分为 mixin 类来组织:
```
markov_chain_base.py     — __init__, stats, _tokenize, _is_sentence_end (~60行)
markov_chain_train.py    — train, train_from_file, train_corpus, _train_builtin (~106行)
markov_chain_io.py       — save, load (~37行)
markov_chain_gen.py      — generate, _find_start_context, _sample_next, _sample_from_counter, _detokenize, _calc_coherence, _fallback (~256行)
```

---

## 4. brain.py (1126 行) — 核心编排器 (Aris Brain)

**状态: 最核心文件，被 cognitive_cycle.py, daemon.py 等大量引用**

### 当前结构
| 组件 | 行数 | 说明 |
|------|------|------|
| EmotionalValence (Enum) | 12 | 11种情绪值 |
| AttentionFocus (Enum) | 8 | 7种注意力焦点 |
| CognitiveNeed (Enum) | 6 | 5种认知需求 |
| CognitiveState | 67 | 认知状态 dataclass + to_dict/to_prompt_block |
| **ArisBrain** | **953** | **主脑类 (10个方法)** |

ArisBrain 内部方法分布:
| 方法 | 行数 | 说明 |
|------|------|------|
| `__init__` | 253 | 构造函数 — 加载18+个模块，每个都是 try/except 块 |
| `_init_modules` | 17 | 延迟加载 LAAP 认知模块 |
| `think` | 116 | 主认知循环入口 |
| `_perceive` | 99 | 第一阶段: 感知 |
| `_select` | 92 | 第二阶段: 注意力和需求选择 |
| `_integrate` | 102 | 第三阶段: 整合 |
| `learn` | 78 | 第四阶段: 学习 |
| `introspect` | 95 | 内省报告 |
| `save_state` | 46 | 持久化 |
| `reset` | 8 | 重置 |

### 拆分建议

这是五个文件中**设计最成熟**的——方法职责清晰，但 `__init__` 的 253 行是最大痛点（一个构造函数硬编码了18+个模块的加载逻辑）。

```
brain/
├── __init__.py                    # 导出 ArisBrain, CognitiveState, 三个Enum
├── types.py                       # EmotionalValence, AttentionFocus, CognitiveNeed, CognitiveState
├── aris_brain.py                  # ArisBrain (主类，去掉__init__中的模块加载)
|                                   #  包含: think, introspect, save_state, reset
├── brain_init.py                  # ArisBrain.__init__ 逻辑 — 模块注册/工厂方法
├── perception.py                  # ArisBrain._perceive (情感标记 + Tom观测)
├── attention.py                   # ArisBrain._select (注意力 + 需求动态)
├── integration.py                 # ArisBrain._integrate (绑定 + DMN + IPC)
├── learning.py                    # ArisBrain.learn (后处理学习 + 自动保存)
└── __main__.py                    # 自测
```

**优化方案**: `__init__` 的 253 行应采用"模块注册表"模式:

```python
# brain_init.py
MODULE_REGISTRY = [
    ("quantum_bridge", "aris_brain.quantum_bridge", "QuantumCognitiveBridge", {"dim": 512}),
    ("metacognition", "aris_brain.metacognition", "ArchitectureChangeDetector"),
    ("dmn", "aris_brain.dmn", "DefaultModeNetwork"),
    ("tom", "aris_brain.theory_of_mind", "TheoryOfMindEngine"),
    # ... etc
]

def load_brain_modules(brain: ArisBrain) -> Dict[str, Any]:
    """Lazy-load all registered modules with error handling."""
    modules = {}
    for attr_name, module_path, class_name, *kwargs in MODULE_REGISTRY:
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            if kwargs:
                modules[attr_name] = cls(brain=brain, **kwargs[0])
            else:
                modules[attr_name] = cls(brain=brain)
        except Exception as e:
            logger.warning(f"[Init] {attr_name} failed: {e}")
    return modules
```

---

## 5. ao_core.py (1106 行) — 单文件独立运行核心

**状态: 活跃使用，被 ao_bridge.py, ao_mobile.py, ao_server_1024d.py 等引用**

### 当前结构
| 组件 | 行数 | 说明 |
|------|------|------|
| AoConfig | 23 | 核心配置 dataclass |
| QuantumPSI | 249 | 量子 PSI 认知循环(8个方法) |
| VoiceAuth | 233 | 声纹认证(6个方法, extract_features 135行) |
| ConceptNet | 65 | 概念网络 |
| PhraseNet | 96 | 短语网络 |
| ArisLM | 75 | 语言模型(66行 speak 方法) |
| AndroidBridge | 81 | 安卓桥接(10个方法, 大部分 stub) |
| AoCore | 173 | 主核心类(9个方法, think 67行) |
| 自测 | ~42 | if __name__ |

### 拆分建议

组件边界非常清晰，大部分模块之间无循环依赖。

```
ao_core/
├── __init__.py              # 导出 AoCore, AoConfig, 及各模块
├── config.py                # AoConfig
├── quantum_psi.py           # QuantumPSI (PSI认知循环)
├── voice_auth.py            # VoiceAuth (声纹认证, 233行中extract_features 135行可内部分组)
├── concept_net.py           # ConceptNet
├── phrase_net.py            # PhraseNet
├── aris_lm.py               # ArisLM
├── android_bridge.py        # AndroidBridge
├── core.py                  # AoCore (主核心类)
└── __main__.py              # 自测代码
```

VoiceAuth 的 `extract_features(135行)` 内含 `_create_mel_filterbank`，可进一步内部分组：
- 特征提取段 (~80行)
- 滤波器组段 (~23行)
- 特征向量化段 (~32行)

---

## 跨文件依赖与公共关注点

### 文件间引用情况

```
aris_lm_v5.py    → 被 v11_agi_daemon.py 引用 (已废弃)
psilang_v2.py    → 被 agi_kernel.py, psi_cli.py, psilang_lm.py 等引用
aris_v12_5_engine.py → 被 aris_fusion_v15.py, aris_standalone.py 等引用
brain.py         → 被 cognitive_cycle.py, daemon.py, cli_integration.py 等引用
ao_core.py       → 被 ao_bridge.py, ao_mobile.py, ao_server_1024d.py 等引用
```

**重点**: 5个文件之间**没有直接的交叉引用**，各自被不同下游消费。这意味每个文件的拆分是独立的，无需担心拆分后的循环依赖问题。

### 共通模式
1. 所有文件都有 `if __name__ == '__main__'` 自测块 → 拆出到 `__main__.py`
2. 所有文件都用 `logger = logging.getLogger(...)` → 保持一致
3. 所有文件都用 `try/except` 做懒加载 → 对 braim.py 的 `__init__` 影响最大

### 推荐优先级

| 优先级 | 文件 | 原因 |
|--------|------|------|
| P0 | **brain.py** | 核心大脑，__init__ 253行硬编码18+模块，最影响可维护性 |
| P1 | **psilang_v2.py** | 31个类1个文件，Parser 440行 + VM 385行，逻辑层级分明 |
| P2 | **aris_v12_5_engine.py** | MarkovChainV12 495行占42%，功能分组清晰 |
| P3 | **ao_core.py** | 组件边界最清晰，拆分最简单，可快速完成 |
| P4 | **aris_lm_v5.py** | 已废弃，建议仅做标记 deprecation 处理 |

### 拆分原则

1. **保持公开 API 向后兼容**: 拆分后的 `__init__.py` 应导出与原文件完全相同的内容，使 `from old_file import X` 无缝迁移
2. **文件内循环引用禁止**: 拆分后模块间只能单向引用
3. **只拆不重构**: 不建议在拆分同时修改代码逻辑，分两步走
4. **性能影响最小化**: 拆分为包后引入额外的 `__init__.py` 查找开销，但 Python 会缓存已导入模块，实际影响可忽略
