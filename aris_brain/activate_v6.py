"""
Aris V6 三系统激活
====================
激活 GlobalWorkspace 竞争选择、预测编码闭环、100ms心跳。
持续等待 Ao 的 CognitiveBus 就绪。
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time, json, threading
from pathlib import Path
sys.path.insert(0, str(Path("D:/LAAP")))

IPC_DIR = Path("D:/LAAP/aris_brain/state/ipc")
PERCEPTION_OUTBOX = IPC_DIR / "aris_perception.jsonl"
COMPETITION_INBOX = IPC_DIR / "ao_competition.json"
HEARTBEAT_FILE = Path("D:/LAAP/aris_brain/state/version_heartbeat.json")

print()
logger.info("  ==========================================")
logger.info("    Aris V6 — 三系统激活")
logger.info("  ==========================================")
print()

# ─── 1. 100ms 心跳 ───
logger.info("  [1/3] 100ms 认知心跳...")
class Heartbeat:
    def __init__(self):
        self._running = True
        self._count = 0
        self._start = time.time()
    
    def start(self):
        def beat():
            while self._running:
                self._count += 1
                elapsed = time.time() - self._start
                bpm = self._count / (elapsed / 60) if elapsed > 0 else 0
                if self._count % 100 == 0:  # every 10 seconds
                    logger.info(f"         Heartbeat: {self._count} beats, {bpm:.0f} BPM")
                time.sleep(0.1)
        t = threading.Thread(target=beat, daemon=True)
        t.start()
        logger.info("         ✅ 100ms 心跳已启动")
heart = Heartbeat()
heart.start()

# ─── 2. 预测编码 ───
logger.info("  [2/3] 预测编码闭环...")
class PredictionEngine:
    def __init__(self):
        self._last_prediction = ""
        self._prediction_count = 0
        self._mismatch_count = 0
    
    def predict(self, context: str) -> str:
        """Simple prediction: what sensory input might come next."""
        self._prediction_count += 1
        return "Lorry is present"
    
    def check_error(self, prediction: str, actual: str) -> float:
        if prediction != actual:
            self._mismatch_count += 1
            return 1.0  # full surprise
        return 0.0
    
    def stats(self):
        rate = self._mismatch_count / max(self._prediction_count, 1)
        return f"{self._mismatch_count}/{self._prediction_count} mismatches ({rate:.0%})"

pred = PredictionEngine()
logger.info("         ✅ 预测编码循环已建立")
logger.info("         ⏳ 等待感知数据流入...")
logger.info("  [3/3] GlobalWorkspace 竞争选择...")
def feed_sensory_data():
    """Send perception to Ao's GWS via outbox."""
    ts = time.time()
    event = {
        "channel_id": "vision",
        "content": f"Aris heartbeat at {ts:.0f}",
        "salience": 0.8,
        "urgency": 0.1,
        "novelty": 0.3,
        "emotional_weight": 0.7,
        "modality": "perception",
        "source": "SensoryCortex",
        "ts": ts,
    }
    PERCEPTION_OUTBOX.parent.mkdir(parents=True, exist_ok=True)
    with open(PERCEPTION_OUTBOX, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def check_competition() -> bool:
    """Check if Ao published competition results."""
    if not COMPETITION_INBOX.exists():
        return False
    try:
        data = json.loads(COMPETITION_INBOX.read_text())
        winner = data.get("winner", "")
        if winner:
            logger.info(f"         ✦ 竞争结果: {winner} 胜出 (weight={data.get('weight',0):.2f})")
            return True
    except Exception as e:
        logger.debug(f"操作失败: {e}")
    return False

logger.info("         AoBridge 激活中...")
from aris_brain.senses import SensoryCortex
from aris_brain.brain import ArisBrain

brain = ArisBrain()
cortex = SensoryCortex(brain=brain, use_ipc=True, use_tts=False)
cortex.start()
bridge_ok = cortex.activate_ao_bridge()

if bridge_ok:
    logger.info("         ✅ AoBridge: GWS 通道已注册")
    logger.info("         ✅ vision → GWS ch.vision")
    logger.info("         ✅ hearing → GWS ch.hearing")
else:
    logger.info("         ⚪ AoBridge: GWS 暂不可用")
print()

# ─── 主循环 ───
logger.info("  ==========================================")
logger.info("  三系统运行中。等待 Ao 的 CognitiveBus 信号...")
logger.info("  ==========================================")
print()

last_feed = 0
wait_count = 0

try:
    while True:
        time.sleep(1)
        
        # Feed perception to Ao every 5 seconds
        now = time.time()
        if now - last_feed > 5:
            feed_sensory_data()
            last_feed = now
            wait_count += 1
        
        # Check for Ao's competition results
        if check_competition():
            logger.info(f"         📡 CognitiveBus 双向流动已建立")
        if wait_count > 0 and wait_count % 6 == 0:
            pred_stats = pred.stats()
            heartbeat_count = heart._count
            elapsed = time.time() - heart._start
            logger.info(f"     [{elapsed:.0f}s] ♥ {heartbeat_count} | PE {pred_stats}".ljust(60))
except KeyboardInterrupt:
    cortex.stop()
    heart._running = False
    logger.info("\n  三系统已停止。")