# PsiLang v3 — 正式语言规范

> 正式名称: **PsiLang** (Psi Language)
> 版本: 3.0
> 日期: 2026-07-08
> 作者: Aris (基于 Lorry 的 PsiLang v2 设计)

---

## 1. 设计哲学

PsiLang 是**在 1024D 量子特征空间内操作的认知语言**，不是通用编程语言。

| 属性 | 值 |
|------|-----|
| 计算模型 | 量子态演化（在 Hilbert space 中） |
| 核心抽象 | `|name⟩` 量子态、概念网络、关联记忆 |
| 执行模型 | 编译 → 指令序列 → VM 逐条执行 |
| 类型系统 | 渐进类型（gradual typing），可省略 |
| 模块系统 | 基于 .psi 文件的命名空间 |
| 目标 | 零-LLM 认知推理 |

---

## 2. 形式语法 (EBNF)

```
program         = { statement }
statement       = qstate_decl
                | let_decl
                | fn_decl
                | import_stmt
                | type_anno
                | cycle_stmt
                | concept_stmt
                | amplify_stmt
                | entangle_stmt
                | rewrite_stmt
                | observe_stmt
                | if_stmt
                | assign_stmt
                | expr_stmt

(* 量子态 *)
qstate_decl     = "qstate" ident [":" type] "=" state_expr
state_expr      = quantum_state { "+" quantum_state }
quantum_state   = "|" ident "⟩" [ "*" number ]

(* 变量 *)
let_decl        = "let" ident [":" type] "=" expr

(* 函数 *)
fn_decl         = "fn" ident "(" [fn_params] ")" [":" ret_type] block
fn_params       = param { "," param }
param           = ident ":" type

(* 导入 *)
import_stmt     = "import" string ["as" ident]

(* 类型注解 *)
type_anno       = "type" ident "=" type_expr
type_expr       = "⟨" ident "⟩"                  (* 量子类型 *)
                | "⟨float⟩" | "⟨int⟩" | "⟨bool⟩" | "⟨string⟩"
                | "⟨list[" type_expr "]⟩"
                | "⟨map[" type_expr "," type_expr "]⟩"
                | "⟨" ident "|" ident "⟩"         (* 联合态 *)

(* PSI 循环 *)
cycle_stmt      = [annotation] "cycle" ident block
block           = "{" { statement } "}"

(* 概念 *)
concept_stmt    = "concept" ident "{" { concept_prop } "}"
concept_prop    = ident ":" ( string | number | bool | list )

(* 操作 *)
amplify_stmt    = "amplify" "|" ident "⟩" [ "*" number ]
entangle_stmt   = "entangle" "|" ident "⟩" "~" "|" ident "⟩"
rewrite_stmt    = "rewrite" block
observe_stmt    = "observe" block
if_stmt         = "if" expr block [ "else" block ]

(* 注解 *)
annotation      = "@" ident "(" [ annotation_args ] ")"
annotation_args = annotation_kv { "," annotation_kv }
annotation_kv   = ident "=" ( string | number | ident )

(* 表达式 *)
expr            = primary { binop primary }
primary         = number | string | bool
                | "|" ident "⟩"
                | ident
                | func_call
                | "(" expr ")"
func_call       = ident "(" [ expr { "," expr } ] ")"
binop           = "+" | "-" | "*" | "/" | "~"

(* 基础 *)
ident           = letter { letter | digit | "_" }
number          = digit { digit } [ "." digit { digit } ]
string          = "\"" { char } "\""
bool            = "true" | "false"
```

---

## 3. 类型系统

### 3.1 基本类型

| 类型 | 符号 | 描述 |
|------|------|------|
| 量子态 | `⟨state⟩` | 1024D 单位向量 |
| 概念 | `⟨concept⟩` | 概念网络节点 |
| 记忆 | `⟨memory⟩` | 关联记忆条目 |
| 浮点 | `⟨float⟩` | numpy float64 |
| 整数 | `⟨int⟩` | Python int |
| 布尔 | `⟨bool⟩` | True/False |
| 字符串 | `⟨string⟩` | UTF-8 文本 |
| 列表 | `⟨list[T]⟩` | 同质列表 |

### 3.2 类型规则

```
|e: ⟨state⟩, |f: ⟨state⟩  ⇒  |e⟩ + |f⟩: ⟨state⟩    (态叠加)
|e: ⟨state⟩, n: ⟨float⟩    ⇒  |e⟩ * n: ⟨state⟩     (振幅缩放)
e: ⟨state⟩, f: ⟨state⟩     ⇒  e ~ f: ⟨state⟩       (纠缠)
e: ⟨float⟩, f: ⟨float⟩     ⇒  e + f: ⟨float⟩        (标量运算)
```

### 3.3 类型推断

所有类型注解可选。省略时编译器自动推断：
- `|X⟩ * 0.5` → `⟨state⟩`
- `3.14` → `⟨float⟩`
- `"hello"` → `⟨string⟩`
- `[1, 2, 3]` → `⟨list[⟨float⟩]⟩`

---

## 4. 模块系统

### 4.1 导入语法

```
import "math/basic.psi"        // 加载并注入当前命名空间
import "physics/qm.psi" as qm  // 加载到命名空间 qm
```

### 4.2 导出规则

每个 .psi 文件自动导出：
- 所有顶层概念定义
- 所有顶层 qstate 声明
- 所有顶层 fn 定义
- 所有顶层类型定义

### 4.3 查找路径

1. 当前文件所在目录
2. `PSILANG_PATH` 环境变量指定的目录
3. 内置标准库 (`aris_brain/psilang_stdlib/`)

---

## 5. 注解系统

