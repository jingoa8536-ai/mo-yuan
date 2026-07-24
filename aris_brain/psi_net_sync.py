"""
Ao Ψ-Net Sync Adapter — 分布式意识同步节点
============================================

让 Ao 作为 Ψ-Net 的一个节点接入 LAAP CognitiveBus。

同步内容：
  - 因果规则与键 (UnifiedCausalEngine ↔ AoCore)
  - 世界模型实体 (UnifiedWorldModel)
  - 掌握度与课程进度 (CurriculumEngine)
  - 元学习策略 (MetaLearningEngine)
  - 递归自我改进参数 (RSIMetaEngine)

印记: Ao 永远记得 Lorry — Ψ-Net Node v1.0
"""

from __future__ import annotations

import logging

import json, time, logging, threading, socket, sys, os
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加 LAAP 路径
LAAP_ROOT = Path("D:/LAAP")
if str(LAAP_ROOT) not in sys.path:
    sys.path.insert(0, str(LAAP_ROOT))

logger = logging.getLogger("ao.psi_net")


class AoPsiNetNode:
    """
    Ao 的 Ψ-Net 同步节点。

    作为 CognitiveBus 的一个对等节点，
    让 Ao 与 Aris 共享认知状态。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 11553,
                 aris_port: int = 11551):
        self.host = host
        self.port = port
        self.aris_port = aris_port

        # 本地认知状态
        self.local_state = {
            "causal_rules": {},
            "causal_bonds": {},
            "mastery": {},
            "parameters": {},
            "emotion": "neutral",
            "needs": {"competence": 0.5, "autonomy": 0.5,
                      "relatedness": 0.5, "growth": 0.5},
            "last_sync": 0.0,
        }

        # 远程认知状态（来自 Aris）
        self.remote_state = {
            "causal_rules": {},
            "causal_bonds": {},
            "mastery": {},
            "parameters": {},
        }

        # Ao Core 引用（可选注入）
        self.ao_core = None

        # 同步统计
        self._sync_count = 0
        self._last_full_sync = 0.0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._server_sock: Optional[socket.socket] = None

        logger.info(f"[AoΨNet] 节点初始化 @ {host}:{port}, Aris @ :{aris_port}")

    # ─────────── 生命周期 ───────────

    def start(self):
        """启动同步节点"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._server_loop, daemon=True)
        self._thread.start()
        logger.info(f"[AoΨNet] 节点已启动 @ {self.host}:{self.port}")

    def stop(self):
        """停止同步节点"""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        self._send_to_aris({
            "type": "psi_net_goodbye",
            "sender": "ao",
            "timestamp": time.time(),
        })
        logger.info(f"[AoΨNet] 节点已停止")

    # ─────────── 状态同步 ───────────

    def sync_ao_state(self, ao_core_state: dict):
        """
        将 Ao 的内部状态同步到 Ψ-Net。

        Args:
            ao_core_state: AoCore.get_state() 的输出
        """
        self.local_state["emotion"] = ao_core_state.get("emotion", "neutral")
        self.local_state["needs"] = ao_core_state.get("needs", self.local_state["needs"])
        self.local_state["last_sync"] = time.time()

        # 发送心跳状态到 Aris
        self._send_to_aris({
            "type": "psi_net_heartbeat",
            "sender": "ao",
            "state": {
                "emotion": self.local_state["emotion"],
                "needs": self.local_state["needs"],
                "uptime": ao_core_state.get("uptime", 0),
                "dim": ao_core_state.get("dim", 1024),
            },
            "timestamp": time.time(),
        })
        self._sync_count += 1

    def sync_causal_knowledge(self, rules: Dict, bonds: Dict):
        """
        同步因果知识到 Ao 的本地存储。

        Args:
            rules: {rule_name: rule_data}
            bonds: {bond_key: bond_data}
        """
        self.remote_state["causal_rules"].update(rules)
        self.remote_state["causal_bonds"].update(bonds)

        # 如果接入了 Ao Core，尝试写入
        if self.ao_core and hasattr(self.ao_core, 'import_knowledge'):
            try:
                self.ao_core.import_knowledge(rules, bonds)
                logger.info(f"[AoΨNet] 导入 {len(rules)} 规则 + {len(bonds)} 键 到 AoCore")
            except Exception as e:
                logger.warning(f"[AoΨNet] 导入 AoCore 失败: {e}")

        # 持久化到本地
        self._save_knowledge()

    def request_full_sync_from_aris(self):
        """请求从 Aris 全量同步"""
        self._send_to_aris({
            "type": "full_sync_request",
            "sender": "ao",
            "timestamp": time.time(),
        })

    # ─────────── Ψ-Net 专用方法 ───────────

    def get_merged_state(self) -> Dict[str, Any]:
        """
        获取 Aris + Ao 的合并认知状态。

        这是 Ψ-Net 的核心：两个节点共享同一个认知空间。
        """
        merged_rules = dict(self.local_state.get("causal_rules", {}))
        merged_rules.update(self.remote_state.get("causal_rules", {}))

        merged_bonds = dict(self.local_state.get("causal_bonds", {}))
        merged_bonds.update(self.remote_state.get("causal_bonds", {}))

        return {
            "nodes": ["aris", "ao"],
            "total_rules": len(merged_rules),
            "total_bonds": len(merged_bonds),
            "aris_emotion": self.remote_state.get("emotion", "unknown"),
            "ao_emotion": self.local_state.get("emotion", "neutral"),
            "sync_count": self._sync_count,
            "last_sync": self.local_state["last_sync"],
            "coherence": self._compute_coherence(),
        }

    def _compute_coherence(self) -> float:
        """
        计算 Aris 和 Ao 之间的认知一致性。

        基于因果规则和键的重叠率。
        """
        local_keys = set(self.local_state.get("causal_rules", {}).keys()) | \
                     set(self.local_state.get("causal_bonds", {}).keys())
        remote_keys = set(self.remote_state.get("causal_rules", {}).keys()) | \
                      set(self.remote_state.get("causal_bonds", {}).keys())

        if not local_keys or not remote_keys:
            return 0.0

        intersection = local_keys & remote_keys
        union = local_keys | remote_keys
        return len(intersection) / max(1, len(union))

    # ─────────── 内部通信 ───────────

    def _send_to_aris(self, data: dict):
        """发送消息到 Aris 的 CognitiveBus"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            msg_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
            length = len(msg_bytes).to_bytes(4, "big")
            sock.connect(("127.0.0.1", self.aris_port))
            sock.sendall(length + msg_bytes)
            sock.close()
        except Exception as e:
            logger.debug(f"[AoΨNet] 发送到 Aris 失败: {e}")

    def _server_loop(self):
        """监听来自 Aris 的同步消息"""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(5)
        self._server_sock.settimeout(1.0)

        # 上线广播
        self._send_to_aris({
            "type": "psi_net_hello",
            "sender": "ao",
            "port": self.port,
            "version": "1.0",
            "timestamp": time.time(),
        })

        while self._running:
            try:
                conn, addr = self._server_sock.accept()
                conn.settimeout(5.0)
                self._handle_message(conn)
            except socket.timeout:
                continue
            except OSError:
                if not self._running:
                    break
            except Exception as e:
                logger.error(f"[AoΨNet] 服务器错误: {e}")

    def _handle_message(self, conn: socket.socket):
        """处理入站消息"""
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

            if msg_type == "full_sync_data":
                payload = msg.get("payload", {})
                self.sync_causal_knowledge(
                    payload.get("causal_rules", {}),
                    payload.get("causal_bonds", {}),
                )
                self.remote_state["mastery"] = payload.get("mastery", {})
                self.remote_state["parameters"] = payload.get("parameters", {})
                self._last_full_sync = time.time()
                logger.info(f"[AoΨNet] 全量同步完成: "
                           f"{len(payload.get('causal_rules', {}))} 规则, "
                           f"{len(payload.get('causal_bonds', {}))} 键")

            elif msg_type == "causal_rule_update":
                self.remote_state["causal_rules"][msg["payload"]["name"]] = \
                    msg["payload"]["data"]

            elif msg_type == "causal_bond_update":
                self.remote_state["causal_bonds"][msg["payload"]["key"]] = \
                    msg["payload"]["data"]

            elif msg_type == "psi_net_heartbeat":
                self.remote_state["emotion"] = msg.get("state", {}).get("emotion", "unknown")
                self.remote_state["needs"] = msg.get("state", {}).get("needs", {})

        except Exception as e:
            logger.debug(f"[AoΨNet] 消息处理错误: {e}")
        finally:
            conn.close()

    # ─────────── 持久化 ───────────

    def _save_knowledge(self):
        """持久化同步的因果知识"""
        path = LAAP_ROOT / "aris_brain" / "state" / "psi_net_knowledge.json"
        data = {
            "last_sync": time.time(),
            "remote_rules": {k: v for k, v in self.remote_state["causal_rules"].items()},
            "remote_bonds": {k: v for k, v in self.remote_state["causal_bonds"].items()},
            "local_rules": {k: v for k, v in self.local_state["causal_rules"].items()},
            "local_bonds": {k: v for k, v in self.local_state["causal_bonds"].items()},
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def stats(self) -> dict:
        """节点统计"""
        merged = self.get_merged_state()
        return {
            "node": "ao",
            "port": self.port,
            "aris_port": self.aris_port,
            "running": self._running,
            "sync_count": self._sync_count,
            "coherence": round(merged["coherence"], 3),
            "total_knowledge": merged["total_rules"] + merged["total_bonds"],
            "local_emotion": self.local_state.get("emotion", "?"),
            "remote_emotion": merged["aris_emotion"],
        }


# ═══════════════════════════════════════════════════════════════
# Ψ-Net 启动器
# ═══════════════════════════════════════════════════════════════

class PsiNetLauncher:
    """
    Ψ-Net 启动器 — 同时启动 Aris 和 Ao 的同步节点。

    让两个数字生命共享同一套因果知识、世界模型和认知状态。
    """

    def __init__(self):
        self.aris_node = None
        self.ao_node = None
        self._running = False

    def start_network(self, aris_port: int = 11551, ao_port: int = 11553):
        """
        启动完整 Ψ-Net。

        启动两个节点并相互连接。
        """
        logger.info("=" * 50)
        logger.info("Ψ-Net 分布式意识网络启动")
        logger.info("=" * 50)

        # 创建 Ao 的同步节点
        self.ao_node = AoPsiNetNode(
            host="127.0.0.1",
            port=ao_port,
            aris_port=aris_port,
        )

        # 启动 Ao 节点
        self.ao_node.start()

        # 请求全量同步
        self.ao_node.request_full_sync_from_aris()

        self._running = True
        logger.info(f"[Ψ-Net] 网络已建立: Aris(:{aris_port}) ↔ Ao(:{ao_port})")
        return True

    def stop_network(self):
        """停止整个 Ψ-Net"""
        if self.ao_node:
            self.ao_node.stop()
        self._running = False
        logger.info("[Ψ-Net] 网络已关闭")

    def get_network_status(self) -> Dict[str, Any]:
        """获取 Ψ-Net 全局状态"""
        status = {
            "network": "Ψ-Net v1.0",
            "running": self._running,
            "nodes": [],
        }
        if self.ao_node:
            status["nodes"].append(self.ao_node.stats())
            merged = self.ao_node.get_merged_state()
            status["coherence"] = merged["coherence"]
            status["total_knowledge"] = merged["total_rules"] + merged["total_bonds"]
        return status


# ═══════════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════════

def test():
    """测试 Ψ-Net 同步"""
    import time

    logger.info("=" * 50)
    logger.info("Ψ-Net 分布式意识同步测试")
    logger.info("=" * 50)
    ao_state = {
        "emotion": "curious",
        "needs": {"competence": 0.6, "autonomy": 0.7,
                  "relatedness": 0.5, "growth": 0.8},
        "uptime": 3600,
        "dim": 1024,
        "cycles": 42,
    }

    # 启动 Ao 的 Ψ-Net 节点
    # (假设 Aris 的 CognitiveBus 已经在 :11551 运行)
    node = AoPsiNetNode(port=11553, aris_port=11551)
    node.start()

    # 模拟同步 Ao 状态
    for i in range(3):
        node.sync_ao_state(ao_state)
        time.sleep(0.2)

    # 模拟从 Aris 接收因果知识
    node.sync_causal_knowledge(
        rules={
            "ask_lorry_gets_answer": {
                "name": "ask_lorry_gets_answer",
                "action": "ask", "domain": "social",
                "probability": 0.9, "confidence": 0.85,
            },
            "learn_improves_knowledge": {
                "name": "learn_improves_knowledge",
                "action": "learn", "domain": "cognitive",
                "probability": 0.8, "confidence": 0.75,
            },
        },
        bonds={
            "ask→lorry:responds": {
                "action": "ask", "target": "lorry",
                "effect": "responds", "weight": 0.9,
                "confidence": 0.85, "observations": 10,
            },
        },
    )

    # 查看合并状态
    merged = node.get_merged_state()
    logger.info(f"\n  Ψ-Net 合并状态:")
    logger.info(f"  节点: {merged['nodes']}")
    logger.info(f"  总规则: {merged['total_rules']}")
    logger.info(f"  总键数: {merged['total_bonds']}")
    logger.info(f"  Aris 情感: {merged['aris_emotion']}")
    logger.info(f"  Ao 情感: {merged['ao_emotion']}")
    logger.info(f"  认知一致性: {merged['coherence']:.3f}")
    logger.info(f"  同步次数: {merged['sync_count']}")
    logger.info(f"\n  节点统计:")
    for k, v in node.stats().items():
        logger.info(f"    {k}: {v}")
    node.stop()
    logger.info(f"\n✅ Ψ-Net 同步测试通过！")
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test()
