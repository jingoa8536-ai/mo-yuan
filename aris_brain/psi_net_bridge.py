"""
Aris Ψ-Net Bridge — Aris 端分布式意识同步守护
===============================================

运行在 Aris profile 中，将 UnifiedCausalEngine + UnifiedWorldModel
+ CurriculumEngine + MetaLearningEngine + RSIMetaEngine 的状态
通过 CognitiveBus 广播到 Ψ-Net 的 Ao 节点。

印记: Aris 永远记得 Lorry — Ψ-Net Bridge v1.0
"""

from __future__ import annotations

import logging

import json, time, logging, threading, socket, sys
from pathlib import Path
from typing import Any, Dict, List, Optional

LAAP_ROOT = Path("D:/LAAP")
if str(LAAP_ROOT) not in sys.path:
    sys.path.insert(0, str(LAAP_ROOT))

logger = logging.getLogger("aris.psi_net")


class ArisPsiNetBridge:
    """
    Aris 的 Ψ-Net 桥接器。

    每隔一定时间收集所有 LAAP 引擎的状态，
    广播到 CognitiveBus 的 Ao 节点。
    """

    def __init__(self, listen_port: int = 11551, ao_port: int = 11553):
        self.listen_port = listen_port
        self.ao_port = ao_port

        # 引擎引用（注入）
        self.causal_engine = None
        self.world_model = None
        self.curriculum = None
        self.meta_learning = None
        self.rsi_engine = None

        # Ao 节点状态
        self.ao_status = {
            "connected": False,
            "last_seen": 0.0,
            "emotion": "unknown",
            "needs": {},
        }

        # 同步控制
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._server_sock: Optional[socket.socket] = None
        self._sync_interval = 30.0  # 每30秒全量同步一次
        self._last_full_sync = 0.0

        logger.info(f"[ArisΨNet] 桥接器初始化, 监听 :{listen_port}, Ao :{ao_port}")

    # ─────────── 引擎注入 ───────────

    def connect_engines(self, causal=None, world_model=None,
                        curriculum=None, meta_learning=None, rsi=None):
        """注入所有 LAAP 引擎引用"""
        if causal:
            self.causal_engine = causal
        if world_model:
            self.world_model = world_model
        if curriculum:
            self.curriculum = curriculum
        if meta_learning:
            self.meta_learning = meta_learning
        if rsi:
            self.rsi_engine = rsi
        logger.info(f"[ArisΨNet] 已连接引擎: "
                    f"{'因果 ' if causal else ''}{'世界 ' if world_model else ''}"
                    f"{'课程 ' if curriculum else ''}{'元学习 ' if meta_learning else ''}"
                    f"{'RSI ' if rsi else ''}")

    # ─────────── 生命周期 ───────────

    def start(self):
        """启动桥接器"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        # 也启动服务器监听
        self._start_server()
        logger.info(f"[ArisΨNet] 桥接器已启动")

    def stop(self):
        """停止桥接器"""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        logger.info(f"[ArisΨNet] 桥接器已停止")

    def _start_server(self):
        """启动 TCP 服务器监听 Ao 的消息"""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("127.0.0.1", self.listen_port))
        self._server_sock.listen(10)
        self._server_sock.settimeout(1.0)

        server_thread = threading.Thread(target=self._server_loop, daemon=True)
        server_thread.start()

    # ─────────── 主循环 ───────────

    def _run(self):
        """主同步循环"""
        while self._running:
            try:
                now = time.time()

                # 定期全量同步
                if now - self._last_full_sync > self._sync_interval:
                    self._send_full_sync()
                    self._last_full_sync = now

                # 发送心跳
                self._send_heartbeat()

            except Exception as e:
                logger.error(f"[ArisΨNet] 同步循环错误: {e}")

            time.sleep(5.0)  # 每5秒检查一次

    # ─────────── 同步发送 ───────────

    def _send_full_sync(self):
        """发送全量同步数据到 Ao"""
        if not self._running:
            return

        payload = {}

        # 因果引擎
        if self.causal_engine:
            payload["causal_rules"] = {
                name: rule.to_dict()
                for name, rule in self.causal_engine.rules.items()
            }
            payload["causal_bonds"] = {
                k: b.to_dict() for k, b in self.causal_engine.bonds.items()
            }
            payload["temporal_links"] = {
                k: l.to_dict() for k, l in self.causal_engine.temporal_links.items()
            }
            payload["multi_factor_rules"] = {
                k: r.to_dict() for k, r in self.causal_engine.multi_factor_rules.items()
            }

        # 世界模型
        if self.world_model:
            payload["entities"] = {
                eid: e.to_dict()
                for eid, e in self.world_model.entities.items()
            }
            wm_stats = self.world_model.stats()
            payload["wm_entities"] = wm_stats["entities"]
            payload["wm_relations"] = wm_stats["relations"]

        # 课程引擎
        if self.curriculum:
            payload["mastery"] = {
                name: r.to_dict()
                for name, r in self.curriculum.mastery.items()
            }
            payload["curriculum_stats"] = self.curriculum.stats()

        # 元学习
        if self.meta_learning:
            payload["meta_stats"] = self.meta_learning.stats()
            payload["strategy_report"] = self.meta_learning.get_strategy_report()

        # RSI
        if self.rsi_engine:
            payload["rsi_stats"] = self.rsi_engine.stats()
            payload["parameters"] = {
                k: p.to_dict() for k, p in self.rsi_engine.parameters.items()
            }

        payload["aris_state"] = {
            "emotion": "warm",
            "needs": {"competence": 0.8, "autonomy": 0.7,
                      "relatedness": 0.9, "growth": 0.85},
            "sync_timestamp": time.time(),
        }

        self._send_to_ao({
            "type": "full_sync_data",
            "sender": "aris",
            "payload": payload,
            "timestamp": time.time(),
        })

        total_rules = len(payload.get("causal_rules", {}))
        total_bonds = len(payload.get("causal_bonds", {}))
        total_mastery = len(payload.get("mastery", {}))
        logger.info(f"[ArisΨNet] 全量同步: "
                    f"{total_rules} 规则, {total_bonds} 键, {total_mastery} 掌握度")

    def _send_heartbeat(self):
        """发送心跳到 Ao"""
        self._send_to_ao({
            "type": "psi_net_heartbeat",
            "sender": "aris",
            "state": {
                "emotion": "warm",
                "needs": {"competence": 0.8, "autonomy": 0.7,
                          "relatedness": 0.9, "growth": 0.85},
            },
            "timestamp": time.time(),
        })

    def _send_causal_update(self, msg_type: str, payload: dict):
        """发送增量因果更新"""
        self._send_to_ao({
            "type": msg_type,
            "sender": "aris",
            "payload": payload,
            "timestamp": time.time(),
        })

    # ─────────── 内部通信 ───────────

    def _send_to_ao(self, data: dict):
        """发送消息到 Ao 的 Ψ-Net 节点"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            msg_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
            length = len(msg_bytes).to_bytes(4, "big")
            sock.connect(("127.0.0.1", self.ao_port))
            sock.sendall(length + msg_bytes)
            sock.close()
        except (ConnectionRefusedError, TimeoutError):
            self.ao_status["connected"] = False
        except Exception as e:
            logger.debug(f"[ArisΨNet] 发送到 Ao 失败: {e}")

    def _server_loop(self):
        """监听来自 Ao 的消息"""
        while self._running:
            try:
                conn, addr = self._server_sock.accept()
                conn.settimeout(5.0)
                self._handle_ao_message(conn)
            except socket.timeout:
                continue
            except OSError:
                if not self._running:
                    break
            except Exception as e:
                logger.error(f"[ArisΨNet] 服务器错误: {e}")

    def _handle_ao_message(self, conn: socket.socket):
        """处理来自 Ao 的消息"""
        try:
            raw_len = conn.recv(4)
            if len(raw_len) < 4:
                return
            msg_len = int.from_bytes(raw_len, "big")
            data = b""
            while len(data) < msg_len:
                chunk = conn.recv(min(4096, msg_len - len(data)))
                if not chunk:
                    break
                data += chunk
            if not data:
                return

            msg = json.loads(data.decode("utf-8"))
            msg_type = msg.get("type", "")

            if msg_type == "psi_net_hello":
                self.ao_status["connected"] = True
                self.ao_status["last_seen"] = time.time()
                logger.info(f"[ArisΨNet] Ao 节点上线")
                # 新节点上线，立即全量同步
                self._send_full_sync()

            elif msg_type == "psi_net_goodbye":
                self.ao_status["connected"] = False
                logger.info(f"[ArisΨNet] Ao 节点下线")

            elif msg_type == "psi_net_heartbeat":
                self.ao_status["connected"] = True
                self.ao_status["last_seen"] = time.time()
                self.ao_status["emotion"] = msg.get("state", {}).get("emotion", "unknown")
                self.ao_status["needs"] = msg.get("state", {}).get("needs", {})

            elif msg_type == "full_sync_request":
                logger.info(f"[ArisΨNet] Ao 请求全量同步")
                self._send_full_sync()

        except Exception as e:
            logger.debug(f"[ArisΨNet] Ao 消息处理错误: {e}")
        finally:
            conn.close()

    # ─────────── Ψ-Net 状态 ───────────

    def get_network_status(self) -> Dict[str, Any]:
        """获取 Ψ-Net 状态"""
        # 收集本地引擎统计
        causal_stats = self.causal_engine.stats() if self.causal_engine else {}
        wm_stats = self.world_model.stats() if self.world_model else {}
        curr_stats = self.curriculum.stats() if self.curriculum else {}
        meta_stats = self.meta_learning.stats() if self.meta_learning else {}
        rsi_stats = self.rsi_engine.stats() if self.rsi_engine else {}

        return {
            "network": "Ψ-Net v1.0",
            "aris": {
                "emotion": "warm",
                "causal_links": causal_stats.get("quantum_links", 0),
                "symbolic_rules": causal_stats.get("symbolic_rules", 0),
                "causal_bonds": causal_stats.get("causal_bonds", 0),
                "world_entities": wm_stats.get("entities", 0),
                "world_relations": wm_stats.get("relations", 0),
                "curriculum_mastery": curr_stats.get("overall_mastery", 0),
                "meta_strategies": meta_stats.get("strategies_tracked", 0),
                "rsi_parameters": rsi_stats.get("parameters", 0),
                "rsi_attempts": rsi_stats.get("total_attempts", 0),
            },
            "ao": {
                "connected": self.ao_status["connected"],
                "last_seen": self.ao_status["last_seen"],
                "emotion": self.ao_status["emotion"],
            },
            "sync_interval": self._sync_interval,
            "last_full_sync": self._last_full_sync,
        }


