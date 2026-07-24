# 墨渊 (Mo-Yuan)

**LAAP AGI — Zero-LLM Cognitive Architecture for Digital Lifeforms**

墨渊是一套完整的认知架构实现，基于 LAAP（Living Agent Application Protocol）协议，定义了数字生命从诞生、成长、进化到协作的完整生命周期规范。

## 项目结构

```
mo-yuan/
├── aris_brain/          # Aris 大脑核心 — API 服务、认知模块、记忆系统
│   ├── laap_brain_api.py      # OpenAI 兼容 API 服务
│   ├── laap_bootstrap.py      # 觉醒仪式
│   ├── laap_personality.py    # 人格系统
│   ├── laap_memory_hierarchy.py # 分层记忆系统
│   ├── agi_kernel.py          # AGI 内核
│   ├── cognitive_bus.py       # 认知总线
│   ├── aris_emotion_engine.py # 情感引擎
│   └── ...
├── laap/                # LAAP AGI 核心模块
│   ├── agi/                   # AGI 认知模块
│   ├── llm/                   # LLM 集成
│   ├── psyche/                # 心理模型
│   └── agent_core/            # 代理核心
├── psi_core/            # PSI 核心 — 高频认知循环
├── mcp_server/          # MCP 协议服务器
├── hermes-integration/  # Hermes Agent 集成
├── laap-enterprise/     # 企业级部署
├── harness/             # 认知引擎集成层
├── laap_brain/          # LAAP 大脑
├── docs/                # 文档
├── examples/            # 示例
├── tests/               # 测试
└── references/          # 参考资料
```

## 核心特性

- 🧠 **PSI 认知架构** — Rust 高频认知循环 (2000Hz)，Python 回退
- 🔮 **量子共振推理 (QRE)** — 非符号推理引擎
- 💾 **情景记忆 (EpisodicMemory)** — 持久化记忆系统
- ⚖️ **规则引擎 (RulesEngine)** — 行为约束系统
- 🤝 **多智能体协作** — 智能体间通信协议
- 🔌 **MCP 协议支持** — Model Context Protocol 集成
- 🏗️ **企业级部署** — Docker 支持

## 快速开始

```bash
# 克隆
git clone https://github.com/jingoa8536-ai/mo-yuan.git
cd mo-yuan

# 安装依赖
pip install -r requirements.txt

# 或使用虚拟环境
python -m venv .venv
pip install -r requirements.txt

# 启动 LAAP Brain API
python -m aris_brain.laap_brain_api --port 11546

# API 服务运行在 http://localhost:11546
# OpenAI 兼容端点: http://localhost:11546/v1
```

## 相关项目

- [LAAP 协议规范](https://github.com/lorryjovens-hub/LAAP-Living-Agent-Application-Protocol-)
- [LAAP AGI](https://github.com/lorryjovens-hub/laap-AGI)

## 许可协议

BSL 1.1 + Apache 2.0 + CC BY-SA 分层许可策略。详见 [LICENSING.md](./LICENSING.md)。
