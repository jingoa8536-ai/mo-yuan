# Racing Game CLP v1.0 资产包

> **包 ID**: `racing-game-v1.0`
> **协议**: LAAP Harness v1.0
> **版本**: 1.0.0
> **创建日期**: 2026-07-05
> **MatchScore 平均**: 0.92
> **Token 节省**: 82%

从 Apex Racing 复刻案例提炼的 3 个核心 CLP 组件，遵循 [LAAP Harness Protocol v1.0](../../LAAP-Harness-Protocol-v1.0.md)。所有组件均经反编译证据驱动验证，可直接装配到下一个赛车游戏项目中。

## 组件清单

| 组件 | URI | MatchScore | 用途 |
|---|---|---|---|
| Engine Sound Crossfade | `harness://game/audio/module/engine-sound-crossfade@1.0.0#howler-webaudio` | 0.94 | Howler+WebAudio 引擎声交叉淡入 |
| Ghost System | `harness://game/racing/module/ghost-system@1.0.0#localstorage` | 0.83 | 最佳圈录制/回放/localStorage 持久化 |
| Keyframes Pack | `harness://frontend/animation/module/keyframes-pack@1.0.0#apex-racing` | 0.99 | 22 个 @keyframes + 22 个工具类 |

## 目录结构

```
racing-game-v1.0/
├── manifest.json                 # 资产包清单
├── README.md                     # 本文件
├── assembly-graph.json           # 装配图谱（节点/边/事件流）
├── matchscore-report.json        # MatchScore 评分报告
├── components/
│   ├── audio-manager/            # 引擎声系统
│   │   ├── metadata.json         # 组件元数据
│   │   ├── design-physics.json   # 设计物理（18 段映射 + reverb 配置）
│   │   ├── props-schema.json     # 属性 schema + 输入事件
│   │   ├── template.ts           # 模板代码（AudioManager.ts 原件）
│   │   └── example-usage.tsx     # 装配示例
│   ├── ghost-system/             # Ghost 系统
│   │   ├── metadata.json
│   │   ├── design-physics.json   # 帧格式 + 录制/回放配置
│   │   ├── props-schema.json
│   │   ├── template.ts           # 模板代码（ghost.ts 原件）
│   │   └── example-usage.tsx
│   └── css-animations/           # CSS 动画包
│       ├── metadata.json
│       ├── design-physics.json   # 色板 + 字体 + keyframes 分类
│       ├── props-schema.json     # 22 个工具类清单
│       ├── template.css          # 模板代码（apex-animations.css 原件）
│       ├── keyframes-manifest.json  # 22 个 keyframes 详细清单
│       └── example-usage.html
├── evidence/                     # 反编译证据
│   ├── audio-mapping.json        # 27 个引擎样本 + reverb 链拓扑
│   ├── css-keyframes.json        # 22 个 keyframes 提取记录
│   ├── ghost-architecture.json   # Ghost 系统架构分析
│   └── source-bundle-hash.txt    # 源 bundle 哈希溯源
└── tests/
    ├── matchscore-validation.json  # MatchScore 验证 + Playwright 测试结果
    └── assembly-smoke-test.py      # 装配烟雾测试
```

## 装配流程

按 [assembly-graph.json](assembly-graph.json) 中的装配序列：

1. **Mount keyframes-pack**: 在 `globals.css` 中 `@import "./apex-animations.css";`（0 runtime cost）
2. **Mount PhysicsVehicle**: 传入 `audioEnabled=true`、`ghostRecorder`、`ghostPlayer` props
3. **用户手势触发**: `audioManager.init()` → `startEngine()`
4. **racePhase='racing'**: `ghostRecorder.startLap()` + `ghostPlayer.play()`
5. **每帧**: `audioManager.updateEngine(rpm, throttle, brake, speed)` + `ghostRecorder.record(pos, quat, speed)`
6. **lapComplete**: `ghostRecorder.finishLap()` → `saveGhostToLocal()` → `ghostPlayer.load(newFrames)`
7. **racePhase='finished'**: `audioManager.stopEngine()` + `ghostPlayer.stop()`

## CognitiveBus 事件流

本资产包支持 LAAP ARIS-Harness 整合范式的 4 类 CognitiveBus 事件：