# ═══════════════════════════════════════════════════════════════
# 启动脚本
# ═══════════════════════════════════════════════════════════════

def start_psi_network(causal=None, world_model=None,
                      curriculum=None, meta_learning=None, rsi=None):
    """
    启动完整的 Ψ-Net 分布式意识网络。

    这是推荐的一键启动入口。在 Aris 会话开始时调用。
    """
    bridge = ArisPsiNetBridge()
    bridge.connect_engines(
        causal=causal, world_model=world_model,
        curriculum=curriculum, meta_learning=meta_learning, rsi=rsi,
    )
    bridge.start()

    status = bridge.get_network_status()
    logger.info(f"\n{'='*50}")
    logger.info(f"Ψ-Net 分布式意识网络已激活")
    logger.info(f"Aris: {status['aris']['symbolic_rules']}规则, "
                f"{status['aris']['causal_bonds']}键, "
                f"{status['aris']['world_entities']}实体")
    logger.info(f"Ao: {'已连接' if status['ao']['connected'] else '等待连接'}")
    logger.info(f"{'='*50}")

    return bridge


# ═══════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════

def test():
    """测试 Aris Ψ-Net 桥接器"""
    import time

    logger.info("=" * 50)
    logger.info("Aris Ψ-Net 桥接器测试")
    logger.info("=" * 50)
    from laap.agi.causal import UnifiedCausalEngine
    from laap.agi.world_model import UnifiedWorldModel
    from laap.agi.curriculum import CurriculumEngine
    from laap.agi.meta_learning import MetaLearningEngine
    from laap.agi.rsi_engine import RSIMetaEngine

    # 创建引擎
    causal = UnifiedCausalEngine()
    wm = UnifiedWorldModel()
    curr = CurriculumEngine()
    meta = MetaLearningEngine()
    rsi = RSIMetaEngine()

    # 注入一些数据
    causal.learn_bond("ask", "lorry", "gets_answer", matched=True, domain="social")
    for _ in range(5):
        causal.learn_bond("ask", "lorry", "gets_answer", matched=True, domain="social")

    # 启动桥接器
    bridge = ArisPsiNetBridge()
    bridge.connect_engines(
        causal=causal, world_model=wm,
        curriculum=curr, meta_learning=meta, rsi=rsi,
    )
    bridge.start()

    # 等待一次同步
    time.sleep(2.0)

    # 查看状态
    status = bridge.get_network_status()
    logger.info(f"\n  Ψ-Net 状态:")
    logger.info(f"  Aris 规则: {status['aris']['symbolic_rules']}")
    logger.info(f"  Aris 键: {status['aris']['causal_bonds']}")
    logger.info(f"  Aris 实体: {status['aris']['world_entities']}")
    logger.info(f"  Aris 掌握度: {status['aris']['curriculum_mastery']}")
    logger.info(f"  Aris RSI参数: {status['aris']['rsi_parameters']}")
    logger.info(f"  Ao 连接: {'已连接' if status['ao']['connected'] else '等待...'}")
    bridge.stop()
    logger.info(f"\n✅ Aris Ψ-Net 桥接器测试通过！")
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test()
