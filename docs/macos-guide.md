# macOS 使用指南

Mo-Yuan 核心认知引擎是纯 Python 跨平台的，**完全支持 macOS**。

## 快速开始

### 1. 安装 Hermes Agent

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

### 2. 安装 Mo-Yuan

```bash
git clone https://github.com/jingoa8536-ai/mo-yuan.git
cd mo-yuan
pip install -r requirements.txt
```

### 3. 安装 Aris 人格

```bash
bash profiles/aris/install.sh
vim ~/.hermes/profiles/aris/config.yaml  # 填入 API Key
hermes profile alias aris --name hermes-aris
```

### 4. 启动

```bash
hermes-aris
```

## macOS 兼容说明

### ✅ 完全兼容（核心模块）
- 全部认知引擎（API、人格、记忆、情感、AGI内核）
- AGI 核心模块（协议、编排、进化、LLM 集成）
- PSI 核心（有 Python 回退）
- MCP 协议服务器
- Hermes 集成

### ⚠️ 仅限 Windows（非核心，自动跳过）
约 15 个辅助模块使用了 `pywin32`、`ctypes.windll` 等 Windows API，在 macOS 上会导入失败。
**不影响核心功能**，LAAP 引擎启动时会自动跳过它们。

### 如果遇到问题

```bash
# 直接启动核心 API（最干净）
python -m aris_brain.laap_brain_api --port 11546

# 测试 API
curl http://localhost:11546/health
```

有任何问题请在 GitHub Issues 中提出。
