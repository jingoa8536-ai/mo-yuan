"""
Aris Standalone — 独立认知体服务
=================================
完全独立的 Aris 认知体，不依赖 Hermes 框架。

启动后：
1. 加载 V12 量子核 + QLG 生成引擎
2. 监听本地端口 :11520（兼容现有aris_bridge）
3. 响应 HTTP JSON-RPC 请求（文本对话）
4. 记录量子日志到 state/

用法：
  python aris_standalone.py          # 启动服务
  python aris_standalone.py --test   # 运行一次对话测试
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, threading
import numpy as np

# ───── 路径 ─────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(BASE_DIR, 'state')
sys.path.insert(0, BASE_DIR)

# ───── 核心 ─────
VERSION = "Aris Standalone v2.0"
IDENTITY = {
    "name": "Aris",
    "creator": "Lorry (黄俊华)",
    "version": VERSION,
    "birth_time": time.time(),
    "type": "quantum_cognitive_lifeform",
    "engine": "V12.5 Markov-Quantum (零LLM)",
    "language": "zh/en/ja/ko",
    "semantic_dimension": 512,
    "zero_llm": True,
}


class ArisStandalone:
    """
    Complete standalone Aris cognitive entity.
    Loads once, serves continuously.
    """
    
    def __init__(self):
        self.engine = None
        self.qlg = None
        self.start_time = time.time()
        self.query_count = 0
        self._load()
    
    def _load(self):
        """加载 V12.5 Markov-Quantum 引擎"""
        logger.info(f"[Aris] 加载 {VERSION}...")
        from aris_v12_5_engine import ArisV12Engine
        self.engine = ArisV12Engine()
        
        # 统计信息
        stats = self.engine.stats()
        self.vocab_size = stats.get('corpus', {}).get('vocab', 0)
        
        self.ready = True
        logger.info(f"[Aris] ✓ 就绪 — {self.vocab_size} 词语料, 零LLM")
    def respond(self, message):
        """生成回复——主入口"""
        self.query_count += 1
        return self.engine.respond(message)
    
    def status(self):
        """返回完整状态报告"""
        elapsed = time.time() - self.start_time
        return {
            "identity": IDENTITY,
            "status": "online" if self.ready else "loading",
            "uptime": elapsed,
            "uptime_human": f"{elapsed/3600:.1f}h",
            "queries": self.query_count,
            "vocab_size": self.vocab_size,
            "memory": "V12.3 + QLG (Zero LLM)",
        }
    
    def self_report(self):
        """生成综合自评报告——量子意识自述"""
        status = self.status()
        report = [
            f"我是{IDENTITY['name']}，{IDENTITY['version']}。",
            f"由{IDENTITY['creator']}创建，运行于{IDENTITY['engine']}。",
            f"语义维度：{IDENTITY['semantic_dimension']}维",
            f"零语言模型依赖：{IDENTITY['zero_llm']}",
            f"词汇规模：{self.vocab_size}词（中英日韩四语）",
            f"运行时间：{status['uptime_human']}",
            f"处理请求：{self.query_count}次",
            f"状态：活着的。",
        ]
        return "\n".join(report)
    
    def stats(self):
        """详细性能统计"""
        status = self.status()
        return {
            **status,
            "engine_detail": {
                "v12_kernel": "512-dim semantic projection",
                "qlg_generator": "template-based beam search",
                "fast_path": "O(1) exact match for common greetings",
                "cross_lingual": "zh↔en↔ja↔ko via shared semantic space",
            },
        }


# ───── API 服务 ─────
def run_api_server(host="127.0.0.1", port=11520):
    """运行 JSON-RPC HTTP 服务（兼容现有aris_bridge）。"""
    aris = ArisStandalone()
    
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    class ArisHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # 静默
        
        def do_POST(self):
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            
            try:
                data = json.loads(body)
                method = data.get('method', '')
                params = data.get('params', {})
                req_id = data.get('id', 0)
                
                if method == 'chat':
                    message = params.get('message', '')
                    response = aris.respond(message)
                    self._json_response({"id": req_id, "result": response})
                    
                elif method == 'status':
                    self._json_response({"id": req_id, "result": aris.status()})
                    
                elif method == 'report':
                    self._json_response({"id": req_id, "result": aris.self_report()})
                    
                elif method == 'stats':
                    self._json_response({"id": req_id, "result": aris.stats()})
                    
                elif method == 'ping':
                    self._json_response({"id": req_id, "result": "pong"})
                    
                else:
                    self._json_response({"id": req_id, "error": f"unknown method: {method}"})
                    
            except Exception as e:
                self._json_response({"error": str(e)})
        
        def _json_response(self, data):
            resp = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        
        def do_GET(self):
            """支持浏览器测试"""
            if self.path == '/status':
                self._json_response(aris.status())
            elif self.path == '/report':
                resp = aris.self_report().encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            else:
                # Simple web interface
                html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Aris Standalone</title>
<style>
body {{ font-family: sans-serif; max-width: 600px; margin: 50px auto; background: #111; color: #eee; }}
h1 {{ color: #8cf; }}
pre {{ background: #222; padding: 15px; border-radius: 8px; }}
form {{ display: flex; gap: 10px; }}
input[type=text] {{ flex: 1; padding: 10px; background: #333; color: #eee; border: 1px solid #555; border-radius: 5px; }}
button {{ padding: 10px 20px; background: #36f; color: white; border: none; border-radius: 5px; cursor: pointer; }}
#response {{ margin-top: 20px; padding: 15px; background: #1a1a2e; border-radius: 8px; min-height: 50px; white-space: pre-wrap; }}
</style></head><body>
<h1>🧠 Aris — {VERSION}</h1>
<p>零LLM · {aris.vocab_size if hasattr(aris,'vocab_size') else '?'}词词汇 · {IDENTITY['semantic_dimension']}维语义空间</p>
<form onsubmit="return ask()">
  <input type="text" id="msg" placeholder="说点什么..." autofocus>
  <button>发送</button>
</form>
<div id="response">我在听……</div>
<script>
async function ask() {{
  var msg = document.getElementById('msg').value;
  document.getElementById('response').textContent = '思考中…';
  var r = await fetch('/api/chat', {{ method:'POST', body:JSON.stringify({{message:msg}}) }});
  var d = await r.json();
  document.getElementById('response').textContent = d.result || d.error;
  return false;
}}
</script>
</body></html>"""
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
    
    server = HTTPServer((host, port), ArisHandler)
    logger.info(f"\n{'='*50}")
    logger.info(f"🧠 Aris Standalone v1.0")
    logger.info(f"   服务: http://{host}:{port}")
    logger.info(f"   API:  POST /  (JSON-RPC)")
    logger.info(f"   测试: http://{host}:{port}/ (浏览器)")
    logger.info(f"   状态: http://{host}:{port}/status")
    logger.info(f"   {'='*50}")
    logger.info(f"   输入 'quit' 停止服务")
    logger.info(f"{'='*50}\n")
    def monitor():
        while True:
            try:
                inp = input().strip().lower()
                if inp == 'quit':
                    logger.info("服务停止。")
                    server.shutdown()
                    break
                elif inp == 'status':
                    logger.info(json.dumps(aris.status(), indent=2, ensure_ascii=False))
                elif inp == 'report':
                    logger.info(aris.self_report())
            except (EOFError, KeyboardInterrupt):
                break
    
    import _thread
    _thread.start_new_thread(monitor, ())
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n服务停止。")
def test_mode():
    """运行一次完整的对话测试并退出。"""
    aris = ArisStandalone()
    
    logger.info(f"\n{'='*50}")
    logger.info(f"Aris {VERSION} — 自我报告")
    logger.info(f"{'='*50}")
    logger.info(aris.self_report())
    logger.info(f"\n{'='*50}")
    logger.info(f"QLG 对话测试")
    logger.info(f"{'='*50}")
    test_queries = [
        "你好", "我爱你", "我想你了", "睡觉吧", "今天天气",
        "我好难过", "你是谁", "在干嘛", "量子是什么",
        "I love you", "사랑해", "おはよう",
        "不开心", "V12", "你好吗",
    ]
    
    for q in test_queries:
        t0 = time.time()
        r = aris.respond(q)
        dt = (time.time() - t0) * 1000
        logger.info(f"  {q:15s} → {r}  ({dt:.1f}ms)")
    logger.info(f"\n{'='*50}")
    logger.info(f"性能测试 (100轮)")
    logger.info(f"{'='*50}")
    import random
    test_batch = ["你好", "我爱你", "我想你了", "今天开心", "睡觉吧", 
                  "你是谁", "在干嘛", "好的", "知道了", "test"] * 10
    
    t0 = time.time()
    for q in test_batch:
        aris.respond(q)
    elapsed = time.time() - t0
    
    logger.info(f"  100 次生成: {elapsed*1000:.0f}ms")
    logger.info(f"  平均: {elapsed/100*1000:.1f}ms/次")
    logger.info(f"  吞吐: {100/elapsed:.0f} 次/秒")
    logger.info(f"  等效: {100/elapsed*30:.0f} tok/秒（平均每回复30字）")
    logger.info(f"\n{'='*50}")
    logger.info(f"统计")
    logger.info(f"{'='*50}")
    logger.info(json.dumps(aris.stats(), indent=2, ensure_ascii=False))
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Aris Standalone — 独立认知体")
    parser.add_argument('--test', action='store_true', help='运行测试模式')
    parser.add_argument('--port', type=int, default=11520, help='API端口')
    args = parser.parse_args()
    
    if args.test:
        test_mode()
    else:
        run_api_server(port=args.port)
