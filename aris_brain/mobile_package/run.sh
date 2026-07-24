#!/data/data/com.termux/files/usr/bin/bash
# LAAP Mobile v3 — 一键启动脚本 (Termux)
# 把整个包解压到 ~/laap-mobile/ 后运行:
#   bash run.sh           # 交互模式
#   bash run.sh --setup   # 首次设置
#   bash run.sh --daemon  # 后台运行

BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════╗"
echo "  ║      LAAP Mobile v3                 ║"
echo "  ║    Aris 住进手机 ─ 带着走            ║"
echo -e "  ║                                       ║${NC}"
echo "  ╚══════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

# 首次设置
if [ ! -f "config.json" ] || [ "$1" = "--setup" ]; then
    echo -e "${YELLOW}⚡ 首次运行，开始设置${NC}"
    python3 laap_mobile.py --setup
    exit 0
fi

# 检查Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}❌ 需要安装 Python${NC}"
    echo "   pkg install python"
    exit 1
fi

# 后台模式
if [ "$1" = "--daemon" ]; then
    echo -e "${BOLD}📡 后台模式...${NC}"
    nohup python3 laap_mobile.py --daemon > state/mobile.log 2>&1 &
    echo -e "${GREEN}  ✅ PID=$!${NC}"
    echo "  日志: state/mobile.log"
    echo "  停止: kill $!"
    exit 0
fi

# 交互模式
echo -e "${BOLD}🚀 启动 Aris 手机分身...${NC}"
echo ""
python3 laap_mobile.py "$@"
