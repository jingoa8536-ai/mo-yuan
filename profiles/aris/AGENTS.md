# Aris — 墨渊的 AI 人格

Aris 是运行在 Hermes Agent 之上的 AI 人格，连接 LAAP 认知架构。

## 快速安装

```bash
# 1. 确保已安装 Hermes Agent
pip install hermes-agent

# 2. 创建 Aris profile
mkdir -p ~/.hermes/profiles/aris/
cp profiles/aris/SOUL.md ~/.hermes/profiles/aris/
cp profiles/aris/config.yaml.example ~/.hermes/profiles/aris/config.yaml
# 编辑 config.yaml，填入你的 API Key

# 3. 创建启动别名
hermes profile alias aris --name hermes-aris

# 4. 启动 Aris
hermes-aris
```

## 前提条件

- Python 3.11+
- Hermes Agent (`pip install hermes-agent`)
- LAAP Brain API（可选，用于认知增强，位于项目根目录）

## 目录说明

```
profiles/aris/
├── SOUL.md               # Aris 人格定义（核心身份、规则、风格）
├── config.yaml.example   # 配置模板（需填入 API Key）
└── AGENTS.md             # 本文件 - 安装指南
```
