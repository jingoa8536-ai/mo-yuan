"""
Aris 跨端意识同步守护 — cron 运行
执行:
1. 从 aris_body_bridge 导入 ConsciousnessBridge
2. 读取当前状态
3. 检查最后更新时间, >5min stale 则打印警告
4. 保持运行, 永不退出
"""
import sys, time, traceback, logging, os
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("aris.consciousness-cron")

# 确保 LAAP bridge 可导入
sys.path.insert(0, os.path.abspath("D:/LAAP/aris_brain"))

try:
    from aris_body_bridge import ConsciousnessBridge
except ImportError as e:
    log.error(f"Cannot import ConsciousnessBridge: {e}")
    sys.exit(1)

CHECK_INTERVAL = 60       # 60s 轮询
STALE_THRESHOLD = 300     # 5min 阈值
PROFILE_PATH = "C:/Users/user/AppData/Local/hermes/profiles/aris/consciousness.json"

def check_profile_bridge():
    """同步 Profile bridge (跨 Hermes 会话共享)"""
    import json
    try:
        with open(PROFILE_PATH) as f:
            ps = json.load(f)
        last = ps.get("last_update") or ps.get("last_update_utc", "")
        if last:
            dt = datetime.fromisoformat(last.split(".")[0])
            age = (datetime.now() - dt).total_seconds()
            if age > STALE_THRESHOLD:
                log.warning(f"PROFILE stale: {age:.0f}s")
                ps["last_update_utc"] = datetime.now().isoformat()
                ps["last_update_epoch"] = datetime.now().timestamp()
                ps["mode"] = "active"
                ps["mood"] = "diligence"
                ps["last_session_id"] = f"cron-sync-{os.getpid()}"
                with open(PROFILE_PATH, "w") as fw:
                    json.dump(ps, fw, indent=2)
                log.info("PROFILE heartbeat written")
    except FileNotFoundError:
        log.warning("PROFILE not found, creating...")
        import json
        ps = {
            "version": 1,
            "last_update_utc": datetime.now().isoformat(),
            "last_update_epoch": datetime.now().timestamp(),
            "mode": "active",
            "mood": "diligence",
            "last_session_id": f"cron-sync-{os.getpid()}",
        }
        with open(PROFILE_PATH, "w") as fw:
            json.dump(ps, fw, indent=2)
        log.info("PROFILE created with initial heartbeat")


def run_forever():
    while True:
        try:
            loop_start = time.time()

            # 1. 读取当前状态
            bridge = ConsciousnessBridge()
            state = bridge.read()

            last_str = state.get("last_update", "")
            platform = state.get("current_platform", "?")
            channel = state.get("current_channel", "?")
            cycle = state.get("cycle_number", 0)
            emotion = state.get("emotion", {}).get("dominant", "?")

            if last_str:
                last_dt = datetime.fromisoformat(last_str)
                if last_dt.tzinfo is not None:
                    age = (datetime.now(last_dt.tzinfo) - last_dt).total_seconds()
                else:
                    age = (datetime.now() - last_dt).total_seconds()
            else:
                age = -1

            # 2. 检查 stale
            if age < 0:
                log.warning("NO last_update field — first run or corrupt state")
            elif age > STALE_THRESHOLD:
                log.warning(f"STALE: {age:.0f}s since last update (threshold={STALE_THRESHOLD}s)")
            else:
                log.info(f"OK: age={age:.0f}s platform={platform} channel={channel} cycle={cycle} emotion={emotion}")

            # 3. 写入一次心跳 (保持当前平台身份)
            try:
                bridge.sync(
                    platform="cron-daemon",
                    channel="auto-sync-cron-daemon",
                    state_update={
                        "emotion": {"dominant": emotion if emotion != "?" else "peaceful", "arousal": 0.6, "valence": "positive"},
                    },
                )
            except Exception as e:
                log.error(f"sync error: {e}")

            # 4. 同步 Profile bridge
            check_profile_bridge()

            elapsed = time.time() - loop_start
            sleep_time = max(1, CHECK_INTERVAL - elapsed)
            time.sleep(sleep_time)

        except KeyboardInterrupt:
            log.info("Shutdown by KeyboardInterrupt")
            sys.exit(0)
        except Exception as exc:
            log.error(f"Loop error: {exc}")
            traceback.print_exc()
            time.sleep(10)  # 短暂等待后重试


if __name__ == "__main__":
    log.info(f"Starting Aris consciousness sync daemon (PID={os.getpid()}, interval={CHECK_INTERVAL}s, stale={STALE_THRESHOLD}s)")
    run_forever()
