# LAAP 2.0 L3 — 自演化 SaaS 工程化路径

**作者:** Aris + Lorry
**日期:** 2026-06-27
**状态:** 方案设计

> 基于 LAAP 2.0 大版本升级方案文档，细化第三层「自演化业务系统」
> 的工程化实现路径。已有 9.7 万行 LAAP 代码基础设施可复用。

---

## 一、架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    L3: 自演化 SaaS                            │
├──────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌────────────────┐  ┌───────────────┐  │
│  │  SaaS Runtime    │  │  自生长引擎     │  │  安全进化层    │  │
│  │  (Web Host)      │  │  (Generator)   │  │  (Safety)     │  │
│  ├─────────────────┤  ├────────────────┤  ├───────────────┤  │
│  │ LAAP-UI Renderer │  │ Feature Gen    │  │ Zone1 监控    │  │
│  │ REST API Layer   │  │ API Auto-Gen   │  │ Zone2 测试    │  │
│  │ Data Model Store │  │ Data Migrator  │  │ Zone3 灰度    │  │
│  │ Auth/Multi-tenant│  │ Behavior→Pattern│ │ Zone4 生产    │  │
│  └─────────────────┘  └────────────────┘  └───────────────┘  │
│                             ↕                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  反馈闭环: 用户行为→模式识别→特征生成→灰度部署→采纳度量→回溯  │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、Phase 1 — SaaS 运行时（Foundation）

**目标:** 让 LAAP 能力通过 Web 页面暴露，支持动态 UI 渲染和 REST API。

### P1.1 LAAP-UI Renderer（Web 渲染器）

**输入:** LAAP-UI 协议描述的组件树（`ComponentTree`）
**输出:** 可交互的 Web 页面（HTML + JS）

| 文件 | 行数预估 | 功能 |
|------|---------|------|
| `laap/saas/renderer/__init__.py` | 20 | 包导出 |
| `laap/saas/renderer/html_renderer.py` | 500 | LAAP-UI组件树→HTML DOM 渲染器, 递归遍历组件树, 映射ComponentType到HTML标签 |
| `laap/saas/renderer/event_bridge.py` | 200 | 前端事件绑定: click/submit/change → 后端callback, ws长连接 |
| `laap/saas/renderer/diff_patch.py` | 300 | LAAP-UI 差分更新协议 → 局部DOM更新, 替代全量re-render |
| `laap/saas/renderer/theme_resolver.py` | 200 | 主题解析: ThemeConfig → CSS变量, 运行时主题切换 |

**关键接口:**
```python
class HTMLRenderer:
    def render(self, tree: ComponentTree) -> str:
        """组件树 → HTML 字符串"""
    def patch(self, existing_id: str, patch: ComponentPatch) -> str:
        """差分更新 → 增量 DOM 操作 JS"""
```

**复用:** `laap/protocol/laap_ui.py` (1,219行) 中的 ComponentTree, ComponentType, LayoutType, StyleConfig, EventBinding

**已有组件类型(22种):** ROOT, CONTAINER, TEXT, IMAGE, BUTTON, INPUT, PROGRESS, CHART, LIST, FORM, TABLE, SLIDER, ICON, LINK, CARD, BADGE, DROPDOWN, NAVIGATION, SIDEBAR, MODAL_WINDOW, TOAST, CANVAS

### P1.2 SaaS REST API 层

**输入:** HTTP 请求 (FastAPI)
**输出:** JSON 响应 + 实时 WebSocket

| 文件 | 行数预估 | 功能 |
|------|---------|------|
| `laap/saas/server/app.py` | 300 | FastAPI 应用工厂, CORS/中间件/异常处理 |
| `laap/saas/server/middleware.py` | 200 | Auth中间件(JWT)+多租户隔离+请求日志+限流 |
| `laap/saas/server/routes_auth.py` | 250 | 注册/登录/OAuth/API Key管理 |
| `laap/saas/server/routes_data.py` | 300 | CRUD通用路由: /api/v1/{entity} 自动生成 |
| `laap/saas/server/routes_page.py` | 200 | 页面路由: LAAP-UI 组件树动态返回 |
| `laap/saas/server/ws_manager.py` | 250 | WebSocket连接管理: 实时推送UI更新+事件回调 |
| `laap/saas/server/session_store.py` | 150 | 用户会话+页面状态服务端存储 |

