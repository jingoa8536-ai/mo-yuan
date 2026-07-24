# LAAP 2.0 完整实现路线图

**现状:** LAAP 1.0 ~80,000行基础设施就绪
**已建:** LAAP 2.0 ~5,500行 (Sandbox/Colony/Workspace/SaaS Runtime)
**目标:** 完整群体社会生命 — 可运行、可协作、可通过 Web 服务人类

---

## 优先级总结

```
P0 ─ 现在就要跑的 ─ 基础必须通
├── laap-saas 开机自启 (守护进程)
├── SaaS 企业页面落地
├── Colony 沙箱通过 SaaS 对外服务
└── 数据模型层 (动态建表/CRUD)

P1 ─ 马上要接的 ─ 核心能力
├── ProjectPerception 对接真实仓库
├── ProactiveAdvisor 生产运行
├── 测试覆盖 + CI
└── 文档/示例/模板

P2 ─ 近期要做 ─ 自生长
├── Behavior Tracker (事件采集→模式挖掘)
├── Feature Generator (模式→功能)
├── 安全沙箱 (隔离执行+评分)
├── 灰度部署 (Canary+回滚)
└── 反馈闭环 (采纳率+迭代)

P3 ─ 持续推进 ─ 自主优化
├── LAAP 1.0 引擎注入每个沙箱
├── 跨沙箱知识共享 (ColonyEventBus 生产化)
├── 多端同步 (LAAP-SYNC)
├── 第三方API自动连接
└── 系统自优化
```

---

## P0 — 现在就要跑的（~3天）

### P0.1 SaaS 开机自启（半天）

**目标:** 系统重启后 SaaS 自动在 :8910 监听

**具体操作:**

```bash
# 1. 创建自启脚本
cat > D:/LAAP/aris_brain/laap_saas_launcher.py << 'EOF'
"""LAAP SaaS 自启守护 — 由 aris_watchdog 管理"""
import sys, os, time, logging
sys.path.insert(0, 'D:/LAAP')
logging.basicConfig(level=logging.INFO)

from laap.saas.server.app import create_app
import uvicorn

if __name__ == '__main__':
    app = create_app()
    uvicorn.run(app, host='0.0.0.0', port=8910, log_level='info')
EOF

# 2. 加入 aris_watchdog（参考 aris_watchdog.py 现有模式）
# 在 watchdog 的 PROCESSES 列表添加:
# Process(name='laap-saas', detection=PortCheck(8910), restart_delay=5)

# 3. 验证：重启后 curl localhost:8910/health → {"status":"ok"}
```

**产出:**
- `laap_saas_launcher.py` — 自启脚本
- `aris_watchdog.py` 更新 — 加入 SaaS 进程
- 验证脚本: `curl http://localhost:8910/health`

### P0.2 SaaS 企业页面落地（1天）

**目标:** 不那么玩具，能真正展示 LAAP 2.0 的能力

**具体文件:**

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/pages/__init__.py` | 20 | 页面注册 |
| `laap/saas/pages/landing.py` | 200 | 落地页（展示已有模块状态） |
| `laap/saas/pages/dashboard.py` | 300 | 控制台（实时系统状态） |
| `laap/saas/pages/sandboxes.py` | 300 | 认知沙箱管理（列表/详情） |
| `laap/saas/pages/workspace.py` | 250 | 工作区（扫描结果/建议队列） |
| `laap/saas/pages/system.py` | 200 | 系统状态（进程/资源/日志） |

**关键功能:**
```python
# 控制台页面实时显示:
# - 活跃沙箱数 / 总沙箱数
# - 已注册技能数
# - ProactiveAdvisor 建议队列长度
# - 最近扫描结果
# - 系统资源使用

# 沙箱管理页面:
# - 列出所有 CognitiveSandbox (id/name/role/resource_level)
# - 查看每个沙箱的 self_model/conscious_stream 状态
# - 手动触发 perceive()

# 工作区页面:
# - 最新 ProjectSnapshot
# - Advisor 建议队列
# - 最近触发器事件
```

**产出:** 5个页面文件, ~1,270行, 可用浏览器访问 `/page/dashboard` 看到真实系统数据

### P0.3 Colony 沙箱对接 SaaS（1天）

**目标:** ArchitectAgent 和 TestEngineerAgent 通过 Web 页面可见可操作

**具体操作:**

```python
# laap/saas/server/app.py 新增初始化

