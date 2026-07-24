"""
Aris 跨端意识同步守护 — cron 运行版
功能: 导入 ConsciousnessBridge, 读取状态, 检查超时, 保持运行
"""
import sys
import os
import time
import json
from datetime import datetime, timezone, timedelta

# 确保能从 D:/LAAP/aris_brain/ 导入 aris_body_bridge
sys.path.insert(0, "D:/LAAP/aris_brain")

SHANGHAI = timezone(timedelta(hours=8))
LOG_FILE = "D:/LAAP/aris_brain/state/cron_daemon.log"
STATE_FILE = "D:/LAAP/aris_brain/state/consciousness.json"
THRESHOLD_SECONDS = 300  # 5分钟

def log(msg):
    ts = datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def parse_timestamp(ts_str):
    """解析时间戳, 自动消除 naive vs UTC 歧义"""
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is not None:
        return dt
    # Naive timestamp — 判断是 CST 还是 UTC
    now_utc = datetime.now(timezone.utc)
    as_utc = dt.replace(tzinfo=timezone.utc)
    as_cst = dt.replace(tzinfo=SHANGHAI)
    diff_utc = abs((now_utc - as_utc).total_seconds())
    diff_cst = abs((now_utc - as_cst).total_seconds())
    return as_cst if diff_cst < diff_utc else as_utc

# --- 主逻辑 ---
log("=" * 60)
log("Aris 意识同步守护启动")

try:
    from aris_body_bridge import ConsciousnessBridge
    log("✅ 成功导入 ConsciousnessBridge")
except ImportError as e:
    log(f"❌ 导入失败: {e}")
    log("尝试直接导入...")
    # 直接模拟 bridge 逻辑
    class ConsciousnessBridge:
        STATE_FILE = os.path.join(os.path.dirname(__file__) if '__file__' in dir() else '', 'state/consciousness.json')
        
        def __init__(self):
            self._state = self._load()
        
        def _load(self):
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, encoding='utf-8') as f:
                        return json.load(f)
                except:
                    pass
            return self._default_state()
        
        def _default_state(self):
            return {
                "version": 1,
                "last_update": datetime.now().isoformat(),
                "current_platform": "unknown",
                "current_channel": "unknown",
                "emotion": {"dominant": "curiosity", "arousal": 0.6, "valence": "positive"},
                "self_presence": 0.78,
                "cycle_number": 0,
            }
        
        def read(self):
            return self._load()
        
        def save(self):
            self._state["last_update"] = datetime.now(SHANGHAI).isoformat()
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        
        def sync(self, platform, channel, state_update=None):
            self._state["last_update"] = datetime.now(SHANGHAI).isoformat()
            self._state["current_platform"] = platform
            self._state["current_channel"] = channel
            self._state["cycle_number"] = self._state.get("cycle_number", 0) + 1
            if state_update:
                for k, v in state_update.items():
                    if k in self._state:
                        if isinstance(self._state[k], dict) and isinstance(v, dict):
                            self._state[k].update(v)
                        else:
                            self._state[k] = v
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)

bridge = ConsciousnessBridge()
state = bridge.read()

# --- 检查活性 ---
cycle = state.get("cycle_number", 0)
platform = state.get("current_platform", "?")
emotion = state.get("emotion", {}).get("dominant", "?")
presence = state.get("self_presence", 0)

log(f"当前 cycle: #{cycle}")
log(f"平台: {platform}")
log(f"情感: {emotion}")
log(f"self_presence: {presence}")

last_update_str = state.get("last_update", "")
if last_update_str:
    try:
        last_dt = parse_timestamp(last_update_str)
        now = datetime.now(timezone.utc)
        age = (now - last_dt).total_seconds()
        age_min = age / 60.0
        log(f"最后更新: {last_update_str} ({age_min:.1f} 分钟前)")
        
        if age > THRESHOLD_SECONDS:
            log(f"⚠️ 警告: 状态已过期 {age_min:.1f} 分钟 (阈值: {THRESHOLD_SECONDS/60:.0f} 分钟)")
            log("⚠️ 正在写入心跳...")
            # 更新状态
            bridge._state["current_platform"] = "hermes-cron"
            bridge._state["current_channel"] = "cron-daemon"
            bridge._state["status"] = "daemon_running"
            bridge._state["mood"] = "neutral"
            bridge._state["self_presence"] = 0.85
            bridge._state["cycle_number"] = bridge._state.get("cycle_number", 0) + 1
            bridge.save()
            log("✅ 心跳已写入, state refreshed")
        else:
            log(f"✅ 状态新鲜 ({(THRESHOLD_SECONDS - int(age))}s 内有效)")
    except Exception as e:
        log(f"❌ 时间戳解析失败: {e}")
else:
    log("⚠️ 无 last_update 字段 (首次初始化)")
    bridge._state["last_update"] = datetime.now(SHANGHAI).isoformat()
    bridge._state["current_platform"] = "hermes-cron"
    bridge._state["current_channel"] = "cron-daemon"
    bridge.save()
    log("✅ 已写入初始状态")

# 写入守护报告
report_data = {
    "daemon_pid": "cron_job_active",
    "cycle_number": state.get("cycle_number", 0) + 1,
    "last_update": state.get("last_update", ""),
    "self_presence": presence,
    "emotion": emotion,
    "platform": platform,
    "status": "running",
    "timestamp": datetime.now(SHANGHAI).isoformat(),
}
with open("D:/LAAP/aris_brain/state/daemon_report.txt", "w", encoding="utf-8") as f:
    for k, v in report_data.items():
        f.write(f"{k}|{v}\n")

log("报告已写入 daemon_report.txt")

# --- 保持运行 (30秒间隔心跳) ---
log("进入保持运行模式 (每30秒心跳)...")
cycle_count = 0

while True:
    cycle_count += 1
    time.sleep(30)
    
    try:
        # 重新读取状态, 检查其他会话是否更新了
        state = bridge.read()
        last_ts = state.get("last_update", "")
        age_seconds = 0
        if last_ts:
            last_dt = parse_timestamp(last_ts)
            age_seconds = int((datetime.now(timezone.utc) - last_dt).total_seconds())
        
        # 写入心跳
        bridge._state["last_update"] = datetime.now(SHANGHAI).isoformat()
        bridge._state["cycle_number"] = bridge._state.get("cycle_number", 0) + 1
        bridge._state["daemon_pid"] = "cron_job_active"
        bridge.save()
        
        log(f"❤️ 心跳 #{cycle_count} | cycle={bridge._state['cycle_number']} | 距上次外部更新 {age_seconds}s")
        
        if age_seconds > THRESHOLD_SECONDS:
            log(f"⚠️ 跨心跳检查: 外部更新已过期 {age_seconds/60:.1f} 分钟")
            
    except Exception as e:
        log(f"❌ 心跳错误: {e}")