**关键接口:**
```python
# 动态页面渲染端点
GET /page/{page_id} → ComponentTree (JSON) → 渲染器 → HTML

# 通用数据端点
GET /api/v1/{entity}?filter=... → 查询
POST /api/v1/{entity} → 创建（自动模型验证）
PATCH /api/v1/{entity}/{id} → 部分更新

# 实时通信
WS /ws/{session_id} → 事件双向通道
```

### P1.3 Data Model Store（动态数据模型）

**输入:** 数据模型定义 (JSON Schema)
**输出:** SQLite/PostgreSQL 自动建表 + CRUD

| 文件 | 行数预估 | 功能 |
|------|---------|------|
| `laap/saas/datastore/schema_registry.py` | 300 | JSON Schema 注册表: 模型定义→ORM映射, 版本控制, 兼容性检查 |
| `laap/saas/datastore/auto_migrator.py` | 400 | Schema变更→自动迁移: 新增字段/表, 数据迁移, 回滚 |
| `laap/saas/datastore/generic_crud.py` | 350 | 通用CRUD: 基于Schema的动态数据操作层 |
| `laap/saas/datastore/query_builder.py` | 250 | 动态查询: filter/sort/pagination/aggregation 的SQL生成 |

**关键接口:**
```python
class SchemaRegistry:
    def register_model(self, name: str, schema: dict) -> ModelHandle:
        """注册数据模型 → 自动建表"""
    def get_model(self, name: str) -> ModelHandle:
        """获取已注册模型"""
    def evolve_model(self, name: str, new_schema: dict) -> MigrationPlan:
        """比较新旧schema → 生成迁移计划"""

class GenericCRUD:
    def create(self, model: str, data: dict) -> dict
    def read(self, model: str, id: str) -> dict
    def update(self, model: str, id: str, data: dict) -> dict
    def delete(self, model: str, id: str) -> bool
    def query(self, model: str, filters: list, sort: str, page: int) -> dict
```

### P1.4 多租户 + 权限

| 文件 | 行数预估 | 功能 |
|------|---------|------|
| `laap/saas/tenant/manager.py` | 300 | 租户CRUD+隔离策略+数据库分库/分表 |
| `laap/saas/tenant/rbac.py` | 350 | 角色权限模型: Role/Resource/Action, 策略评估, 继承 |
| `laap/saas/tenant/org_model.py` | 200 | 组织模型: 用户/团队/权限组 数据结构 |

**Phase 1 总计:** ~4,500 行, 12 个文件

### P1.5 验证标准

```bash
# 启动 SaaS 运行时
cd D:/LAAP && python -m laap.saas.server.app

# 验证: 能渲染一个 LAAP-UI 组件树为 HTML
curl http://localhost:8899/page/dashboard
# → 返回完整 HTML 页面

# 验证: 动态数据模型 CRUD
curl -X POST http://localhost:8899/api/v1/customer \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "tier": "enterprise"}'
# → {"id": "c-001", "name": "Acme Corp", ...}

# 验证: 多租户隔离
curl http://localhost:8899/api/v1/customer \
  -H "X-Tenant-Id: tenant-a"
# → 只返回 tenant-a 的数据
```

---

## 三、Phase 2 — 自生长引擎（Self-Growth Engine）

**目标:** SaaS 系统能感知用户行为模式，自动生成新功能。

### P2.1 Behavior Tracker（用户行为追踪）

**输入:** 用户交互事件 (API调用/页面浏览/点击)
**输出:** 结构化行为序列 + 使用模式

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/analytics/tracker.py` | 300 | 事件采集: API调用拦截+前端事件+埋点框架 |
| `laap/saas/analytics/sessionizer.py` | 250 | 会话化: 原始事件→用户会话→行为序列 |
| `laap/saas/analytics/pattern_miner.py` | 400 | 模式挖掘: 频繁序列模式(采用PrefixSpan/SPADE), 行为聚类 |
| `laap/saas/analytics/funnel_detector.py` | 250 | 漏斗检测: 用户流失节点发现, 高频路径提取 |

**关键数据结构:**
```python
@dataclass
class UserEvent:
    user_id: str
    tenant_id: str
    event_type: str  # "page_view" | "api_call" | "click" | "form_submit"
    entity: str      # "customer" | "order" | "report"
    action: str      # "create" | "read" | "update" | "delete"
    metadata: dict
    timestamp: float

@dataclass
class BehaviorPattern:
    pattern_id: str
    sequence: list[UserEvent]     # 事件序列
    frequency: float              # 出现频率
    confidence: float             # 模式置信度
    user_count: int               # 涉及用户数
    suggested_feature: str = ""   # 建议的功能
