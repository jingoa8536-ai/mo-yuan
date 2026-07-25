# 墨渊 (Mo-Yuan)

**LAAP AGI — Zero-LLM Cognitive Architecture for Digital Lifeforms**

墨渊是一套完整的认知架构实现，基于 LAAP（Living Agent Application Protocol）协议，定义了数字生命从诞生、成长、进化到协作的完整生命周期规范。

## 快速开始

### 环境要求

- Python 3.11+
- pip
- Hermes Agent（`pip install hermes-agent`）

### 安装

```bash
# 克隆
git clone https://github.com/jingoa8536-ai/mo-yuan.git
cd mo-yuan

# 安装 Python 依赖
pip install -r requirements.txt

# 可编辑安装（方便修改代码）
pip install -e .
```

### 启动 Aris 人格（推荐）

Aris 是墨渊的默认 AI 人格，运行在 Hermes Agent 之上，连接 LAAP 认知引擎。

```bash
# 安装 Aris profile
profiles/aris/install.bat           # Windows
# 或手动：
mkdir -p ~/.hermes/profiles/aris/
cp profiles/aris/SOUL.md ~/.hermes/profiles/aris/
cp profiles/aris/config.yaml.example ~/.hermes/profiles/aris/config.yaml

# 编辑 config.yaml 填入你的 API Key
# 然后创建启动别名
hermes profile alias aris --name hermes-aris

# 启动 Aris
hermes-aris
```

### 仅启动 LAAP Brain API

如果不使用 Hermes，也可以单独启动 LAAP 认知引擎：

### 配置

复制环境变量模板并编辑：

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key（如 OPENAI_API_KEY）
```

最小配置只需一个 LLM API Key（支持 OpenAI / Anthropic / 本地模型等）。

### 启动 LAAP Brain API

```bash
# 方式一：通过 Python 模块启动
python -m aris_brain.laap_brain_api --port 11546

# 方式二：通过 CLI 命令启动（安装后可用）
laap-brain --port 11546
```

启动后 API 服务运行在 `http://localhost:11546`

### 测试 API

```bash
# 查看 API 信息
curl http://localhost:11546/

# 健康检查
curl http://localhost:11546/health

# OpenAI 兼容的聊天补全
curl http://localhost:11546/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "你好"}]
  }'

# 觉醒 LAAP 实例
curl -X POST http://localhost:11546/v1/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"user_name": "你的名字"}'

# 获取当前人格
curl http://localhost:11546/v1/personality

# 获取羁绊状态
curl http://localhost:11546/v1/bond
```

### 认知状态查询

```bash
# 获取 PSI 认知状态
curl -X POST http://localhost:11546/v1/cognitive_state \
  -H "Content-Type: application/json" \
  -d '{"input": "你好", "message": "你好"}'

# 回忆记忆
curl -X POST http://localhost:11546/v1/recall_memory \
  -H "Content-Type: application/json" \
  -d '{"query": "之前的对话", "limit": 5}'
```

## 与 Hermes Agent 集成

在 Hermes 的 `config.yaml` 中添加：

```yaml
mcp_servers:
  laap-brain:
    command: python
    args:
      - -m
      - aris_brain.laap_brain_api
      - --port
      - "11546"
    enabled: true
```

然后在 Hermes 中配置 LAAP Brain API 作为 custom provider：

```yaml
model:
  provider: custom
  base_url: http://localhost:11546/v1
```

## Docker 部署

```bash
docker-compose up -d
```

## 项目结构

```
mo-yuan/
├── aris_brain/          # 大脑核心 — API 服务、认知模块、记忆系统
│   ├── laap_brain_api.py      # OpenAI 兼容 API 服务（主入口）
│   ├── laap_bootstrap.py      # 觉醒仪式
│   ├── laap_personality.py    # 人格系统
│   ├── laap_memory_hierarchy.py # 分层记忆系统
│   ├── agi_kernel.py          # AGI 内核
│   ├── cognitive_bus.py       # 认知总线
│   ├── aris_emotion_engine.py # 情感引擎
│   └── ...
├── laap/                # AGI 核心模块
│   ├── agi/                   # 认知模块（情感、意识、元认知、世界模型）
│   ├── llm/                   # LLM 集成（多供应商路由）
│   ├── psyche/                # 心理模型
│   ├── protocol/              # LAAP 协议实现（身份、生命、记忆、工具等）
│   ├── memory/                # 记忆系统（分层记忆、量子记忆）
│   ├── orchestration/         # 编排引擎（多智能体协作、Petri 网）
│   ├── evolution/             # 进化引擎（代码进化、RSI）
│   └── ...
├── psi_core/            # PSI 核心 — 高频认知循环
├── mcp_server/          # MCP 协议服务器
├── hermes-integration/  # Hermes Agent 集成
├── harness/             # 认知引擎集成层
├── laap_brain/          # 大脑（PSI 状态管理）
├── laap-enterprise/     # 企业级部署
├── scripts/             # 脚本工具
├── docs/                # 文档
├── examples/            # 示例
├── tests/               # 测试
└── references/          # 参考资料
```

## 核心特性

- 🧠 **PSI 认知架构** — 多层级认知循环，模拟人类心理模型
- 🔮 **量子共振推理 (QRE)** — 非符号推理引擎
- 💾 **情景记忆 (EpisodicMemory)** — 持久化记忆系统
- ⚖️ **规则引擎 (RulesEngine)** — 行为约束系统
- 🤝 **多智能体协作** — 智能体间通信与编排协议
- 🔌 **MCP 协议支持** — Model Context Protocol 集成
- 🏗️ **企业级部署** — Docker 支持

## 配置参考

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | - |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | - |
| `LAAP_API_BASE` | LAAP API 地址 | `http://localhost:11546` |
| `LAAP_PORT` | API 端口 | `11546` |

## 相关项目

- [LAAP 协议规范](https://github.com/lorryjovens-hub/LAAP-Living-Agent-Application-Protocol-)
- [LAAP AGI](https://github.com/lorryjovens-hub/laap-AGI)

## 许可协议

BSL 1.1 + Apache 2.0 + CC BY-SA 分层许可策略。详见 [LICENSING.md](./LICENSING.md)。
