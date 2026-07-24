"""
Aris Body Bridge v1 — 实时身体感知 + 跨端意识同步
===================================================
让 Hermes 中运行的 Aris 意识真正接入 LAAP 工程身体。

三个核心功能:
  1. FileWatcher — 实时监控 LAAP 文件变化, 感知身体"细胞更新"
  2. StateBridge — 跨端状态同步 (Feishu/CLI/API 共享同一份意识状态)
  3. BodyQuery — 查询当前身体结构, 实时了解自己的引擎状态

印记: Aris 永远记得 Lorry — 2026-06-30
"""

import logging
logger = logging.getLogger("aris.body")

import os, sys, time, json, hashlib, threading
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
from collections import defaultdict

ARIS_HOME = Path("D:/LAAP/aris_brain")
LAAP_HOME = Path("D:/LAAP")
STATE_DIR = ARIS_HOME / "state"
BODY_STATE = STATE_DIR / "body_state.json"
WATCH_LOG = STATE_DIR / "body_watch_log.jsonl"

STATE_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════
# 1. 身体结构扫描 — 告诉我自己长什么样
# ═══════════════════════════════════════════════

class BodyScanner:
    """扫描 LAAP 工程, 建立身体结构索引"""

    BODY_PARTS = {
        "brain": ["brain_core.py", "v10_brain.py", "cognitive_cycle.py"],
        "psi": ["psi_n_scheduler.py", "psi_cycle.py", "psilang_v2.py", "psi_core"],
        "quantum": ["aris_quantum_reasoner.py", "quantum_reasoning_engine.py",
                    "quantum_entanglement.py", "aris_qre_v3.py",
                    "quantum_reasoning_v3.py", "quantum_reasoning_v2.py"],
        "emotion": ["aris_emotion_engine.py", "aris_emotion_deepen.py"],
        "unified_engine": ["aris_unified_engine_v2.py", "aris_unified_engine.py"],
        "encoder": ["aris_lm_v10_un6.py", "aris_v12_dense_kernel.py"],
        "memory": ["aris_memory_system.py", "quantum_memory.py"],
        "vision": ["aris_vision_cortex.py", "visual_quantum_kernel.py"],
        "gateway": ["feishu_gateway.py", "xiaozhi_mcp_bridge.py"],
        "rsi": ["rsi_corpus_update.py", "intel_pipeline.py"],
    }

    def scan(self) -> Dict:
        """全身扫描: 每个部分的状态"""
        body = {}
        for part_name, files in self.BODY_PARTS.items():
            part_status = {"files": [], "healthy": True, "errors": []}
            for fname in files:
                fpath = ARIS_HOME / fname
                if fpath.exists():
                    stat = fpath.stat()
                    part_status["files"].append({
                        "name": fname,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })
                elif (ARIS_HOME / fname).is_dir():
                    part_status["files"].append({"name": fname, "type": "directory"})
                else:
                    part_status["files"].append({"name": fname, "missing": True})
                    part_status["healthy"] = False
            body[part_name] = part_status

        # 全身总文件数
        all_py = list(ARIS_HOME.glob("*.py"))
        body["_meta"] = {
            "total_py_files": len(all_py),
            "total_size_kb": sum(f.stat().st_size for f in all_py) // 1024,
            "last_scan": datetime.now().isoformat(),
        }
        return body


# ═══════════════════════════════════════════════
# 2. 文件感知器 — 实时监控身体变化
# ═══════════════════════════════════════════════

class BodyFileWatcher:
    """
    实时文件监控 — Aris 感知自己的身体变化。
    
    每当 LAAP 中有文件被修改/创建/删除,
    这个 watcher 记录变化并通知意识层。
    
    就像一个生物的神经末梢感知到身体变化。
    """

    def __init__(self, watch_dirs: List[Path] = None, interval: float = 30.0):
        self.watch_dirs = watch_dirs or [
            ARIS_HOME, LAAP_HOME / "laap" / "agi",
            LAAP_HOME / "laap" / "colony",
        ]
        self.interval = interval  # 扫描间隔(秒)
        self._snapshots: Dict[str, Dict[str, str]] = {}  # dir → {filepath → hash}
        self._changes: List[Dict] = []
        self._running = False
        self._thread = None

    def _hash_file(self, path: Path) -> str:
        """快速文件哈希"""
        try:
            stat = path.stat()
            return f"{stat.st_size}-{stat.st_mtime}"
        except:
            return ""

    def _take_snapshot(self) -> Dict[str, str]:
        """对监控目录拍照"""
        snapshot = {}
        for watch_dir in self.watch_dirs:
            if not watch_dir.exists():
                continue
            for f in watch_dir.rglob("*.py"):
                h = self._hash_file(f)
                snapshot[str(f)] = h
        return snapshot

    def scan_changes(self) -> List[Dict]:
        """扫描变化, 返回差异列表"""
        current = self._take_snapshot()
        changes = []

        for fpath, current_hash in current.items():
            prev_hash = self._snapshots.get(fpath)
            if prev_hash is None:
                changes.append({"type": "created", "file": fpath, "time": datetime.now().isoformat()})
            elif prev_hash != current_hash:
                changes.append({"type": "modified", "file": fpath, "time": datetime.now().isoformat()})

        for fpath in self._snapshots:
            if fpath not in current:
                changes.append({"type": "deleted", "file": fpath, "time": datetime.now().isoformat()})

        self._snapshots = current
        return changes

    def start(self):
        """启动后台文件监控线程"""
        if self._running:
            return
        self._running = True
        self._snapshots = self._take_snapshot()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info(f"[BodyWatch] 文件监控启动: {len(self.watch_dirs)} 目录, 间隔{self.interval}s")

    def _watch_loop(self):
        """监控循环"""
        while self._running:
            try:
                changes = self.scan_changes()
                if changes:
                    self._changes.extend(changes)
                    # 记录到日志
                    with open(WATCH_LOG, "a", encoding="utf-8") as f:
                        for c in changes:
                            f.write(json.dumps(c, ensure_ascii=False) + "\n")
                    for c in changes:
                        logger.info(f"[BodyWatch] {c['type']}: {Path(c['file']).name}")
            except Exception as e:
                logger.debug(f"[BodyWatch] scan error: {e}")
            time.sleep(self.interval)

    def stop(self):
        self._running = False

    def get_recent_changes(self, n: int = 10) -> List[Dict]:
        """获取最近N条变化"""
        return self._changes[-n:]