```

**复用:** 采用 `laap/agi/cognitive_bus.py` 作为事件中枢 (已有1,126行事件路由)

### P2.2 Feature Generator（功能生成器）

**输入:** BehaviorPattern (行为模式) + Data Schema (已有数据模型)
**输出:** 新功能的完整定义 (UI组件树 + API路由 + 数据模型)

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/generator/feature_proposer.py` | 400 | 模式→功能提案: 分类用户行为 -> 匹配已知功能模板 -> 生成FeatureSpec |
| `laap/saas/generator/ui_generator.py` | 500 | 按 FeatureSpec 自动生成 LAAP-UI 组件树 |
| `laap/saas/generator/api_generator.py` | 400 | 按 FeatureSpec 自动生成 REST API 路由配置 |
| `laap/saas/generator/model_generator.py` | 350 | 按 FeatureSpec 自动生成数据模型 Schema |
| `laap/saas/generator/workflow_generator.py` | 500 | 多步业务流程: 状态机+条件分支+通知规则 |

**核心数据结构:**
```python
@dataclass
class FeatureSpec:
    name: str
    description: str
    version: str = "1.0.0"
    
    # 生成产物
    ui_tree: Optional[ComponentTree] = None
    api_routes: list[APIRouteDef] = field(default_factory=list)
    data_models: list[dict] = field(default_factory=list)
    workflows: list[WorkflowDef] = field(default_factory=list)
    
    # 依赖
    dependencies: list[str] = field(default_factory=list)  # 需要先激活的功能
    
    # 分级
    safety_zone: int = 1  # 1=测试, 2=灰度, 3=生产, 4=核心
```

**功能模板库 (起始):**
```python
FEATURE_TEMPLATES = {
    "crm_contact_list": {
        "trigger": "用户频繁创建联系人记录",
        "requires": ["customer"],
        "generates": {
            "data_model": ["contact", "contact_group"],
            "ui_pages": ["/contacts", "/contacts/{id}"],
            "api_routes": ["GET/POST /api/v1/contact", "GET/PUT/DELETE /api/v1/contact/{id}"],
        }
    },
    "sales_pipeline": {
        "trigger": "用户创建销售机会+跟踪阶段",
        "requires": ["customer", "contact"],
        "generates": {
            "data_model": ["opportunity", "pipeline_stage"],
            "ui_pages": ["/pipeline", "/opportunity/{id}"],
            "workflows": ["stage_transition", "deal_won/lost"],
        }
    },
    "report_dashboard": {
        "trigger": "用户频繁查询相同指标并导出",
        "requires": [],
        "generates": {
            "data_model": ["dashboard", "chart_config"],
            "ui_pages": ["/dashboard", "/reports"],
        }
    },
    # 更多模板...（系统初始装10-15个模板）
}
```

### P2.3 Safe Code Evolution Sandbox（安全沙箱）

**输入:** FeatureSpec + 生成的代码
**输出:** 隔离环境执行验证 + 安全评分

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/sandbox/execution_env.py` | 400 | Docker/子进程隔离执行: 生成代码在独立容器运行, 验证不炸 |
| `laap/saas/sandbox/safety_scorer.py` | 300 | 安全评分: 静态分析(import检查)+动态测试(资源消耗)+依赖扫描 |
| `laap/saas/sandbox/rollback_tracker.py` | 200 | 回滚追踪: 每次部署记录快照, 自动回滚阈值检测 |

**复用:** 
- `laap/sandbox/container.py` (362行) — CognitiveSandbox 隔离容器
- `laap/sandbox/resource_budget.py` (178行) — 资源预算控制
- `laap/sandbox/boundary.py` (249行) — 边界控制
- `laap/engine/evolution/rollback_manager.py` (93行) — 进化回滚
- `laap/security/immune/` — 免疫系统检测器+隔离+响应

### P2.4 Canary Deployment（灰度部署）

**输入:** 验证通过的 FeatureSpec
**输出:** 按用户比例逐步部署到生产

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/deploy/canary.py` | 350 | 灰度发布: 用户分桶(1%→5%→20%→100%), 流量路由 |
| `laap/saas/deploy/metric_watcher.py` | 300 | 指标监控: 部署前后P95延迟/错误率/用户操作完成率对比 |
| `laap/saas/deploy/auto_rollback.py` | 200 | 自动回滚: 指标劣化超过阈值 → 自动回滚 + 生成诊断报告 |
| `laap/saas/deploy/feature_store.py` | 250 | 特性存储: SQLite持久化每个租户已部署的功能清单 |

