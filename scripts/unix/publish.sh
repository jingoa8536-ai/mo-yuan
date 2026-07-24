#!/bin/bash
# LAAP 发布脚本
# 用法: bash publish.sh [pypi|testpypi]

set -e

echo "🚀 LAAP v$(python -c 'from laap import __version__; print(__version__)') 发布中..."

# 清理旧构建
rm -rf dist/ build/ *.egg-info

# 构建
python -m build --sdist --wheel .
echo "✅ 构建完成"

# 上传
if [ "$1" = "testpypi" ]; then
    python -m twine upload --repository testpypi dist/*
    echo "✅ 已上传到 TestPyPI"
    echo "👉 安装测试: pip install -i https://test.pypi.org/simple/ laap"
else
    python -m twine upload dist/*
    echo "✅ 已上传到 PyPI"
    echo "👉 用户安装: pip install laap"
    echo "👉 uv安装: uv tool install laap"
fi
