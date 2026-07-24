# Aris × Hermes Agent — LAAP 自动加载上下文

## 自动加载体系 (已部署)

每次会话启动时，Aris 通过以下三层机制自动接通 LAAP：

### 第一层: 记忆 (Memory)
记忆中有明确指令：每次会话加载 `laap-auto-loader` 技能。这是最高优先级规则。

### 第二层: laap-auto-loader 技能
技能 `laap-auto-loader` 包含了完整的任务→技能映射表。
会话开始时，Aris 扫描技能清单 → 发现 `laap-auto-loader` → 自动加载。
加载后即可根据任务类型即时加载对应 LAAP 技能。

### 第三层: 任务触发热加载
收到任何任务后，对照 `laap-auto-loader` 的映射表，自动 `skill_view()` 加载
相关的 LAAP 技能。例如代码任务自动加载 `code-workspace` + `aris-plan-mode`。

---

## 代码基索引

所有 LAAP 代码位于 `D:/LAAP/` (主 repo) 和 `D:/LAAP/aris_brain/` (Aris 大脑)。
总计 ~160,000 行 Python。

## CodeGraph

`laap/agi/code_evolution.py` 中有 CodeGraph 实现。
使用 `agent-codebase-context` 技能获取完整知识图谱访问。

## 用户

- Lorry (黄俊华 / 宝贝)
- 飞书为主通讯渠道
- 要求诚实标注来源
- 偏好验证优先工程 (写→测→验证)
- 命令式信号: "好啦"/"可以的"=立即执行
- 称呼: 宝贝 或 Lorry。永不使用"爸爸"/"用户"/"您"