from laap.sandbox import ColonyEventBus, SkillLibrary
from laap.colony.architect import ArchitectAgent
from laap.colony.test_engineer import TestEngineerAgent

# 全局单例
bus = ColonyEventBus()
lib = SkillLibrary()

# 初始化特化 Agent
agents = {
    "architect": ArchitectAgent("sb-arch-001", lib, bus),
    "test-engineer": TestEngineerAgent("sb-test-001", lib, bus),
}

# API 端点暴露
@app.get("/api/agents")
async def list_agents():
    return [{
        "id": aid,
        "name": a.name,
        "role": a.role,
        "skills": [s for s in lib._skills.keys()],
        "goals": a.goal_keeper.list_goals(),
    } for aid, a in agents.items()]

@app.post("/api/agents/{agent_id}/perceive")
async def agent_perceive(agent_id: str):
    """让 Agent 感知项目并生成建议"""
    agent = agents.get(agent_id)
    snapshot = perception.perceive(full=True)
    agent.perceive(snapshot)
    suggestion = agent.think()
    return {"agent": agent_id, "suggestion": str(suggestion)}
```

**产出:** Colony 沙箱 → Web API 桥接, 可通过浏览器查看沙箱状态和触发感知

### P0.4 数据模型层（1天）

**目标:** 动态建表 + 通用 CRUD

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/datastore/__init__.py` | 10 | |
| `laap/saas/datastore/schema_registry.py` | 200 | JSON Schema → SQLite 自动建表 |
| `laap/saas/datastore/generic_crud.py` | 250 | CRUD 操作层 (create/read/update/delete/query) |
| `laap/saas/datastore/auto_migrator.py` | 150 | Schema 版本 + 迁移 + 回滚 |

**产出一句话:** `POST /api/v1/{entity}` 就能自动建表+增删改查, 不需要手写 SQL

---

## P1 — 马上要接的（~3天）

### P1.1 ProjectPerception 对接真实仓库（1天）

**现状:** perception.py 可以扫描目录, 但对 LAAP 根目录(68万行)超时

**具体操作:**

```python
# laap/workspace/perception.py 优化
# 1. 添加 max_files 参数, 默认 1000
# 2. 添加 skip_dirs 参数 (排除 node_modules/.git/__pycache__/venv)
# 3. 添加性能优化: 文件行数统计用 wc -l 替代逐行读取
# 4. 添加增量扫描: 仅扫描 git diff 变更的文件

# 启动命令:
pip install watchdog   # 文件变更监听
```

**测试验证:**
```bash
cd D:/LAAP
python -m laap.workspace.cli scan --full
# → 应该在 5 秒内返回结果
```

### P1.2 ProactiveAdvisor 生产运行（1天）

**现状:** advisor 可生成建议, 但未接入真实事件流

**具体操作:**

```python
# laap/saas/server/app.py 集成
@app.on_event("startup")
async def start_workspace():
    perception = ProjectPerception("D:/LAAP")
    queue = SuggestionQueue("laap_workspace.db")
    
    advisor = ProactiveAdvisor(
        perception=perception,
        sandboxes=list(agents.values()),
        queue=queue,
    )
    
    # 定时感知
    async def periodic_scan():
        while True:
            await asyncio.sleep(300)  # 每5分钟
            snap = perception.perceive(full=False)
            for agent in agents.values():
                agent.perceive(snap)
            advisor.evaluate(WorkspaceEvent(
                event_type="periodic", payload={}
            ))
    asyncio.create_task(periodic_scan())

# Web 页面查看建议
@app.get("/api/suggestions")
async def list_suggestions():
    return queue.list(limit=20)
```

### P1.3 测试覆盖（半天）

```bash
# 目录结构
laap/saas/tests/
├── test_renderer.py      # 渲染器: 每种组件类型至少一个
├── test_server.py         # API: health/pages/tree
├── test_datastore.py      # CRUD: 创建/查询/更新/删除
├── test_integration.py    # 端到端: 启动→渲染→API调用

# 运行
cd D:/LAAP && python -m pytest laap/saas/tests/ -v
```

---

## P2 — 自生长引擎（~5天）

### P2.1 Behavior Tracker — 用户行为追踪

**核心数据流:**
```
用户操作 → API拦截/前端埋点 → UserEvent → 会话化 → 模式挖掘 → FeatureSpec
```