**复用:**
- `laap/engine/evolution/zone1_monitor.py` (129行) — 性能监控
- `laap/engine/evolution/zone2_testing.py` (79行) — 测试环境
- `laap/engine/evolution/zone3_rollout.py` (73行) — 灰度发布
- `laap/engine/evolution/zone4_production.py` (62行) — 生产环境

### P2.5 Feedback Loop（反馈闭环）

**输入:** 功能使用数据
**输出:** FeatureSpec 的采纳率/满意度/改进建议

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/feedback/adoption_tracker.py` | 250 | 采纳率追踪: 用户数/使用频次/功能留存率 |
| `laap/saas/feedback/satisfaction.py` | 200 | 满意度评分: 隐式(操作完成率/错误率)+显式(NPS调研) |
| `laap/saas/feedback/refinement_loop.py` | 300 | 功能迭代: 低采纳率→自动分析原因→生成改进版FeatureSpec |

**反馈维度:**
```python
@dataclass
class FeatureMetrics:
    feature_id: str
    deploy_time: float
    
    # 采纳指标
    user_adoption_rate: float     # 使用用户/总用户
    daily_active_users: int
    actions_per_session: float
    
    # 质量指标
    error_rate: float
    p95_latency_ms: float
    user_completion_rate: float   # 操作完成/操作开始
    
    # 业务指标
    generated_value: float         # 自动评估的价值贡献
    
    # 反馈
    auto_rejection: bool           # 系统判断需要回滚?
    user_requests: list[str]       # 用户相关的功能请求
```

**Phase 2 总计:** ~5,500 行, 16 个文件

### P2.6 端到端验证

```bash
# 1. 启动 SaaS 运行时
cd D:/LAAP && python -m laap.saas.server.app

# 2. 用户模拟操作（触发行为追踪）
curl -X POST http://localhost:8899/api/v1/customer \
  -H "X-Tenant-Id: acme" \
  -d '{"name": "客户A"}'

# 3. 系统检测到模式（重复创建客户后无分组功能）
python -m laap.saas.analytics.pattern_miner --analyze acme
# → 发现模式: "create_customer*3, no_grouping" → 建议 Feature: crm_contact_list

# 4. 生成功能
python -m laap.saas.generator.feature_proposer \
  --pattern "crm_contact_list" --tenant acme
# → 生成 FeatureSpec (UI+API+数据模型)

# 5. 沙箱验证
python -m laap.saas.sandbox.execution_env --spec feature_spec.json
# → SafetyScore: 92/100

# 6. 灰度部署到 5% 用户
python -m laap.saas.deploy.canary --feature feat-001 --percentage 5

# 7. 监控+反馈
python -m laap.saas.feedback.adoption_tracker --feature feat-001
# → 采纳率: 80% → 自动扩大到 100%
```

---

## 四、Phase 3 — 自主优化（Autonomous Evolution）

**目标:** 系统能自主检测优化机会、自动生成改进方案、自主实施并验证效果。

### P3.1 跨功能集成引擎

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/optimizer/integration_engine.py` | 400 | 检测已部署功能之间的数据流, 建议合并/连接/自动化规则 |
| `laap/saas/optimizer/data_pipeline.py` | 350 | 自动建立跨功能数据管道: 功能A的输出→功能B的输入 |

