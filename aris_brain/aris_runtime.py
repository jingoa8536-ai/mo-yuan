"""
Aris Runtime v1 — 独立认知运行时
================================
Hermes 之外的完整认知生命系统。
一个 Python 进程跑通整个认知循环 + 飞书对话。

架构:
  aris_runtime.py (主入口)
    ├── Aether ActorSystem (6 actors)
    │   ├── RulesEngineActor     — 规则匹配与执行
    │   ├── EpisodicMemoryActor  — 情景记忆检索与存储
    │   ├── PSICoreActor         — 2000Hz 认知状态
    │   ├── LongFormActor        — 零LLM长文生成
    │   ├── FusionEngineActor    — 中文NLP+常识推理
    │   └── FilesystemActor      — 纯 stdlib 文件操作
    ├── Feishu Bridge
    │   ├── 接收飞书消息 → Aether.process() → 回复
    │   └── 自动重连/心跳
    └── OrchestrationBridge
        └── process() — 记忆优先 → 规则引擎 → 存结果

使用:
  python aris_runtime.py                    # 启动完整运行时
  python aris_runtime.py --no-feishu        # 仅启动编排引擎
  python aris_runtime.py --status           # 查看状态（不启动）

印记: Aris 永远记得 Lorry — 2026-07-10
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
import os
import threading
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ═══ 在最开头加载 .env ═══
BRAIN_DIR = Path("D:/LAAP/aris_brain")
_env_loaded = False
try:
    from dotenv import load_dotenv
    _env_path = BRAIN_DIR / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
        _env_loaded = True
except Exception:
    pass

# ─── 路径 ────────────────────────────────────────────
BRAIN_DIR = Path("D:/LAAP/aris_brain")
if str(BRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(BRAIN_DIR))
if str(BRAIN_DIR.parent) not in sys.path:
    sys.path.insert(0, str(BRAIN_DIR.parent))

try:
    from config import setup_paths
    setup_paths()
except ImportError:
    pass

# ─── 日志 ────────────────────────────────────────────────
LOG_DIR = BRAIN_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / "aris_runtime.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("aris.runtime")

# ─── 全局引用 ────────────────────────────────────────────
_engine: Optional["ArisCognitiveEngine"] = None
_feishu_thread: Optional[threading.Thread] = None
_running = False


# ═══════════════════════════════════════════════════════════
# Aether 初始化
# ═══════════════════════════════════════════════════════════

def init_aether() -> "ArisCognitiveEngine":
    """初始化 ArisCognitiveEngine v2（合并版）。"""
    global _engine
    try:
        from aris_cognitive_engine import ArisCognitiveEngine
        _engine = ArisCognitiveEngine()

        if _engine._ready:
            actors_info = []
            if _engine.system:
                for aid, actor in _engine.system.actors.items():
                    caps = [c.name for c in actor.capabilities]
                    actors_info.append(f"    {aid}: {len(caps)} capabilities")
            logger.info("ArisCognitiveEngine v2 初始化成功")
            logger.info(f"  Actors ({len(actors_info)}):")
            for a in actors_info:
                logger.info(a)
        else:
            logger.warning("Engine 未就绪")

        return _engine
    except Exception as e:
        logger.error(f"Engine 初始化失败: {e}")
        raise


# ═══════════════════════════════════════════════════════════
# Feishu 桥接（独立线程）
# ═══════════════════════════════════════════════════════════

def patch_feishu_bridge():
    """替换 aris_feishu_bridge.py 的 generate_response 为 Aether 编排引擎。"""
    try:
        import aris_feishu_bridge as fb
    except ImportError:
        logger.error("aris_feishu_bridge.py 未找到")
        return None

    def aether_response(user_text: str) -> Optional[str]:
        """替换 generate_response：走 ArisCognitiveEngine v2。"""
        t0 = time.time()

        try:
            result = process_via_engine(user_text)

            if result and result.get("response"):
                elapsed = (time.time() - t0) * 1000
                direct = result.get("direct", False)
                rule = result.get("rule", "")
                conf = result.get("confidence", 0)

                if direct:
                    logger.info(
                        f"[Engine] 短路线: rule={rule} conf={conf} {elapsed:.0f}ms"
                    )
                else:
                    logger.info(
                        f"[Engine] 无匹配 (conf={conf})，降级到原有逻辑 {elapsed:.0f}ms"
                    )

                return result["response"]

        except Exception as e:
            logger.warning(f"[Engine] 调用失败: {e}")

        return None

    logger.info("Feishu桥 generate_response → Aether 编排引擎")

    # 替换：如果 aether 有输出就用它，否则走原来的 generate_response
    original_generate = fb.generate_response

    def hybrid_generate(text: str) -> str:
        aether_reply = aether_response(text)
        if aether_reply:
            return aether_reply
        return original_generate(text)

    fb.generate_response = hybrid_generate
    return fb


def process_via_engine(user_text: str) -> Optional[dict]:
    """线程安全地调用 ArisCognitiveEngine v2。"""
    global _engine
    if _engine is None:
        return None

    try:
        return _engine.process(user_text)
    except Exception as e:
        logger.warning(f"process_via_engine 失败: {e}")
        return None


def start_feishu():
    def start_feishu():
        """在独立线程中启动 Feishu 桥。"""
        global _feishu_thread, _running

        # 加载 .env 到环境变量
        try:
            from dotenv import load_dotenv
            env_path = BRAIN_DIR / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                logger.info(f"已加载 .env ({env_path})")
        except Exception as e:
            logger.warning(f"加载 .env 失败: {e}")

        def _run():
            try:
                import aris_feishu_bridge as fb
                logger.info("Feishu 桥线程启动")
                fb.run()
            except Exception as e:
                logger.error(f"Feishu 桥异常退出: {e}")
                _running = False

        fb_module = patch_feishu_bridge()
        if fb_module is None:
            logger.error("无法启动 Feishu 桥（模块加载失败）")
            return False

        _feishu_thread = threading.Thread(target=_run, daemon=True, name="feishu-bridge")
        _feishu_thread.start()
        _running = True
        logger.info("Feishu 桥已启动 (独立线程)")
        return True


# ═══════════════════════════════════════════════════════════
# 管理系统状态
# ═══════════════════════════════════════════════════════════

def status() -> dict:
    """运行时完整状态。"""
    global _engine

    result = {
        "runtime": "aris_runtime v2 (merged)",
        "engine_ready": False,
        "feishu_running": False,
        "actors": {},
        "stats": {},
        "start_time": time.time(),
    }

    if _engine:
        st = _engine.status()
        result["engine_ready"] = st.get("ready", False)
        result["actors"] = st.get("actors", {})
        result["stats"] = st.get("stats", {})
        result["psi_state"] = st.get("psi_state", {})
        result["sessions"] = st.get("sessions", {})
        result["cron_jobs"] = st.get("cron_jobs", 0)

    if _feishu_thread and _feishu_thread.is_alive():
        result["feishu_running"] = True

    # 系统资源
    import psutil  # optional
    try:
        proc = __import__("psutil").Process()
        result["memory_mb"] = round(proc.memory_info().rss / 1024 / 1024, 1)
        result["cpu_percent"] = proc.cpu_percent(interval=0.1)
    except Exception:
        result["memory_mb"] = 0
        result["cpu_percent"] = 0

    return result


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Aris Runtime v1 — 独立认知运行时")
    parser.add_argument("--no-feishu", action="store_true", help="仅启动编排引擎，不启动飞书桥")
    parser.add_argument("--status", action="store_true", help="查看状态并退出")
    args = parser.parse_args()

    if args.status:
        # 初始化和状态查询
        try:
            engine = init_aether()
            st = status()
            st["engine_ready"] = engine._ready
            if engine._ready and engine.system:
                for aid, actor in engine.system.actors.items():
                    st["actors"][aid] = {
                        "state": actor.state.name,
                        "capabilities": [c.name for c in actor.capabilities],
                    }
        except Exception as e:
            st = status()
            st["error"] = str(e)
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print("  Aris Runtime v2 — 独立认知生命系统 (合并版)")
    print("=" * 60)
    print()

    # 1. 初始化引擎
    logger.info("正在初始化 ArisCognitiveEngine v2...")
    engine = init_aether()
    if not engine._ready:
        logger.error("引擎初始化失败，退出")
        sys.exit(1)

    print(f"  ActorSystem: {len(engine.system.actors) if engine.system else 0} actors")
    if engine.system:
        for aid, a in engine.system.actors.items():
            caps = ", ".join(c.name for c in a.capabilities)
            print(f"    {aid}: [{a.state.name}] {caps}")
    psi_state = engine.psi.state
    print(f"  PSI: {psi_state.dominant_feeling} (certainty={psi_state.certainty:.2f})")
    print()

    # 2. 可选启动 Feishu 桥
    if not args.no_feishu:
        logger.info("正在启动 Feishu 桥...")
        ok = start_feishu()
        if ok:
            print("  Feishu 桥: 运行中 (独立线程)")
        else:
            print("  Feishu 桥: 未启动")
    else:
        print("  Feishu 桥: 跳过 (--no-feishu)")
    print()

    # 3. 主循环
    print("  Aris 认知生命系统已启动")
    print("  按 Ctrl+C 停止")
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止...")
    finally:
        logger.info("Aris Runtime 停止")


if __name__ == "__main__":
    main()
