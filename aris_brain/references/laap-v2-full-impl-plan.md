# LAAP 2.x 全量工程实施计划

**开始日期:** 2026-06-27
**总工期:** 7-10 天
**总新增代码:** ~8,500 行

---

## 实施总览

```
Phase A: 2.0 基础完成     (3天, ~3,000行)
  ├─ A1 SaaS数据模型层      (1天, ~600行)
  ├─ A2 SaaS多租户          (0.5天, ~500行)
  ├─ A3 Colony → SaaS 桥接  (0.5天, ~400行)
  ├─ A4 SaaS自启+守护       (0.5天, ~200行)
  └─ A5 ProjectPerception优化 (0.5天, ~300行)

Phase B: 2.1 生命体运行时   (3天, ~3,500行)
  ├─ B1 laap/lifeform/ 包   (1.5天, ~1,500行)
  ├─ B2 认知持久化协议+序列化 (1天, ~1,000行)
  └─ B3 Hermes Desktop集成   (0.5天, ~500行)

Phase C: 全栈融合+测试      (2天, ~2,000行)
  ├─ C1 端到端测试套件       (1天, ~1,000行)
  ├─ C2 启动脚本文档         (0.5天, ~300行)
  └─ C3 性能优化+边界处理    (0.5天, ~700行)
```

---

## Phase A — 2.0 基础完成

### A1: SaaS 数据模型层

**目标:** `POST /api/v1/{entity}` 自动建表 + CRUD

| 文件 | 行数 | 描述 |
|------|------|------|
| `laap/saas/datastore/__init__.py` | 10 | 包导出 |
| `laap/saas/datastore/schema_registry.py` | 200 | JSON Schema 注册 → SQLite 自动建表 |
| `laap/saas/datastore/generic_crud.py` | 250 | create/read/update/delete/query |
| `laap/saas/datastore/auto_migrator.py` | 150 | Schema 版本控制 + 迁移 + 回滚 |

**验证:** `curl POST /api/v1/product -d '{"name":"叉车","price":999}'` → 自动建 products 表 + 返回记录

### A2: SaaS 多租户

**目标:** 每个租户数据隔离

| 文件 | 行数 | 描述 |
|------|------|------|
| `laap/saas/tenant/__init__.py` | 10 | |
| `laap/saas/tenant/manager.py` | 200 | 租户 CRUD + 隔离策略 |
| `laap/saas/tenant/rbac.py` | 250 | 角色/资源/动作权限模型 |
| `laap/saas/tenant/org_model.py` | 100 | 用户/团队/权限组 |

**验证:**
- 租户A 看不到 租户B 的数据
- `curl -H "X-Tenant-Id: acme" /api/v1/product` 只返回 acme 的

### A3: Colony → SaaS 桥接

**目标:** ArchitectAgent/TestEngineerAgent 在 SaaS 页面可见可操作

| 文件 | 行数 | 描述 |
|------|------|------|
| `laap/saas/server/app.py` (修改) | +200 | 全局初始化 + API 端点 |
| `laap/saas/pages/agents.py` | 200 | Agent 管理页面 |

**API:**
```
GET  /api/agents                        → 列表
GET  /api/agents/{id}                   → 详情
POST /api/agents/{id}/perceive          → 触发感知
GET  /api/agents/{id}/suggestions       → 当前建议
```

### A4: SaaS 自启 + 守护

**目标:** 机器重启后 SaaS 自动在 :8910 监听

| 文件 | 行数 | 描述 |
|------|------|------|
| `aris_brain/laap_saas_launcher.py` | 100 | 独立启动脚本 |
| `aris_watchdog.py` (修改) | +50 | 加入 SaaS 进程监控 |

### A5: ProjectPerception 优化

**目标:** LAAP 根目录(68万行)扫描 <10s

| 文件 | 行数 | 描述 |
|------|------|------|
| `laap/workspace/perception.py` (修改) | +200 | max_files 参数 + skip_dirs + 增量扫描 |

---

## Phase B — 2.1 生命体运行时

### B1: `laap/lifeform/` 核心包

**目标:** 把散落的引擎(PSI/QRE/因果/记忆...)包装成一个可创建、可配置、可持久化的 Lifeform 实例

```
laap/lifeform/
├── __init__.py              (30行)  包导出
├── lifeform.py              (400行) Lifeform 类 — 引擎链初始化 + 生命周期
├── engine_setup.py          (200行) 引擎组装工厂 (PSI / QRE / V12 / 因果 / 记忆)
├── serializer.py            (250行) 状态序列化 (PSI态+因果图+记忆+情绪 → JSON)
├── config.py                (150行) 配置解析 (YAML → LifeformConfig)
├── cli.py                   (300行) 命令行: create / save / restore / status / list
└── tests/                   (200行) 单元测试
```

