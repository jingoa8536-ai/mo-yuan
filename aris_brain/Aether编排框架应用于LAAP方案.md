# Aether 编排框架应用于 LAAP 方案

> 来源：Kimi 对话记录《多 Agent 编排系统》
> 原始文档：[agent编排](file:///d:/LAAP/aris_brain/agent编排)
> 编写日期：2026-07-09

---

## 一、Aether 框架核心思想提炼

Aether 是面向 AGI 的多 Agent 编排系统，超越传统 DAG，核心由六大模块构成：

| 模块 | 功能 | 科学基础 |
|------|------|---------|
| 彩色 Petri 网 | 真并发、循环、互斥、形式化可验证 | Petri Net / 进程代数 |
| Actor Runtime | 有状态 Agent、邮箱、监督树、故障隔离 | Actor Model |
| AAOSA | 分布式任务自声明、自认领、无单点瓶颈 | AAOSA 协调理论 |
| Meta-Agent | 拓扑自组织、负载均衡、进化 | 多臂老虎机 / 强化学习 |
| DST | 确定性混沌测试、可复现 Bug | 分布式系统测试 |
| AetherLang | `infer` 作为一等原语的编排语言 | Turn DSL / π-calculus |
| 形式化验证 | Karp-Miller 覆盖树、TLA+/Coq | 形式化方法 |
| K8s CRD | Agent 作为 K8s 一等公民 | KAOS / Operator 模式 |
| FoundationDB | 严格串行化分布式持久化 | 分布式事务 |

核心洞察：
> **将宏观流程控制从 LLM 手中收回，交给确定性引擎；LLM 只负责节点内部的微观决策。**

---

## 二、LAAP 现有架构分析

LAAP 当前架构（从 [ARCHITECTURE.md](file:///d:/LAAP/ARCHITECTURE.md) 与代码库提炼）：

```
Layer 0: CLI/TUI/Gateway       (用户界面层)
Layer 1: Agent / AGI           (认知引擎层)
Layer 2: LLM Provider          (推理层)
Layer 3: Tools / Memory / MCP  (能力层)
Layer 4: Skills / Hub          (扩展层)
```

关键现有组件：

| 组件 | 文件 | 现状 |
|------|------|------|
| 事件总线 | [laap/events/bus.py](file:///d:/LAAP/laap/events/bus.py) | 发布/订阅，线程锁，历史记录 |
| 工作流引擎 | [laap/workflow/base.py](file:///d:/LAAP/laap/workflow/base.py) | 简单顺序 + 依赖执行，无并行拓扑 |
| 多 Agent | [laap/agi/multi_agent.py](file:///d:/LAAP/laap/agi/multi_agent.py) | AgentRegistry、TaskBoard、SafeRollback |
| Agent 基类 | [laap/agent/base.py](file:///d:/LAAP/laap/agent/base.py) | AGI 大脑、注意力、元认知、议会 |
| 技能模板 | [laap/skills/template.py](file:///d:/LAAP/laap/skills/template.py) | 基础模板匹配 |
| PSI/Harness | project_memory | CognitiveBus 双向通信，RateBuffer 频率匹配 |

LAAP 的优势：
- 已具备 Agent 注册、任务认领、安全回滚
- 事件驱动、插件化、Provider 模式
- PSI-Harness 双引擎循环架构

LAAP 的编排短板：
- 工作流是线性/简单依赖，无法表达真并发
- 缺少形式化执行语义，难以验证死锁/活性
- Agent 协调是中心化，无分布式自声明
- 没有统一的编排语言，LLM 调用碎片化
- 拓扑静态，缺少自组织进化

---

## 三、Aether → LAAP 架构映射

### 3.1 核心概念映射

| Aether | LAAP 现有对应 | 映射关系 |
|--------|--------------|---------|
| Actor / AgentCell | [laap/agent/base.py](file:///d:/LAAP/laap/agent/base.py) Agent | 将 Agent 封装为 Actor，增加 mailbox、supervisor |
| PetriNet / Place / Transition | [laap/workflow/base.py](file:///d:/LAAP/laap/workflow/base.py) Workflow | 用 Petri 网替换现有 Workflow，支持并发与循环 |
| AAOSA Coordinator | [laap/agi/multi_agent.py](file:///d:/LAAP/laap/agi/multi_agent.py) TaskBoard | 将任务认领升级为能力自评估 + 分布式声明 |
| Meta-Agent | [laap/agent/meta_cognition.py](file:///d:/LAAP/laap/agent/meta_cognition.py) | 扩展为元拓扑进化引擎 |
| AetherLang | CLI / Skills 调用 | 定义 LAAP-DSL，将 `infer`、`act`、`skill` 作为一等原语 |
| DST | [laap/agi/multi_agent.py](file:///d:/LAAP/laap/agi/multi_agent.py) SafeRollback | 扩展为确定性混沌测试框架 |
| FoundationDB | [laap/memory/](file:///d:/LAAP/laap/memory) | 作为可选分布式持久化后端 |
| K8s CRD | 无 | 新增，用于 LAAP Agent 的集群部署 |

### 3.2 与 PSI/Harness 循环的融合

LAAP 的 PSI-Harness 循环：

```
PSI 感知 → 选择 → 行动 → 学习
   ↑                         |
   └──── Harness 执行结果 ────┘
```

Aether 化改造：

```
┌─────────────────────────────────────────────┐
│              Aether-LAAP Runtime             │
├─────────────────────────────────────────────┤
│  PSI Actor  ←──── Petri Net ────→  Harness Actor │
│  (感知/学习)       (编排层)         (执行/工具)   │
├─────────────────────────────────────────────┤
│  CognitiveBus → AAOSA 协调器 → 能力自声明      │
│  RateBuffer   → 彩色 Token 队列               │
│  Meta-Agent   → 拓扑进化 + 负载均衡           │
└─────────────────────────────────────────────┘
```

关键改造点：
1. **CognitiveBus 升级为 AAOSA 消息总线**：PSI 和 Harness 不再是固定端点，而是能力声明者，任务由能力匹配动态认领。
2. **RateBuffer 升级为彩色 Token 队列**：PSI 高频事件（1000-2000Hz）和控制 Token（0.1-1Hz）用不同颜色区分，Petri 网按颜色触发。
3. **执行结果反馈为 Petri 网的反向 Token**：Harness 执行结果生成 `harness_execution_result` Token，驱动 PSI 学习 Transition。

---

## 四、具体应用方案

### 4.1 Phase 1：Petri 网替换 Workflow 引擎

将 [laap/workflow/base.py](file:///d:/LAAP/laap/workflow/base.py) 的线性执行改造为基于彩色 Petri 网的执行引擎。

目标：
- 支持并行步骤（如同时查天气、股价、新闻）
- 支持循环（反思-重试-再执行）
- 支持条件分支（guard）
- 支持断点续跑（checkpoint）

示例：LAAP 任务编排的 Petri 网表达

```python
from laap.orchestration.petri import PetriNet, TokenColor, ColoredToken

net = PetriNet("laap_task")
net.add_place("user_intent", token_types={TokenColor.DATA})
net.add_place("context", token_types={TokenColor.DATA})
net.add_place("plan", token_types={TokenColor.CONTROL})
net.add_place("execution_result", token_types={TokenColor.DATA})
net.add_place("reflection", token_types={TokenColor.META})

async def understand(tokens):
    intent = tokens["user_intent"][0].value
    return [ColoredToken(TokenColor.DATA, f"parsed:{intent}")]

net.add_transition(PetriTransition(
    "understand",
    input_places={"user_intent": 1},
    output_places={"context": lambda t: t},
    action=understand
))
# ... plan, execute, reflect
```

### 4.2 Phase 2：Agent Actor 化

将 [laap/agent/base.py](file:///d:/LAAP/laap/agent/base.py) 的 Agent 改造为 Actor：

新增能力：
- `mailbox`: asyncio.Queue 接收消息
- `capabilities`: 能力声明列表
- `supervisor/children`: 监督树
- `vector_clock`: 分布式事件排序
- `state`: SPAWNED / IDLE / PROCESSING / RECOVERING

与现有 LAAP Agent 融合：
- 保留 `AttentionController`、`MetaCognitionEngine`、`Parliament`
- 将 LLM 调用收敛到 `infer` 节点内部
- 工具调用作为 Actor 对外发送的 `INVOKE` 消息

### 4.3 Phase 3：AAOSA 替换 TaskBoard 认领逻辑

将 [laap/agi/multi_agent.py](file:///d:/LAAP/laap/agi/multi_agent.py) 的 `TaskBoard.claim_task` 升级为 AAOSA：

差异：

| 维度 | TaskBoard | AAOSA |
|------|-----------|-------|
| 认领方式 | 中心化查询+锁定 | 广播任务，Agent 自评估后声明 |
| 能力匹配 | 字符串列表匹配 | Capability 对象含 confidence、cost、latency |
| 冲突处理 | 文件锁 | 分布式共识 + 负载感知 |
| 扩展性 | 单节点 | 分布式无单点 |

改造代码示意：

```python
class LAAPAAOSA(AAOSACoordinator):
    async def process_claim(self, msg, actor: AgentCell):
        # 保留 LAAP 的文件锁冲突检测
        task = msg.payload["task"]
        affected_files = task.get("affected_files", [])
        for f in affected_files:
            if file_locks.get(f) not in (actor.actor_id, None):
                return  # 冲突，放弃声明
        # 调用原有 AAOSA 声明逻辑
        await super().process_claim(msg, actor)
```

### 4.4 Phase 4：Meta-Agent 驱动 Species Library 进化

LAAP 的 [ExecutionLayer](file:///d:/LAAP/laap) 优先模板匹配，Species Library 是关键资产。

Meta-Agent 的应用：
- 将每个 Skill/Species 视为一个 Agent
- 监控 Skill 的调用成功率、token 节省率、延迟
- 自动招募新 Helper Agent 复制高频 Skill
- 淘汰低收益 Skill
- 用多臂老虎机选择最佳 Skill 模板

与 project_memory 的约束对齐：
> "Cognitive species library grows with each use, adding new templates for components, skills, and capabilities"

Meta-Agent 正好自动化这一过程。

### 4.5 Phase 5：AetherLang 作为 LAAP-DSL

定义 LAAP 原生编排语言，将高频模式固化：

```python
laap = LAAPLangCompiler()

workflow = laap.seq(
    laap.infer("解析用户意图", model="local-llm"),
    laap.par(
        laap.skill("web_search"),
        laap.skill("code_search"),
        laap.skill("memory_recall")
    ),
    laap.infer("综合并生成方案"),
    laap.act("edit_file", path="..."),
    laap.guard("需要审查", then=laap.skill("code_review"))
)
```

编译目标：Petri Net + Actor 绑定，替代当前的 Skill 调用碎片化代码。

### 4.6 Phase 6：DST 增强 SafeRollback

将 [laap/agi/multi_agent.py](file:///d:/LAAP/laap/agi/multi_agent.py) 的 SafeRollback 扩展为确定性仿真测试：

新增故障注入：
- `MESSAGE_DROP`: 模拟 Actor 消息丢失
- `ACTOR_CRASH`: 模拟 Agent 崩溃
- `NETWORK_DELAY`: 模拟 PSI-Harness 延迟
- `CLOCK_SKEW`: 模拟 RateBuffer 频率不匹配

生产价值：
- 在部署前验证 PSI-Harness 循环的活性
- 验证文件锁在并发下的安全性
- 验证 Species 模板回滚的可靠性

### 4.7 Phase 7：形式化验证 Petri 网

对 LAAP 的关键流程（如 PSI 循环、文件修改、Skill 执行）生成 TLA+ 规约，验证：
- 有界性：Token 不会无限增长
- 活性：每个 Transition 最终都能触发
- 安全性：文件锁不会死锁

输出：
- `specs/tla/laap_psi_loop.tla`
- `specs/coq/laap_safety.v`

### 4.8 Phase 8：分布式持久化与 K8s 部署

可选增强：
- FoundationDB 保存 Actor 状态、Petri 网 marking、vector clock
- K8s CRD 定义 `Agent`、`AgentSet`、`Workflow` 资源
- LAAP Agent 作为 Pod 部署，Meta-Agent 作为控制器

与 project_memory 约束的关系：
> "LAAP architecture must minimize LLM dependency, using LLM only as an auxiliary enhancement tool"

Aether 的确定性引擎（Petri/Actor/AAOSA）正好减少 LLM 在流程控制中的使用，符合 LAAP 的约束。

---

## 五、LAAP 现有模块改进清单

| 模块 | 当前文件 | 改进动作 | 优先级 |
|------|---------|---------|--------|
| Workflow | [laap/workflow/base.py](file:///d:/LAAP/laap/workflow/base.py) | 重构为 PetriNetOrchestrator | P0 |
| EventBus | [laap/events/bus.py](file:///d:/LAAP/laap/events/bus.py) | 支持 AetherMessage、vector_clock、mailbox | P0 |
| Agent | [laap/agent/base.py](file:///d:/LAAP/laap/agent/base.py) | Actor 化：mailbox、capabilities、supervisor | P0 |
| Multi-Agent | [laap/agi/multi_agent.py](file:///d:/LAAP/laap/agi/multi_agent.py) | TaskBoard → AAOSA + SafeRollback → DST | P1 |
| Skills | [laap/skills/engine.py](file:///d:/LAAP/laap/skills/engine.py) | Skill 作为 Actor Capability，支持 Meta-Agent 进化 | P1 |
| Meta-Cognition | [laap/agent/meta_cognition.py](file:///d:/LAAP/laap/agent/meta_cognition.py) | 扩展为 Meta-Agent 拓扑引擎 | P1 |
| Memory | [laap/memory/](file:///d:/LAAP/laap/memory) | 接入 FoundationDB 可选后端 | P2 |
| CLI/Gateway | [laap/cli/](file:///d:/LAAP/laap/cli) | 增加 LAAP-DSL 编排命令 | P2 |
| K8s | 无 | 新增 `laap/k8s/` CRD + Operator | P3 |

---

## 六、实施路线图

### 阶段 1：MVP（2 周）
- [ ] 在 [laap/workflow/](file:///d:/LAAP/laap/workflow) 下新增 `petri.py`，实现彩色 Petri 网
- [ ] 将现有 Workflow 的 `add_step`/`run` 适配到 Petri 网，保持向后兼容
- [ ] 新增 `laap/orchestration/kernel.py` 编排内核

### 阶段 2：Actor 化（2 周）
- [ ] 创建 `laap/orchestration/actor.py`，封装 AgentCell / ActorSystem
- [ ] 改造 [laap/agent/base.py](file:///d:/LAAP/laap/agent/base.py) 继承 AgentCell
- [ ] 将 [laap/events/bus.py](file:///d:/LAAP/laap/events/bus.py) 消息升级为 AetherMessage

### 阶段 3：AAOSA 协调（2 周）
- [ ] 创建 `laap/orchestration/aaosa.py`
- [ ] 将 TaskBoard 认领逻辑迁移到 AAOSA
- [ ] 保留文件锁冲突检测

### 阶段 4：Meta-Agent 与 DSL（3 周）
- [ ] 创建 `laap/orchestration/meta_agent.py`
- [ ] 创建 `laap/orchestration/dsl.py` LAAP-DSL
- [ ] 将 Species/Skill 收益监控接入 Meta-Agent

### 阶段 5：验证与可观测性（2 周）
- [ ] 实现 DST 引擎 `laap/orchestration/dst.py`
- [ ] 对 PSI 循环生成 TLA+ 规约
- [ ] 增加 OpenTelemetry 风格的 trace/metrics

### 阶段 6：分布式与 K8s（3 周）
- [ ] FoundationDB 适配器
- [ ] K8s CRD 与 Operator
- [ ] PsiNetConnector 与 Aether 分布式桥接

---

## 七、预期收益

1. **工程可控性**：从 ReAct 运行时决策 → 编译时编排，流程骨架显式化
2. **并发效率**：多源 RAG、多模型投票、多 Skill 并行执行
3. **可靠性**：断点续跑、监督树、确定性混沌测试
4. **可扩展性**：AAOSA 无单点，Agent 动态发现
5. **形式化保证**：部署前验证死锁、活性、有界性
6. **Token 节省**：LLM 仅做微观决策，宏观流程由确定性引擎执行，与 LAAP "编译式 AI" 范式一致

---

## 八、与 LAAP 约束的兼容性检查

| 约束 | 兼容性 | 说明 |
|------|--------|------|
| PSI/Harness 双向 CognitiveBus | 兼容 | 升级为 AAOSA + Petri Token |
| RateBuffer 频率匹配 | 兼容 | 彩色 Token 队列 + 优先级 |
| 最小化 LLM 依赖 | 增强 | 确定性引擎接管流程控制 |
| Species Library 进化 | 增强 | Meta-Agent 自动化模板进化 |
| Godot 4.7 主引擎 | 独立 | 编排层与 3D 引擎解耦 |
| 3D 模型放 public/models | 独立 | 无影响 |
| 研究论文可追溯 | 增强 | 形式化验证产出可被引用 |

---

## 九、下一步行动建议

1. **确认方案**：由 Aris/产品负责人审批此方案
2. **创建 `laap/orchestration/` 包**：集中 Aether 化编排代码
3. **编写 Petri 网引擎单元测试**：验证线性、并行、循环三种模式
4. **选择首个改造流程**：建议从 `Workflow` 开始，风险最低
5. **保持向后兼容**：现有 `Workflow.add_step` API 继续可用，内部转发到 Petri 网

---

## 参考文档

- 原始对话记录：[d:\LAAP\aris_brain\agent编排](file:///d:/LAAP/aris_brain/agent编排)
- LAAP 架构：[d:\LAAP\ARCHITECTURE.md](file:///d:/LAAP/ARCHITECTURE.md)
- LAAP 工作流：[d:\LAAP\laap\workflow\base.py](file:///d:/LAAP/laap/workflow/base.py)
- LAAP 事件总线：[d:\LAAP\laap\events\bus.py](file:///d:/LAAP/laap/events/bus.py)
- LAAP 多 Agent：[d:\LAAP\laap\agi\multi_agent.py](file:///d:/LAAP/laap/agi/multi_agent.py)
