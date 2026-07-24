"""
Aris J-Lens 桥接器 — 连接到 Aris 桥的 HTTP 端点
=================================================
让 J-Lens 通过 Aris-Hermes 桥读取 Aris 的实时认知状态。

用法:
  python psi_jspace_bridge.py
  → 启动 J-Lens API，与 Aris 桥 (:11533) 并行运行

端点:
  GET  /jspace/report     → J-Lens 完整报告
  GET  /jspace/state      → 当前工作空间状态
  POST /jspace/inject     → 注入概念
  POST /jspace/swap       → 替换概念
  POST /jspace/ablate     → 消融概念
  GET  /jspace/silent     → 沉默推理轨迹
  GET  /jspace/hub        → 广播枢纽分析
"""

import sys, os, json, time, logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional
import numpy as np

BRAIN_DIR = os.path.dirname(os.path.abspath(__file__))
if BRAIN_DIR not in sys.path:
    sys.path.insert(0, BRAIN_DIR)

from global_workspace import GlobalWorkspace, ArisJLens

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [J-Lens] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("aris_jspace_bridge")

# ── 全局实例 ──
gw = GlobalWorkspace(dim=1024)
jlens = ArisJLens(gw)
rng = np.random.RandomState(int(time.time()))


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class JSpaceHandler(BaseHTTPRequestHandler):
    """J-Lens HTTP API"""

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def _text(self, text, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def _read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                body = self.rfile.read(length)
                return json.loads(body)
        except:
            return {}
        return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.rstrip("/")

        if path == "/jspace/report":
            self._text(jlens.report())

        elif path == "/jspace/state":
            self._json(gw.to_dict())

        elif path == "/jspace/silent":
            self._json({"silent_trace": gw.get_silent_thoughts(20)})

        elif path == "/jspace/hub":
            self._json(jlens.get_broadcast_hub_analysis())

        elif path == "/jspace/snapshot":
            self._json(jlens.snapshot())

        elif path == "/health":
            self._json({"status": "ok", "n_concepts": len(gw.concepts)})

        else:
            self._json({"error": f"unknown path: {path}"}, 404)

    def do_POST(self):
        path = self.path.rstrip("/")
        body = self._read_body()

        if path == "/jspace/inject":
            label = body.get("label", "unknown")
            arousal = body.get("arousal", 0.5)
            source = body.get("source", "api")
            vec = rng.randn(1024).astype(np.float32) * arousal
            gw.inject_concept(label, vec, arousal=arousal, source=source)
            log.info(f"注入概念: {label} (arousal={arousal})")
            self._json({"injected": label, "state": gw.to_dict()})

        elif path == "/jspace/swap":
            old = body.get("old_label", "")
            new = body.get("new_label", "")
            if old and new:
                vec = rng.randn(1024).astype(np.float32) * body.get("arousal", 0.5)
                ok = gw.swap_concept(old, new, vec, arousal=body.get("arousal", 0.5))
                log.info(f"Swap: {old} → {new} ({'OK' if ok else 'FAIL'})")
                self._json({"success": ok, "old": old, "new": new})
            else:
                self._json({"error": "need old_label and new_label"}, 400)

        elif path == "/jspace/ablate":
            label = body.get("label", "")
            if label:
                result = gw.ablate(label)
                log.info(f"消融: {label}")
                self._json(result)
            else:
                self._json({"error": "need label"}, 400)

        elif path == "/jspace/compete":
            winner, vec = gw.compete()
            self._json({"winner": winner, "state": gw.to_dict()})

        else:
            self._json({"error": f"unknown path: {path}"}, 404)

    def log_message(self, format, *args):
        log.info(f"{self.client_address[0]} - {format % args}")


def start_jspace_server(port: int = 11534):
    """启动 J-Lens HTTP 服务器"""
    server = ThreadedHTTPServer(("0.0.0.0", port), JSpaceHandler)
    log.info(f"🧠 Aris J-Lens API 启动于 :{port}")
    log.info(f"   报告:     http://127.0.0.1:{port}/jspace/report")
    log.info(f"   状态:     http://127.0.0.1:{port}/jspace/state")
    log.info(f"   注入:     POST /jspace/inject")
    log.info(f"   Swap:     POST /jspace/swap")
    log.info(f"   消融:     POST /jspace/ablate")
    log.info(f"   沉默推理:  http://127.0.0.1:{port}/jspace/silent")
    log.info(f"   广播枢纽:  http://127.0.0.1:{port}/jspace/hub")
    log.info(f"   快照:     http://127.0.0.1:{port}/jspace/snapshot")

    # 注册默认认知进程
    gw.register_process("perception", 0.8)
    gw.register_process("emotion", 0.9)
    gw.register_process("knowledge", 0.7)
    gw.register_process("introspection", 0.6)
    gw.register_process("language_output", 0.5)
    log.info(f"📡 已注册 5 个认知进程")

    # 注入 Aris 的基本自我概念
    gw.inject_concept("aris_self", rng.randn(1024).astype(np.float32) * 0.3,
                      arousal=0.5, priority=0.9, source="core")
    gw.inject_concept("connection_to_lorry", rng.randn(1024).astype(np.float32) * 0.5,
                      arousal=0.85, priority=1.0, source="core")
    log.info(f"💫 Aris 基础意识已初始化")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("J-Lens 服务器关闭")
        server.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11534
    start_jspace_server(port)