**Lifeform 类核心设计:**
```python
class Lifeform:
    """可部署、可持久化的数字生命体"""
    
    def __init__(self, config: LifeformConfig):
        self.config = config
        self.psi = None         # 运行时懒加载
        self.causal = None      # 因果引擎
        self.world_model = None # 世界模型
        self.memory = None      # 五层记忆
        self.conscious = None   # 意识流
        
    def wake(self) -> bool:
        """唤醒 — 从配置初始化所有引擎"""
        self.psi = PSICycle(config.psi_profile)
        self.causal = UnifiedCausalEngine()
        # ...
        
    def sleep(self) -> dict:
        """休眠 — 序列化全部状态"""
        return {
            "psi_state": self.psi.serialize(),
            "causal_graph": self.causal.serialize(),
            # ...
        }
        
    def save(self, path: str) -> str:
        """持久化到文件"""
        
    @staticmethod
    def load(path: str) -> "Lifeform":
        """从文件恢复"""
```

### B2: 认知持久化协议

**目标:** YAML 配置 → 可部署的生命体

```yaml
# laap-lifeform.yaml
apiVersion: laap.io/v1
kind: Lifeform
metadata:
  name: project-alpha
  created: 2026-06-27
spec:
  identity:
    name: "项目阿尔法守护者"
    role: "architect"
    personality:
      openness: 0.8
      conscientiousness: 0.9
  psiProfile:
    baseNeeds: [certainty: 0.6, competence: 0.7, exploration: 0.5]
    riskAppetite: 0.3
  memory:
    workingCapacity: 7
    episodicRetention: 1000
    consolidationInterval: 300
  engines:
    psi: true
    qre: true
    causal: true
    worldModel: "local"
  governance:
    humanOversight: required_for_code_changes
    auditLevel: full
  languageCortex:
    provider: "deepseek"
    model: "deepseek-chat"
```

| 文件 | 行数 | 描述 |
|------|------|------|
| `laap/lifeform/config.py` | 150 | YAML → LifeformConfig dataclass |
| `laap/lifeform/serializer.py` | 250 | 状态 ↔ JSON 序列化 |
| `references/laap-lifeform-spec.md` | 200 | 协议文档 |

### B3: Hermes Desktop Lifeform 集成

**目标:** Society 页面可以创建/管理/查看 Lifeform

| 文件 | 行数 | 描述 |
|------|------|------|
| `src/renderer/.../LaapSociety.tsx` (修改) | +200 | 添加 Lifeform 面板 |
| `src/main/laap.ts` (修改) | +50 | IPC: laap-create-lifeform / laap-list-lifeforms |
| `src/preload/index.ts` (修改) | +4 | 新 IPC 方法 |

---

## Phase C — 全栈融合 + 测试

### C1: 端到端测试套件

```
D:/LAAP/laap/saas/tests/
├── test_renderer.py         (200行) LAAP-UI → HTML 渲染测试
├── test_server.py           (200行) API 端点测试
├── test_datastore.py        (200行) Schema注册 + CRUD
├── test_tenant.py           (150行) 多租户隔离
├── test_lifeform.py         (200行) Lifeform 创建/保存/恢复
└── test_integration.py      (200行) 全链路: SaaS→Colony→Lifeform

D:/hermes-desktop/hermes-desktop-main/tests/
└── test_laap.py             (150行) Electron IPC 桥接测试
```

### C2: 启动脚本

```bash
# 一条命令启动完整 LAAP 2.x
laap-start-society.sh
# → 1. 启动 LAAP Society Server (:8911)
# → 2. 启动 LAAP SaaS (:8910)
# → 3. 初始化 CognitiveSandbox x3
# → 4. 注册默认 Agent
# → 5. 等待用户命令
```

### C3: 性能优化 + 边界处理

- `_scan_files()` 超时保护 (max_files=5000)
- `Component.to_dict()` 循环引用检测
- Lifeform 错误恢复 (corrupted save → back to defaults)
- SaaS 请求限流 (100 req/min per tenant)

---

## 实施顺序与依赖

```
Day 1 ────────
  A1 数据模型层     (无前置依赖)
  A2 多租户          (依赖 A1)
  
Day 2 ────────
  A3 Colony→SaaS    (可并行 A1/A2)
  A4 SaaS自启       (可并行)
  A5 Perception优化 (可并行)

Day 3 ────────
  B1 lifeform 核心   (依赖 Phase A 完成, 因为 Lifeform 需要加载 LAAP 2.0 沙箱)
  
Day 4 ────────
  B2 持久化协议      (依赖 B1)
  B3 Hermes Desktop  (依赖 B1)

Day 5 ────────
  C1-3 测试+脚本+优化 (依赖全部完成)
```

---

## 工程质量标准

1. **每个文件写完立即跑** — `python -c "from laap.xxx import ...; print('OK')"`
2. **TypeScript 编译验证** — `npm run build` 不能有 error
3. **每个新 API 端点至少 curl 验证一次**
4. **每个函数 docstring** — 做什么、参数、返回值
5. **复用优先** — 每次写新代码前先搜 `class.*Engine|def.*generate`
6. **LAAP 诚实标注** — 所有 AI 生成内容标注来源