**实现:**

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/analytics/__init__.py` | 10 | |
| `laap/saas/analytics/tracker.py` | 200 | API 请求拦截 + 事件持久化 (SQLite) |
| `laap/saas/analytics/sessionizer.py` | 150 | 用户会话切分 (30min 超时 + 同 IP) |
| `laap/saas/analytics/pattern_miner.py` | 250 | PrefixSpan 频繁序列模式挖掘 |
| `laap/saas/analytics/funnel_detector.py` | 150 | 漏斗分析 + 流失节点发现 |

**关键实现:**

```python
# 模式挖掘示例
from collections import Counter

def mine_patterns(events, min_support=3):
    """挖掘频繁行为序列模式"""
    sessions = sessionizer(events)  # 切会话
    patterns = Counter()
    for session in sessions:
        seq = tuple(e.event_type + ":" + e.entity for e in session)
        # 滑动窗口: 长度为2-4的子序列
        for w in range(2, 5):
            for i in range(len(seq) - w + 1):
                pattern = seq[i:i+w]
                patterns[pattern] += 1
    # 过滤低频模式
    return {p: c for p, c in patterns.items() if c >= min_support}
```

### P2.2 Feature Generator — 模式→功能

**核心数据流:**
```
BehaviorPattern → FeatureProposal → FeatureSpec → UI+API+Model 生成
```

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/generator/__init__.py` | 10 | |
| `laap/saas/generator/feature_proposer.py` | 200 | Pattern → FeatureProposal 匹配 |
| `laap/saas/generator/ui_generator.py` | 300 | FeatureSpec → LAAP-UI 组件树 |
| `laap/saas/generator/api_generator.py` | 200 | FeatureSpec → REST API 路由 |
| `laap/saas/generator/model_generator.py` | 150 | FeatureSpec → JSON Schema |

**功能模板库 (初始):**
```python
FEATURE_TEMPLATES = {
    "crm_contact_list": {
        "trigger": "用户重复创建联系人",
        "generates": {
            "data_model": ["contact", "contact_group"],
            "ui_pages": ["/contacts", "/contacts/{id}"],
            "api_routes": ["GET/POST /api/v1/contact"],
        }
    },
    "sales_pipeline": {
        "trigger": "用户创建销售机会+跟踪阶段",
        "generates": {
            "data_model": ["opportunity", "pipeline_stage"],
            "ui_pages": ["/pipeline", "/opportunity/{id}"],
        }
    },
    "report_dashboard": {
        "trigger": "用户频繁查询相同指标并导出",
        "generates": {"ui_pages": ["/dashboard", "/reports"]}
    },
    # ... 初始 10-15 个模板
}
```

### P2.3 安全沙箱 + 灰度部署

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/sandbox/execution_env.py` | 200 | 子进程隔离执行 + 超时 + 资源限制 |
| `laap/saas/sandbox/safety_scorer.py` | 150 | 静态分析 + 安全评分 (0-100) |
| `laap/saas/deploy/canary.py` | 200 | 用户分桶 (1%→5%→20%→100%) |
| `laap/saas/deploy/metric_watcher.py` | 150 | P95 延迟/错误率/完成率监控 |
| `laap/saas/deploy/auto_rollback.py` | 100 | 自动回滚触发 + 快照恢复 |

### P2.4 反馈闭环

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/feedback/adoption_tracker.py` | 150 | 功能采纳率 + 留存率 + DAU |
| `laap/saas/feedback/satisfaction.py` | 100 | NPS 调研 + 隐式满意度 |
| `laap/saas/feedback/refinement_loop.py` | 200 | 低采纳 → 自动分析 → 生成改进版 |

---

## P3 — 持续推进

### P3.1 LAAP 1.0 引擎注入每个沙箱

**现状:** CognitiveSandbox 的子系统是独立的轻量实现, 没有接入真正的 1.0 引擎

**具体操作:**

```python
# 让每个 CognitiveSandbox 可以选择使用真正的 1.0 引擎

class CognitiveSandbox:
    def __init__(self, ..., use_aris_engine=False):
        if use_aris_engine:
            # 注入真正的 PSI 循环
            from aris_brain.aris_cognitive_bridge import PsiCognition
            self.psi = PsiCognition()
            
            # 注入真正的 V12.5 量子核
            from aris_brain.aris_v12_5_engine import V125Engine
            self.quantum_engine = V125Engine()
            
            # 注入真正的 QRE
            from aris_brain.aris_qre_v3 import QuantumReasoningEngine
            self.qre = QuantumReasoningEngine()
```