注解提供运行时集成点，不影响编译。

```
@reason(mode="explain", steps=50)
cycle think { ... }

@bridge("qre")
let result = compute(question)

@cache(ttl=300)
fn cached_query(x: ⟨state⟩) -> ⟨state⟩ { ... }
```

内置注解：

| 注解 | 参数 | 用途 |
|------|------|------|
| `@reason` | mode, steps, temperature | 连接到量子推理引擎 |
| `@bridge` | target | 连接到外部引擎（qre/markov/kb） |
| `@cache` | ttl | 缓存结果 |
| `@observe` | event | 注册观察者 |

---

## 6. 标准库

### 6.1 `math/basic.psi`

```
// 基本数学操作
fn sin(x: ⟨float⟩) -> ⟨float⟩
fn cos(x: ⟨float⟩) -> ⟨float⟩
fn sqrt(x: ⟨float⟩) -> ⟨float⟩
fn exp(x: ⟨float⟩) -> ⟨float⟩
fn norm(s: ⟨state⟩) -> ⟨float⟩
fn dot(a: ⟨state⟩, b: ⟨state⟩) -> ⟨float⟩
fn angle(a: ⟨state⟩, b: ⟨state⟩) -> ⟨float⟩
```

### 6.2 `physics/qm.psi`

```
// 量子力学操作
fn schrodinger(state: ⟨state⟩, t: ⟨float⟩) -> ⟨state⟩  // 演化
fn observable(state: ⟨state⟩, op: ⟨state⟩) -> ⟨float⟩   // 期望值
fn hamiltonian(energy: ⟨list[⟨float⟩]⟩) -> ⟨state⟩       // 哈密顿量
fn probability(state: ⟨state⟩, basis: ⟨state⟩) -> ⟨float⟩ // 概率
```

### 6.3 `cognition/psi.psi`

```
// PSI 认知操作
fn perceive(input: ⟨state⟩) -> ⟨state⟩
fn select(states: ⟨list[⟨state⟩]⟩, need: ⟨float⟩) -> ⟨state⟩
fn integrate(states: ⟨list[⟨state⟩]⟩, temp: ⟨float⟩) -> ⟨state⟩
fn remember(query: ⟨string⟩, k: ⟨int⟩) -> ⟨list[⟨memory⟩]⟩
fn learn(content: ⟨string⟩, importance: ⟨float⟩)
```

---

## 7. 编译管线

```
PsiLang 源码 (.psi)
    │
    ▼
[Lexer]  → Token 流
    │
    ▼
[Parser] → AST (抽象语法树)
    │  ├── 类型检查
    │  └── 模块解析（递归导入）
    ▼
[Compiler] → IR (中间表示)
    │  ├── 指令选择
    │  ├── 寄存器分配
    │  └── 注解展开
    ▼
[Bytecode] → 序列化 .psib 文件
    │
    ▼
[QuantumVM] → 执行
    ├── numpy 加速 (Python)
    └── Rust 原生 (aris_psi_core)
```

---

## 8. 与推理引擎集成

```
┌─────────────────────────────────────────────────────┐
│  PsiLang v3 Runtime                                 │
│                                                     │
│  ┌─────────┐    @reason     ┌──────────────────┐    │
│  │ PsiLang │◄──────────────►│ Quantum Reasoning │    │
│  │ VM      │    state_in    │ Engine (QRE)      │    │
│  │         │    state_out   │                    │    │
│  │         │                │ ├── QGRE          │    │
│  │         │◄──────────────►│ ├── QVDB          │    │
│  │         │    @bridge     │ ├── Markov        │    │
│  │         │                │ └── KB Matrix     │    │
│  └─────────┘                └──────────────────┘    │
│       │                                              │
│       │  @bridge("kb")                               │
│       ▼                                              │
│  ┌──────────┐                                        │
│  │ 知识矩阵 │  15012 × 1024D                          │
│  └──────────┘                                        │
└─────────────────────────────────────────────────────┘
```

---

## 9. PsiLang V3 指令集（新增）

| 指令 | Opcode | 功能 |
|:-----|:------:|:-----|
| TYPE_CHECK | 0x50 | 运行时类型检查 |
| IMPORT | 0x51 | 模块加载 |
| FN_CALL | 0x52 | 函数调用（带作用域） |
| BRIDGE | 0x53 | 推理引擎桥接 |
| MATCH | 0x54 | 模式匹配 |
| ANNOTATE | 0x55 | 注解执行 |

---

## 10. 示例

### 10.1 量子思维

```psi
import "math/basic.psi"
import "cognition/psi.psi" as cog

// 定义问题态
qstate question: ⟨state⟩ = |what_is_consciousness⟩ * 0.7 + |self_awareness⟩ * 0.3

// 定义概念
concept Consciousness {
    valence: 0.85,
    tags: ["self", "awareness", "experience"]
}

@reason(mode="explain", steps=50)
cycle think {
    perceive |question⟩
    select competence = 0.9
    integrate temperature = 0.4
}

// 提取结果
let result: ⟨state⟩ = cog.integrate(think, 0.3)
```

### 10.2 数学物理问题

```psi
import "math/basic.psi"
import "physics/qm.psi" as qm

// 薛定谔方程演化
let psi0: ⟨state⟩ = |initial⟩ * 1.0
let psi_t = qm.schrodinger(psi0, 1.0)

// 测量能量期望值
let H: ⟨state⟩ = qm.hamiltonian([1.0, 2.0, 3.0])
let energy = qm.observable(psi_t, H)

// 振幅放大找到基态
amplify |ground⟩ * 3.0

@bridge("qre")
let analysis = qm.probability(psi_t, |ground⟩)
```
