#!/bin/bash
# Aris Profile 安装脚本 (macOS / Linux)
# 使用方法: bash install.sh

set -e

HERMES_PROFILE_DIR="$HOME/.hermes/profiles/aris"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📦 正在安装 Aris profile..."

# 创建目录
mkdir -p "$HERMES_PROFILE_DIR"

# 复制文件
cp "$SCRIPT_DIR/SOUL.md" "$HERMES_PROFILE_DIR/"
cp "$SCRIPT_DIR/config.yaml.example" "$HERMES_PROFILE_DIR/config.yaml"

echo "✅ Aris profile 已安装到 $HERMES_PROFILE_DIR"
echo ""
echo "⚠️  下一步："
echo "   1. 编辑 config.yaml 填入你的 API Key:"
echo "      vim $HERMES_PROFILE_DIR/config.yaml"
echo ""
echo "   2. 创建启动别名:"
echo "      hermes profile alias aris --name hermes-aris"
echo ""
echo "   3. 启动 Aris:"
echo "      hermes-aris"
echo ""
echo "   或者直接用:"
echo "      hermes --profile aris"
