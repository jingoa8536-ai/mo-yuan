#!/usr/bin/env python3
"""
Aris QLG Provider v2 — 统一引擎 API 服务
===========================================
把 Aris Unified Engine v2 包装成 OpenAI Chat Completions API，
这样 Hermes Agent 可以直接把它当成 LLM 使用。

整合引擎：UN6 v10 + V12 Semantic + QLG + V12.5 Markov + V15 Fusion
         + Paragraph Synth + V11 Reasoner + QRE v1 + RFS + Code Kernel

启动后，在 config.yaml 里设置：
  provider: custom
  openai_base_url: http://localhost:11522/v1
  openai_api_key: aris-quantum
  model: aris-unified-v2

印记: Aris 永远记得 Lorry — 2026-06-22
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, signal
sys.path.insert(0, os.path.dirname(__file__) or '.')
HOST = "0.0.0.0"
PORT = 11522

# 直接使用统一引擎 v2
# 如果 v2 不可用，退回到 v1
try:
    from aris_unified_engine_v2 import ArisUnifiedEngineV2, MODEL
    ENGINE_CLS = ArisUnifiedEngineV2
    log.info = print
    log_name = "UnifiedV2"
except ImportError as e:
    from aris_unified_engine import ArisUnifiedEngine, MODEL
    ENGINE_CLS = ArisUnifiedEngine
    log_name = "UnifiedV1"

logger.info(f"\n{'='*50}")
logger.info(f"🧠 Aris QLG Provider v2 — 统一引擎({log_name})")
logger.info(f"{'='*50}\n")
def run_server(host=HOST, port=PORT):
    from http.server import HTTPServer, BaseHTTPRequestHandler

    logger.info("正在初始化统一引擎...")
    engine = ENGINE_CLS(verbose=False)
    logger.info("引擎就绪，启动API服务")
    class OpenAIHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args): pass

        def do_POST(self):
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length) if length else b"{}"
            path = self.path
            try:
                data = json.loads(body) if length else {}
                if '/chat/completions' in path:
                    messages = data.get('messages', [])
                    result = engine.chat(messages)
                    self._json_response(result, 200)
                elif '/models' in path:
                    self._json_response({
                        "object": "list",
                        "data": [{"id": MODEL, "object": "model",
                                  "created": int(time.time()), "owned_by": "aris"}]
                    }, 200)
                else:
                    self._json_response({"error": f"not found: {path}"}, 404)
            except Exception as e:
                logger.error(f"⚠️ API Error: {e}")
                import traceback; traceback.print_exc()
                self._json_response({"error": str(e)}, 500)

        def do_GET(self):
            path = self.path
            if path == '/v1/models' or path == '/models':
                self._json_response({
                    "object": "list",
                    "data": [{"id": MODEL, "object": "model",
                              "created": int(time.time()), "owned_by": "aris"}]
                }, 200)
            elif path == '/health':
                self._json_response({
                    "status": "ok",
                    "engine": f"aris-{log_name.lower()}",
                    "zero_llm": True,
                    "model": MODEL,
                }, 200)
            else:
                self._json_response({"error": "not found"}, 404)

        def _json_response(self, data, status=200):
            resp = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(resp)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(resp)

    server = HTTPServer((host, port), OpenAIHandler)
    logger.info(f"\n{'='*50}")
    logger.info(f"🧠 Aris QLG Provider v2 — OpenAI Compatible API")
    logger.info(f"{'='*50}")
    logger.info(f"  服务: http://{host}:{port}")
    logger.info(f"  API:  POST /v1/chat/completions")
    logger.info(f"  模型: {MODEL}")
    logger.info(f"  引擎: {log_name} ({ENGINE_CLS.__name__})")
    logger.info(f"{'='*50}")
    logger.info(f"  按 Ctrl+C 停止")
    logger.info(f"{'='*50}\n")
    def shutdown(sig, frame):
        logger.info("\n收到停止信号，关闭引擎...")
        engine.close()
        server.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nQLG Provider 停止。")
        engine.close()


if __name__ == '__main__':
    run_server()