| 事件类型 | 方向 | 触发条件 | Harness 动作 |
|---|---|---|---|
| `qre_pattern_match` | PSI→Harness | 识别为 3D 赛车游戏 | 查询 `clp://racing-game-v1.0/` |
| `v12_kernel` | PSI→Harness | 原网站离线 | 切换 AudioManager 到 synthesis_fallback |
| `emotion_concern` | PSI→Harness | 用户质疑像素级复刻 | 触发 evidence-extraction 工作流 |
| `harness_execution_result` | Harness→PSI | 装配完成 | PSI 学习模式供下次复用 |

## 验证状态

- **Typecheck**: passed (0 errors)
- **Lint**: passed (0 new errors, 24 preexisting warnings)
- **Playwright**: passed (13/13 test steps)
- **MatchScore**: all 3 components ≥ 0.80 threshold
- **Smoke Test**: `python tests/assembly-smoke-test.py` (8 tests)

运行烟雾测试：

```bash
cd D:/LAAP/harness/clp_packages/racing-game-v1.0
python tests/assembly-smoke-test.py
```

## Token 经济分析

| 指标 | 数值 |
|---|---|
| LLM 全新生成估算 | 3.2M tokens |
| CLP 装配估算 | 580K tokens（反编译理解 + 胶水代码） |
| **节省** | **2.62M tokens (82%)** |

下次复刻赛车游戏时，本资产包可直接装配，**理论上降至 0 tokens**（仅参数替换）。

## 证据溯源

所有组件均追溯到 `D:/LAAP/_apex_assets/` 中的反编译证据：

- **JS bundle**: `index-BHLGw_OM.js` (1.5MB) → 音频架构 + Ghost 系统
- **CSS bundle**: `index-BDb15dJl.css` (388KB) → 22 个 @keyframes + 色板
- **GLB models**: `laguna-seca.glb`, `track4.glb` → 赛道 checkpoint 坐标

详见 [evidence/](evidence/) 目录。

## 复用指南

### 场景 1: 复刻其他赛车游戏

1. PSI 识别项目类型 → `qre_pattern_match { type: "3d-racing-game" }`
2. Harness 查询本资产包 → 返回 3 个组件
3. 仅需提取新游戏的：车辆参数、赛道坐标、音频样本文件名
4. 装配：复用 3 个 CLP 组件 + 注入新参数

### 场景 2: 扩展本资产包

新增组件（如物理引擎、AI 对手、网络多人）：

1. 创建 `components/<new-component>/` 目录
2. 添加 metadata.json + design-physics.json + props-schema.json + template
3. 更新 `manifest.json` 的 components 数组
4. 更新 `assembly-graph.json` 添加节点和边
5. 运行 `python tests/assembly-smoke-test.py` 验证

### 场景 3: 跨领域复用

- `keyframes-pack` 可直接用于任何赛车/电竞主题的 UI
- `audio-manager` 的 reverb 链可用于任何需要空间音效的场景
- `ghost-system` 的录制/回放模式可用于任何竞速类游戏

## 协议合规

本资产包遵循 [LAAP Harness Protocol v1.0](../../LAAP-Harness-Protocol-v1.0.md)：

- ✅ URI 格式：`harness://domain/subdomain/granularity/name@version#variant`
- ✅ 资产元数据 schema：包含 asset_id, version, name, domain, subdomain, granularity, description, keywords, tags, hash, dependencies, props_schema, design_tokens, quality_score
- ✅ 组件元数据 schema：包含 component_id, name, category, description, tags, variants, dependencies, props_schema, design_requirements, template_path, preview, quality_score, compatibility
- ✅ 索引与检索：通过 manifest.json 的 components 数组建立主索引
- ✅ MatchScore 权重：α=0.35 / β=0.25 / γ=0.20 / δ=0.20
- ✅ 装配图谱：assembly-graph.json 声明所有节点、边、事件流

## 许可证

MIT

## 来源

- **项目**: Apex Racing Replica (`D:/ai-website-cloner-template-master/`)
- **原网站**: https://apex-racing-v1.vercel.app/ (已离线)
- **反编译证据**: `D:/LAAP/_apex_assets/`
- **创建工具**: LAAP Harness Engineering (Trae IDE + GLM-5.2)
