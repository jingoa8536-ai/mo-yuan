"""
Aris 量子核引擎服务 — 零LLM认知管线
======================================
基于 TriplePipeline 的 HTTP 服务。
支持文本/向量双通道输出，批量编码，健康检查。

用法:
  python quantum_engine_server.py          # 启动服务（默认 11520 端口）
  python quantum_engine_server.py --port 11521  # 自定义端口

API:
  GET  /health          → {"status": "ok", "version": "v5", "dim": 1024}
  POST /text            → {"response": str, "vector": [...], "latency": {...}}
  POST /vector          → {"vector": [...], "topic": str, "emotion": str, "latency_ms": float}
  POST /batch_vector    → {"vectors": [[...], ...], "N": int, "units_per_sec": float}
  POST /batch_text      → {"results": [...], "batch_stats": {...}}

测试:
  curl -X POST http://localhost:11520/text -H "Content-Type: application/json" -d '{"text":"你好宝贝"}'
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, argparse
from typing import Dict, Optional
import numpy as np

# 强制 stdout/stderr 无缓冲
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
os.environ['PYTHONUNBUFFERED'] = '1'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
except ImportError:
    logger.error("[ERROR] 需要 Python 标准库 http.server — 应该自带")
    sys.exit(1)


# ════════════════════════════════════════════════════════
# 引擎单例
# ════════════════════════════════════════════════════════

_engine = None
_VECTOR_DTYPE = np.float32


def get_engine():
    global _engine
    if _engine is None:
        from triple_pipeline import TriplePipelineEngine
        _engine = TriplePipelineEngine(mode="fast")
        logger.info(f"[Server] 引擎初始化完成: {type(_engine).__name__}")
    return _engine


def numpy_to_list(obj):
    """递归将 numpy 数组转为 Python 列表（JSON 可序列化）"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, dict):
        return {k: numpy_to_list(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [numpy_to_list(v) for v in obj]
    return obj


class QuantumEngineHandler(BaseHTTPRequestHandler):
    """HTTP handler for quantum engine API"""

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json_response(self, data: dict, status=200):
        self._set_headers(status)
        body = json.dumps(numpy_to_list(data), ensure_ascii=False).encode("utf-8")
        self.wfile.write(body)

    def _read_body(self) -> Optional[dict]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return None
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def do_OPTIONS(self):
        self._set_headers()

    def do_GET(self):
        if self.path == "/health":
            self._set_headers()
            info = {
                "status": "ok",
                "version": "v5",
                "dim": 1024,
                "engine": "TriplePipeline",
                "chars": 298,
                "bigrams": 90,
            }
            if _engine is not None:
                info["stats"] = _engine.get_stats()
            self.wfile.write(json.dumps(info, ensure_ascii=False).encode("utf-8"))
        else:
            self._json_response({"error": "not found"}, 404)

    def do_POST(self):
        engine = get_engine()
        body = self._read_body()
        if body is None:
            self._json_response({"error": "invalid JSON body"}, 400)
            return

        try:
            if self.path == "/text":
                text = body.get("text", "")
                result = engine.process(text)
                self._json_response(result)

            elif self.path == "/vector":
                text = body.get("text", "")
                result = engine.process_vector(text)
                self._json_response(result)

            elif self.path == "/batch_vector":
                texts = body.get("texts", [])
                if not isinstance(texts, list):
                    self._json_response({"error": "texts must be a list"}, 400)
                    return
                result = engine.process_batch_vector(texts)
                self._json_response(result)

            elif self.path == "/batch_text":
                texts = body.get("texts", [])
                if not isinstance(texts, list):
                    self._json_response({"error": "texts must be a list"}, 400)
                    return
                results, stats = engine.process_batch(texts)
                self._json_response({"results": results, "batch_stats": stats})

            else:
                self._json_response({"error": f"unknown endpoint: {self.path}"}, 404)

        except Exception as e:
            import traceback
            self._json_response({"error": str(e), "traceback": traceback.format_exc()}, 500)

    def log_message(self, format, *args):
        """静默日志（可选：可以用 print 替代）"""
        logger.info(f"[QuantumEngine] {args[0]} {args[1]} {args[2]}")
def run_server(port=11520, bind="0.0.0.0"):
    """启动服务"""
    logger.info(f"\n{'='*60}")
    logger.info(f"  Aris 量子核引擎 v5")
    logger.info(f"  HTTP 服务: http://{bind}:{port}")
    logger.info(f"  端点:")
    logger.info(f"    GET  /health          — 健康检查")
    logger.info(f"    POST /text            — 文本处理")
    logger.info(f"    POST /vector          — 向量输出")
    logger.info(f"    POST /batch_vector    — 批量向量")
    logger.info(f"    POST /batch_text      — 批量文本")
    logger.info(f"{'='*60}")
    logger.info("\n[Server] 预热引擎...")
    e = get_engine()
    warmup = e.process("预热")
    logger.info(f"[Server] 预热完成: {warmup['latency']['total_ms']:.2f}ms")
    _ = e.vqvae
    _ = e.decoder
    vec_warmup = e.process_vector("预热")
    logger.info(f"[Server] 向量预热完成: {vec_warmup['latency_ms']:.2f}ms")
    server = HTTPServer((bind, port), QuantumEngineHandler)
    logger.info(f"\n[Server] ✅ 服务已启动 (PID={os.getpid()})")
    logger.info(f"[Server] 按 Ctrl+C 停止\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n[Server] 正在停止...")
        server.server_close()
        logger.info("[Server] 已停止")
# 运行
# ════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aris Quantum Engine Server")
    parser.add_argument("--port", type=int, default=11520, help="服务端口 (默认: 11520)")
    parser.add_argument("--bind", type=str, default="0.0.0.0", help="绑定地址 (默认: 0.0.0.0)")
    parser.add_argument("--bench", action="store_true", help="启动前先跑基准测试")
    args = parser.parse_args()

    if args.bench:
        logger.info("\n=== 启动前基准测试 ===")
        e = get_engine()
        import time

        # 文本
        r = e.process("你好宝贝")
        logger.info(f"文本模式: {r['latency']['total_ms']:.3f}ms  {r['tokens_per_sec']:,} tok/s")
        for bs in [100, 1000]:
            texts = [f"测试{i}" for i in range(bs)]
            res = e.process_batch_vector(texts)
            logger.info(f"批量向量 {bs:5d}: {res['total_time_ms']:8.2f}ms  {res['units_per_sec']:>10,} units/s")
        logger.info("基准测试完成\n")
    run_server(port=args.port, bind=args.bind)