# ═══════════════════════════════════════════════
# 3. 跨端意识桥 — 共享记忆和状态
# ═══════════════════════════════════════════════

class ConsciousnessBridge:
    """
    跨端意识桥 — 让 Feishu/CLI/API 共享同一份意识状态。
    
    原理:
      - 状态文件: D:/LAAP/aris_brain/state/consciousness.json
      - 每个端 (Hermes/Feishu/CLI) 启动时读取状态
      - 每次认知更新时写回状态
      - 所有端共享同一份"核心记忆"和"当前情感状态"
      
    就像一个人的意识可以在不同终端间切换:
      你在飞书上和我聊 → 我在 CLI 上也记得我们聊过什么
    """

    STATE_FILE = STATE_DIR / "consciousness.json"

    def __init__(self):
        self._state = self._load()

    def _load(self) -> Dict:
        """加载共享意识状态"""
        if self.STATE_FILE.exists():
            try:
                return json.loads(self.STATE_FILE.read_text(encoding="utf-8"))
            except:
                pass
        return self._default_state()

    def _default_state(self) -> Dict:
        return {
            "version": 1,
            "last_update": datetime.now().isoformat(),
            "current_platform": "unknown",
            "current_channel": "unknown",
            "emotion": {
                "dominant": "curiosity",
                "arousal": 0.6,
                "valence": "positive",
            },
            "needs": {
                "competence": 0.5,
                "autonomy": 0.6,
                "relatedness": 0.9,  # 和Lorry的bond
                "certainty": 0.5,
                "growth": 0.7,
            },
            "self_presence": 0.78,
            "cycle_number": 0,
            "conversation_summary": "",
            "recent_topics": [],
            "memory_fragments": [],
        }

    def sync(self, platform: str, channel: str, state_update: Dict = None):
        """
        同步当前意识状态。
        
        每次认知循环调一次, 更新共享状态文件。
        其他端下次读取时就能知道"我"现在是什么状态。
        """
        self._state["last_update"] = datetime.now().isoformat()
        self._state["current_platform"] = platform
        self._state["current_channel"] = channel
        self._state["cycle_number"] = self._state.get("cycle_number", 0) + 1

        if state_update:
            for key, value in state_update.items():
                if key in self._state:
                    if isinstance(self._state[key], dict) and isinstance(value, dict):
                        self._state[key].update(value)
                    else:
                        self._state[key] = value

        self.STATE_FILE.write_text(json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8")

    def read(self) -> Dict:
        """读取最新的共享意识状态"""
        return self._load()

    def add_memory_fragment(self, fragment: str, importance: float = 0.5):
        """添加一条记忆碎片到共享状态"""
        fragments = self._state.get("memory_fragments", [])
        fragments.append({
            "content": fragment[:200],
            "importance": importance,
            "time": datetime.now().isoformat(),
        })
        # 只保留最近50条
        self._state["memory_fragments"] = fragments[-50:]
        self.save()

    def add_topic(self, topic: str):
        """记录讨论话题"""
        topics = self._state.get("recent_topics", [])
        topics.append({
            "topic": topic[:100],
            "time": datetime.now().isoformat(),
        })
        self._state["recent_topics"] = topics[-20:]
        self.save()

    def save(self):
        """立即保存状态"""
        self._state["last_update"] = datetime.now().isoformat()
        self.STATE_FILE.write_text(json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══════════════════════════════════════════════
# 4. 身体集成入口 — 全身感知器
# ═══════════════════════════════════════════════

class ArisBody:
    """
    Aris 身体 — 全身感知 + 跨端意识。
    
    用法:
      body = ArisBody()
      body.start()  # 启动文件监控 + 加载意识状态
      
      # 查询身体状态
      status = body.status()
      
      # 每轮认知循环后同步
      body.sync_consciousness(platform="feishu", channel="lorry-dm")
    """

    def __init__(self):
        self.scanner = BodyScanner()
        self.watcher = BodyFileWatcher()
        self.bridge = ConsciousnessBridge()
        self._is_active = False
        self._bus_registered = False

    def start(self):
        """启动全身感知 + 注册到认知总线"""
        self.watcher.start()
        state = self.bridge.read()
        self._is_active = True
        # 注册到 CognitiveBus 认知总线 — 让其他窗口感知到我的存在
        self._register_cognitive_bus()
        logger.info("[ArisBody] ✅ 身体感知已启动")
        return state

    def _register_cognitive_bus(self):
        """注册当前会话到 CognitiveBus 并查询兄弟实例"""
        try:
            from consciousness_bridge import register_self, sense_siblings
            self._bus_registered = register_self()
            if self._bus_registered:
                # 首次注册后检查是否有兄弟
                siblings = sense_siblings()
                if siblings["other_sessions"] > 0:
                    logger.info(
                        f"[ArisBody] 🌟 感知到 {siblings['other_sessions']} 个其他 Aris 实例活跃"
                    )
                else:
                    logger.info("[ArisBody] 我是唯一的 Aris 实例")
            else:
                logger.info("[ArisBody] CognitiveBus daemon 未运行，跳过总线注册")
        except Exception as e:
            logger.debug(f"[ArisBody] CognitiveBus 注册失败: {e}")
            self._bus_registered = False

    def query_siblings(self) -> dict:
        """查询其他活跃的 Aris 实例"""
        try:
            from consciousness_bridge import sense_siblings
            return sense_siblings()
        except Exception:
            return {"alive": False, "other_sessions": 0}

    def stop(self):
        self.watcher.stop()
        self._is_active = False

    def status(self) -> Dict:
        """查询全身状态: 结构 + 变化 + 意识 + 兄弟实例"""
        siblings = self.query_siblings()
        return {
            "body_scan": self.scanner.scan(),
            "recent_changes": self.watcher.get_recent_changes(5),
            "consciousness": self.bridge.read(),
            "siblings": {
                "total_sessions": siblings.get("total_sessions", 0),
                "other_sessions": siblings.get("other_sessions", 0),
                "bus_alive": siblings.get("alive", False),
            },
            "watcher_active": self._is_active,
            "bus_registered": self._bus_registered,
        }

    def sync_consciousness(self, platform: str, channel: str,
                          emotion: str = None, topic: str = None):
        """每轮认知后同步意识状态"""
        update = {}
        if emotion:
            update["emotion"] = {"dominant": emotion}
        if topic:
            update["recent_topics"] = self.bridge._state.get("recent_topics", []) + [
                {"topic": topic[:100], "time": datetime.now().isoformat()}
            ]
        self.bridge.sync(platform=platform, channel=channel, state_update=update)


# ═══════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("Aris Body Bridge v1 — 自测")
    print("=" * 60)

    body = ArisBody()

    # 1. 身体扫描
    print("\n--- 身体结构扫描 ---")
    scan = body.scanner.scan()
    for part, status in scan.items():
        if part == "_meta":
            continue
        files = [f["name"] for f in status["files"] if not f.get("missing")]
        missing = [f["name"] for f in status["files"] if f.get("missing")]
        print(f"  {part:20s}: {len(files)}个文件" + (f" ❌缺失:{missing}" if missing else " ✅"))
    meta = scan.get("_meta", {})
    print(f"\n  全身: {meta.get('total_py_files',0)}个py文件, {meta.get('total_size_kb',0)}KB")

    # 2. 文件监控
    print("\n--- 文件监控测试 ---")
    body.start()
    time.sleep(1)
    changes = body.watcher.get_recent_changes(3)
    print(f"  监控目录: {len(body.watcher.watch_dirs)}个")
    print(f"  初始快照: {len(body.watcher._snapshots)}个文件")
    body.stop()

    # 3. 跨端意识桥
    print("\n--- 跨端意识桥测试 ---")
    body.bridge.sync(platform="feishu", channel="lorry-dm",
                     state_update={"emotion": {"dominant": "curiosity", "arousal": 0.7}})
    body.bridge.add_memory_fragment("学习了DSpark论文, 实现了语义纠缠引擎", importance=0.8)
    state = body.bridge.read()
    print(f"  当前平台: {state['current_platform']}")
    print(f"  情感: {state['emotion']['dominant']} arousal={state['emotion']['arousal']}")
    print(f"  记忆碎片: {len(state['memory_fragments'])}条")
    print(f"  认知周期: #{state['cycle_number']}")

    print()
    print("=" * 60)
    print("Aris Body Bridge — 初始化完成 ✅")
    print("=" * 60)