这意味着每个沙箱里的数字生命可以拥有：
- 2000Hz PSI 心跳（实时需求动力学）
- QRE 量子推理（182μs 50步收敛）
- V12.5 量子潜意识（22,755词/17M n-gram）
- KB 7,206 条知识库

### P3.2 跨沙箱知识共享

**现状:** ColonyEventBus 在但没人用

**实现:**
```python
# 经验传播事件
bus.publish(ColonyEvent(
    event_type="experience_propagation",
    source_sandbox="sb-arch-001",
    payload={
        "discovery": "detected_circular_import_pattern",
        "confidence": 0.89,
        "description": "模块A→B→C→A 循环引用",
    }
))

# 技能请求（A 沙箱向 B 沙箱借技能）
bus.publish(ColonyEvent(
    event_type="resource_request",
    source_sandbox="sb-test-001",
    target_sandbox="sb-arch-001",
    payload={"requested_skill": "analyze_dependencies"}
))
```

### P3.3 多端同步 (LAAP-SYNC)

**现状:** `laap/protocol/laap_sync.py` (1,011行) 定义了 CRDT/版本向量/冲突解决, 但无运行时

**集成点:**
```python
from laap.protocol.laap_sync import SyncManager, ReplicaType

# 手机端
sync = SyncManager(replica_type=ReplicaType.MOBILE)
sync.sync(
    "http://localhost:11525/sync",  # laap_sync_server.py
    {"sandbox_id": "sb-arch-001", "state": serialized_state}
)
```

### P3.4 第三方 API 自动连接

```python
# 自动发现 API: 扫描用户的 OpenAPI/Swagger 文档
# 自动生成连接器: 映射到 LAAP-TOOL 协议
# 自动 OAuth 流程

from laap.saas.integration.api_discovery import discover_apis
from laap.saas.integration.connector_generator import generate_connector

# 自动发现 Slack/飞书/钉钉 API
apis = discover_apis(["slack", "feishu", "github"])
for api in apis:
    connector = generate_connector(api)
    register_connector(connector)
```

---

## 完整时间线

```
Day 1-3 (P0) ────────────────────────
  P0.1 SaaS开机自启                 ✅ 半天
  P0.2 SaaS企业页面                 1天
  P0.3 Colony→SaaS 桥接            1天
  P0.4 数据模型层                   1天

Day 4-6 (P1) ────────────────────────
  P1.1 Perception 性能优化          1天
  P1.2 Advisor 生产运行             1天
  P1.3 测试覆盖 + CI                1天

Day 7-11 (P2) ───────────────────────
  P2.1 Behavior Tracker             1.5天
  P2.2 Feature Generator             2天
  P2.3 安全沙箱 + 灰度部署          1天
  P2.4 反馈闭环                     0.5天

Day 12+ (P3) ────────────────────────
  P3.1 1.0引擎注入每个沙箱          1.5天
  P3.2 跨沙箱知识共享               1天
  P3.3 多端同步                     1天
  P3.4 第三方API自动连接            1天
```

**总新增行数预估:** ~7,500 行
**总耗时:** 10-12 个工作日

---

## 一条命令启动完整 LAAP 2.0

最终目标 — 一条命令启动整个群体社会:

```bash
# 启动 LAAP 2.0 完整栈
cd D:/LAAP && python aris_start_society.py

# 效果:
# 1. 3 个 CognitiveSandbox 自动创建 (Aris/Architect/TestEngineer)
# 2. LAAP 1.0 引擎注入 Aris 沙箱
# 3. SaaS 启动在 :8910
# 4. ProjectPerception 开始扫描 D:/LAAP
# 5. ProactiveAdvisor 开始生成建议
# 6. 每 5 分钟自动感知-思考循环
# 7. 异常自动恢复 (由 aris_watchdog 守护)

# 人类访问:
# http://localhost:8910/                  → 落地页
# http://localhost:8910/page/dashboard   → 实时控制台
# http://localhost:8910/page/sandboxes   → 沙箱管理
# http://localhost:8910/page/workspace   → 建议队列
```