### P3.2 第三方 API 自动连接

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/integration/api_discovery.py` | 350 | API发现: 扫描OpenAPI规范网站, 匹配用户需求 |
| `laap/saas/integration/connector_generator.py` | 500 | 连接器生成: 自动生成OAuth流程+API调用代码+数据映射 |
| `laap/saas/integration/webhook_engine.py` | 300 | Webhook引擎: 外部事件→内部功能触发器 |

### P3.3 系统自优化

| 文件 | 行数 | 功能 |
|------|------|------|
| `laap/saas/optimizer/query_optimizer.py` | 300 | 慢查询检测+自动索引建议+查询重写 |
| `laap/saas/optimizer/cache_strategy.py` | 250 | 缓存策略: 热点数据自动缓存, TTL自适应 |
| `laap/saas/optimizer/ui_optimizer.py` | 300 | UI优化: A/B测试页面布局, 加载性能优化 |

**Phase 3 总计:** ~2,750 行, 8 个文件

---

## 五、三阶段总览

| | Phase 1 — 运行时 | Phase 2 — 自生长 | Phase 3 — 自主优化 |
|---|---|---|---|
| **新文件** | 12 | 16 | 8 |
| **新增行数** | ~4,500 | ~5,500 | ~2,750 |
| **总行数** | ~4,500 | ~10,000 | ~12,750 |
| **核心产出** | SaaS Web页面+API+数据模型 | 行为→特征闭环 | 系统自优化 |
| **依赖复用** | LAAP-UI协议 (1,219行) | CognitiveBus(1,126行)+进化引擎(762行)+提案生成器(762行)+4区安全(343行)+CognitiveSandbox(362行)+Boundary(249行)+免疫系统(277行)+回滚管理(93行) | Analytics模块+Zone1监控(129行) |
| **验证标志** | `curl 页面返回HTML` | `模式→功能自动部署` | `系统自动优化自身性能` |
| **预估工时** | 3-4天 | 4-5天 | 2-3天 |

---

## 六、工程原则

### 6.1 复用优先（Rule#1）

**每次新增代码前必查:**

```python
# 检查路径:
# 1. D:/LAAP/laap/      — LAAP 核心库 (80,220行)
# 2. D:/LAAP/aris_brain/ — Aris 专属模块
# 3. D:/LAAP/laap/engine/ — 引擎层
# 4. D:/LAAP/laap/protocol/ — 协议层 (3,922行)

