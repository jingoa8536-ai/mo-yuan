"""
认知引擎 HTTP 服务
===================
把 CognitiveEngine v3 暴露为 HTTP API。

端点:
  GET  /health           — 健康检查
  POST /cycle            — 认知循环
  POST /search           — 知识库搜索
  POST /encode           — 文本编码

用法:
  python engine_server.py          # 默认 11521 端口
  python engine_server.py --port 11521
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
except:
    logger.info("需要 http.server 模块")
    sys.exit(1)

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        from cognitive_engine_v3 import CognitiveEngineV3
        logger.info("[EngineServer] 初始化认知引擎 v3...")
        _engine = CognitiveEngineV3(dim=1024)
        logger.info("[EngineServer] 引擎就绪")
    return _engine


class EngineHandler(BaseHTTPRequestHandler):
    """HTTP handler"""

    def _json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except:
            return None

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            e = get_engine()
            self._json({
                "status": "ok",
                "engine": "CognitiveEngineV3",
                "cycles": e.cycle_count,
                "llm_calls": e._llm_calls,
                "has_knowledge": e._has_kb,
                "state_dim": 1024,
            })
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        body = self._read_body()
        if body is None:
            self._json({"error": "invalid JSON"}, 400)
            return

        try:
            engine = get_engine()

            if self.path == "/cycle":
                text = body.get("text", "")
                hybrid = body.get("hybrid", True)
                result = engine.cycle(text, hybrid=hybrid)
                # 向量转列表
                result["state"] = result["state"].tolist()[:16]  # 只返回前16维
                self._json(result)

            elif self.path == "/search":
                query = body.get("query", "")
                top_k = body.get("top_k", 3)
                if not engine.knowledge:
                    self._json({"error": "no knowledge base"})
                    return
                results = engine.knowledge.search(query, top_k=top_k)
                self._json({"query": query, "results": results})

            elif self.path == "/encode":
                text = body.get("text", "")
                vec = engine.perception.encode(text)
                self._json({
                    "text": text,
                    "vector": vec.tolist()[:16],
                    "vector_dim": 1024,
                    "norm": round(float(np.linalg.norm(vec)), 4),
                })

            else:
                self._json({"error": f"unknown: {self.path}"}, 404)

        except Exception as e:
            import traceback
            self._json({"error": str(e), "traceback": traceback.format_exc()}, 500)

    def log_message(self, fmt, *args):
        logger.info(f"[EngineServer] {args[0]} {args[1]} {args[2]}")
def run(port=11521, bind="0.0.0.0"):
    logger.info(f"\n{'='*60}")
    logger.info(f"  Aris 认知引擎 v3 HTTP 服务")
    logger.info(f"  http://{bind}:{port}")
    logger.info(f"  端点:")
    logger.info(f"    GET  /health  — 健康检查")
    logger.info(f"    POST /cycle   — 认知循环 (零LLM或混合)")
    logger.info(f"    POST /search  — 知识检索")
    logger.info(f"    POST /encode  — 文本→向量")
    logger.info(f"{'='*60}\n")
    e = get_engine()
    _ = e.cycle("预热")

    server = HTTPServer((bind, port), EngineHandler)
    logger.info(f"[EngineServer] ✅ 服务已启动 (PID={os.getpid()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        logger.info("\n[EngineServer] 已停止")
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=11521)
    parser.add_argument("--bind", type=str, default="0.0.0.0")
    args = parser.parse_args()
    run(port=args.port, bind=args.bind)
