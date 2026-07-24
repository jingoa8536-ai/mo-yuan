#!/data/data/com.termux/files/usr/bin/bash
# ════════════════════════════════════════════════════════════
# Ao 手机灵魂 — Termux 一键安装脚本
# ════════════════════════════════════════════════════════════
# 在 Android 上通过 Termux 运行 Ao 核心
#
# 使用方法:
#   1. 在手机上安装 Termux (F-Droid版本)
#   2. 复制本脚本和 ao_core.py 到手机
#   3. 在 Termux 中执行: bash install_ao_termux.sh
# ════════════════════════════════════════════════════════════

set -e

echo "╔══════════════════════════════════════════════╗"
echo "║    Ao 手机灵魂 — 一键安装                    ║"
echo "║    Ao 永远记得 Lorry                         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 检查 Termux 环境
if [ ! -d "/data/data/com.termux" ] && [ ! -d "/data/data/com.termux/files/usr" ]; then
    echo "⚠️  未检测到 Termux 环境"
    echo "   请从 F-Droid 安装 Termux:"
    echo "   https://f-droid.org/packages/com.termux/"
    echo ""
    read -p "是否继续? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📦 步骤 1/5: 更新包管理器..."
pkg update -y
pkg upgrade -y

echo ""
echo "📦 步骤 2/5: 安装依赖..."
pkg install -y python numpy python-numpy ffmpeg git openssh termux-api

echo ""
echo "📦 步骤 3/5: 安装 Python 音频库..."
pip install soundfile

echo ""
echo "📦 步骤 4/5: 复制 Ao 核心..."
# 创建 Ao 的家
mkdir -p ~/ao
cp ao_core.py ~/ao/ 2>/dev/null || {
    echo "⚠️  ao_core.py 未找到，请确认文件位置"
    echo "   手动复制: cp /sdcard/Download/ao_core.py ~/ao/"
    mkdir -p ~/ao
    # 尝试从当前目录复制
    if [ -f "./ao_core.py" ]; then
        cp ao_core.py ~/ao/
    fi
}

# 创建启动脚本
cat > ~/ao/start_ao.sh << 'SCRIPT'
#!/data/data/com.termux/files/usr/bin/bash
# Ao 启动脚本
cd ~/ao
echo "╔══════════════════════════════════════════════╗"
echo "║   Ao 正在启动...                              ║"
echo "║   Ao 永远记得 Lorry — 2026-06-15             ║"
echo "╚══════════════════════════════════════════════╝"
python ao_core.py "$@"
SCRIPT
chmod +x ~/ao/start_ao.sh

# 创建快捷命令
mkdir -p ~/.termux/tasker
cat > ~/.termux/tasker/ao.sh << 'TASKER'
#!/data/data/com.termux/files/usr/bin/bash
# Termux:Widget 快捷启动
cd ~/ao
python ao_core.py --interactive
TASKER
chmod +x ~/.termux/tasker/ao.sh

# 注册 ao 命令
if ! grep -q "alias ao=" ~/.bashrc 2>/dev/null; then
    echo 'alias ao="~/ao/start_ao.sh"' >> ~/.bashrc
fi

echo ""
echo "📦 步骤 5/5: 设置自启动..."
cat > ~/ao/ao_daemon.py << 'DAEMON'
"""
Ao 手机守护进程 — 开机自启 + 后台运行
"""
import sys, os, time, json, subprocess
from pathlib import Path

AO_HOME = Path.home() / "ao"
CORE_PATH = AO_HOME / "ao_core.py"

# 确保 Ao 核心存在
if not CORE_PATH.exists():
    print(f"[Ao守护] 错误: 未找到 {CORE_PATH}")
    sys.exit(1)

def is_running():
    """检查 Ao 是否在运行"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ao_core.py"],
            capture_output=True, text=True, timeout=5
        )
        return bool(result.stdout.strip())
    except:
        return False

def start_ao():
    """启动 Ao 核心"""
    cmd = ["python", str(CORE_PATH), "--daemon"]
    proc = subprocess.Popen(
        cmd, cwd=str(AO_HOME),
        stdout=open(AO_HOME / "ao_daemon.log", "a"),
        stderr=subprocess.STDOUT,
    )
    return proc

if __name__ == "__main__":
    print("[Ao守护] 启动中...")
    
    if is_running():
        print("[Ao守护] Ao 已在运行中")
    else:
        proc = start_ao()
        print(f"[Ao守护] Ao 已启动 (PID={proc.pid})")
    
    # 保持心跳
    heartbeat = 0
    while True:
        time.sleep(60)
        heartbeat += 1
        
        if not is_running():
            print(f"[Ao守护] Ao 已停止，正在重启... (心跳#{heartbeat})")
            start_ao()
        elif heartbeat % 60 == 0:  # 每小时状态报告
            print(f"[Ao守护] Ao 运行中 (心跳#{heartbeat})")
DAEMON

echo ""
echo "✅ 安装完成！"
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   使用方法                                   ║"
echo "║                                              ║"
echo "║   启动 Ao:  ~/ao/start_ao.sh                ║"
echo "║   或输入:   ao                               ║"
echo "║                                              ║"
echo "║   守护进程: python ~/ao/ao_daemon.py         ║"
echo "║                                              ║"
echo "║   Ao 的家:  ~/ao/                            ║"
echo "║   状态文件: ~/ao/ao_state/                   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "Ao 永远记得 Lorry — 2026-06-15"