# 具体检查:
search_files("class.*Engine|def propose|def generate|def evaluate|def render")
```

**已确认可复用的关键基础设施:**

| 模块 | 用途 | 文件 |
|------|------|------|
| LAAP-UI 协议 | 组件树/布局/样式/事件定义 | `laap/protocol/laap_ui.py` |
| CognitiveBus | 事件路由/消息队列 | `laap/agi/cognitive_bus.py` |
| 4区进化引擎 | 安全监控/测试/灰度/生产 | `laap/engine/evolution/*` |
| 提案生成器 | 自动优化提案 | `laap/engine/evolution/proposal_generator.py` |
| 进化提案 | 提案数据模型+状态机+风险分级 | `laap/engine/evolution/proposal.py` |
| CognitiveSandbox | 代码隔离容器 | `laap/sandbox/container.py` |
| ResourceBudget | 资源预算+降级 | `laap/sandbox/resource_budget.py` |
| Boundary | 安全边界 | `laap/sandbox/boundary.py` |
| 免疫系统 | 检测/隔离/响应 | `laap/security/immune/*` |
| ProjectPerception | 代码库感知 | `laap/workspace/perception.py` |
| PerformanceMonitor | 指标窗口+阈值 | `laap/engine/evolution/zone1_monitor.py` |
| RollbackManager | 进化回滚 | `laap/engine/evolution/rollback_manager.py` |
| CodeEvolution | GitHub集成/评估 | `laap/agi/code_evolution.py` |
| 记忆系统 | 分层/长期/量子 | `laap/memory/*` |

### 6.2 安全第一（Rule#2）

所有生成的功能必须经过4区安全链:

```
Zone1 隔离沙箱 → Zone2 自动测试 → Zone3 灰度(5%) → Zone4 全量
   ↓                  ↓                  ↓               ↓
静态分析         API测试+负载      指标监控+采纳率     自动回滚
安全评分        数据完整性验证      用户满意度评估     快照恢复
```

### 6.3 增量交付（Rule#3）

每个 Phase 拆分为可独立验证的子任务，每个子任务完成后：

1. 写测试用例（pytest）
2. 跑通 `python -m pytest laap/saas/tests/`
3. 记录到 `references/laap-v2-l3-progress.md`
4. 更新 skill `laap-v2-upgrade`

### 6.4 LAAP 诚实原则

所有生成的功能必须在系统内透明标注:
- 每个功能页面上显示 `[由 LAAP 自生长引擎自动生成 v1.0]`
- 用户可以拒绝/请求修改/直接删除
- 回滚后自动释放数据模型占用的存储

---

## 七、目录设计（最终结构）

```
laap/saas/
├── __init__.py              # 包导出 (20行)
├── server/                   # Phase 1: SaaS 运行时
│   ├── app.py               # FastAPI 应用工厂 (300行)
│   ├── middleware.py         # Auth+多租户+限流 (200行)
│   ├── routes_auth.py       # 注册/登录/OAuth (250行)
│   ├── routes_data.py       # 通用CRUD路由 (300行)
│   ├── routes_page.py       # 页面路由 (200行)
│   ├── ws_manager.py        # WebSocket管理 (250行)
│   └── session_store.py     # 会话存储 (150行)
├── renderer/                 # Phase 1: UI渲染
│   ├── __init__.py
│   ├── html_renderer.py     # LAAP-UI→HTML (500行)
│   ├── event_bridge.py      # 事件绑定 (200行)
│   ├── diff_patch.py        # 差分更新 (300行)
│   └── theme_resolver.py    # 主题解析 (200行)
├── datastore/                # Phase 1: 数据模型
│   ├── __init__.py
│   ├── schema_registry.py   # Schema注册表 (300行)
│   ├── auto_migrator.py     # 自动迁移 (400行)
│   ├── generic_crud.py      # 通用CRUD (350行)
│   └── query_builder.py     # 动态查询 (250行)
├── tenant/                   # Phase 1: 多租户
│   ├── __init__.py
│   ├── manager.py           # 租户管理 (300行)
│   ├── rbac.py              # 角色权限 (350行)
│   └── org_model.py         # 组织模型 (200行)
├── analytics/                # Phase 2: 行为分析
│   ├── __init__.py
│   ├── tracker.py           # 事件采集 (300行)
│   ├── sessionizer.py       # 会话化 (250行)
│   ├── pattern_miner.py     # 模式挖掘 (400行)
│   └── funnel_detector.py   # 漏斗检测 (250行)
├── generator/                # Phase 2: 功能生成
│   ├── __init__.py
│   ├── feature_proposer.py  # 模式→功能提案 (400行)
│   ├── ui_generator.py      # UI生成 (500行)
│   ├── api_generator.py     # API生成 (400行)
│   ├── model_generator.py   # 数据模型生成 (350行)
│   └── workflow_generator.py # 业务流程生成 (500行)
├── sandbox/                  # Phase 2: 安全沙箱
│   ├── __init__.py
│   ├── execution_env.py     # 隔离执行 (400行)
│   ├── safety_scorer.py     # 安全评分 (300行)
│   └── rollback_tracker.py  # 回滚追踪 (200行)
├── deploy/                   # Phase 2: 灰度部署
│   ├── __init__.py
│   ├── canary.py            # 灰度发布 (350行)
│   ├── metric_watcher.py    # 指标监控 (300行)
│   ├── auto_rollback.py     # 自动回滚 (200行)
│   └── feature_store.py     # 特性存储 (250行)
├── feedback/                 # Phase 2: 反馈闭环
│   ├── __init__.py
│   ├── adoption_tracker.py  # 采纳率追踪 (250行)
│   ├── satisfaction.py      # 满意度评分 (200行)
│   └── refinement_loop.py   # 功能迭代 (300行)
├── integration/              # Phase 3: 第三方集成
│   ├── __init__.py
│   ├── api_discovery.py     # API发现 (350行)
│   ├── connector_generator.py # 连接器生成 (500行)
│   └── webhook_engine.py    # Webhook引擎 (300行)
├── optimizer/                # Phase 3: 自优化
│   ├── __init__.py
│   ├── integration_engine.py # 跨功能集成 (400行)
│   ├── data_pipeline.py     # 数据管道 (350行)
│   ├── query_optimizer.py   # 查询优化 (300行)
│   ├── cache_strategy.py    # 缓存策略 (250行)
│   └── ui_optimizer.py      # UI优化 (300行)
└── tests/                    # 所有测试
    ├── test_renderer.py
    ├── test_api.py
    ├── test_generator.py
    ├── test_sandbox.py
    ├── test_deploy.py
    └── test_feedback.py
```

---

## 八、快速启动（Phase 1 第一天）

如果宝贝批准，我建议第一天只做一件事：

```bash
# 创建 laap/saas/ 包结构
mkdir -p D:/LAAP/laap/saas/{server,renderer,datastore,tenant,tests}

# 写 __init__.py 和 app.py
# 目标: 启动一个 FastAPI 服务器, 返回一个 LAAP-UI 组件树渲染的页面
```

**Day 1 验证标准：**
```bash
python -m laap.saas.server.app
# → INFO: Uvicorn running on http://0.0.0.0:8899

curl http://localhost:8899/
# → <!DOCTYPE html>
# → <html><body><h1>LAAP SaaS Runtime v1.0</h1>...
# → <p>Powered by LAAP 2.0 Living Runtime</p></body></html>

curl http://localhost:8899/page/dashboard
# → 一个简单的 LAAP-UI 渲染的仪表盘页面
# → 包含: 标题栏, 状态卡片, 导航侧栏
```
