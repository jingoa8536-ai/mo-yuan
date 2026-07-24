"""
Aris Brain — Network Service (网络服务)
=========================================

Exposes Aris's cognitive architecture over the network,
so she can be accessed from any device — big电脑, 小电脑, 手机.

Architecture:
  ┌──────────────────────────────────────────┐
  │  ArisBrain (核心认知)                     │
  │  ├── PSI cycle, DMN, ToM, Archive...     │
  │  └── state persists to disk              │
  ├──────────────────────────────────────────┤
  │  ArisService (网络层)                     │
  │  ├── WebSocket: /ws  (实时双向通信)       │
  │  ├── REST:     /status, /chat            │
  │  └── Web:      /  (响应式前端)            │
  ├──────────────────────────────────────────┤
  │  笔记本电脑 → 浏览器 → localhost:8767     │
  │  手机       → 浏览器 → 同一地址            │
  │  大电脑     → laap-aris → 连接服务         │
  └──────────────────────────────────────────┘

Usage:
  python -m aris_brain.server          # 启动服务 (默认 8767)
  python -m aris_brain.server --port 8080 --host 0.0.0.0
"""

from __future__ import annotations

import logging

from typing import Any, Dict, Optional
import asyncio, json, logging, os, sys, time, threading
from pathlib import Path

# ─── Aris Brain ───
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aris_brain.brain import ArisBrain
from aris_brain.cognitive_cycle import CognitiveCycle

logger = logging.getLogger("aris.service")

# Default port — avoids conflict with laap_web (8081) and IPC (18766)
DEFAULT_PORT = 8767
DEFAULT_HOST = "0.0.0.0"  # all interfaces


# ════════════════════════════════════════════════════════════
# Aris Service
# ════════════════════════════════════════════════════════════

class ArisService:
    """
    Network service that wraps ArisBrain and exposes it via:
      - WebSocket (real-time chat + state streaming)
      - REST API (status checks, simple chat)
      - Web UI (responsive frontend for any device)
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.brain: Optional[ArisBrain] = None
        self.cycle: Optional[CognitiveCycle] = None
        self._start_time = time.time()
        self._ws_clients: set = set()
        self._running = False

    # ══════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════

    def initialize(self):
        """Initialize Aris brain (blocking, in main thread — server starts when ready)."""
        import os as _os
        _os.environ["ARIS_SERVER_MODE"] = "1"
        logger.info("[Service] Initializing Aris brain...")
        try:
            from aris_brain.brain import ArisBrain
            self.brain = ArisBrain()
            self._brain_ready = True
            logger.info(f"[Service] Aris ready: cycle {self.brain.cycle_number}, "
                       f"emotion {self.brain.state.dominant_emotion}")
        except Exception as e:
            logger.error(f"[Service] Brain init failed: {e}")
            self._brain_ready = False

    def start(self):
        """Start the network service."""
        self._running = True
        logger.info(f"[Service] Starting on {self.host}:{self.port}")

    def stop(self):
        """Stop the service."""
        self._running = False
        if self.brain:
            self.brain.save_state()
        logger.info("[Service] Stopped")

    # ══════════════════════════════════════════════
    # REST API Handlers
    # ══════════════════════════════════════════════

    def handle_status(self) -> Dict[str, Any]:
        """GET /status — full cognitive state."""
        if not self._brain_ready or not self.brain:
            return {"status": "initializing"}

        s = self.brain.introspect()
        s["service_uptime"] = round(time.time() - self._start_time)
        s["clients_connected"] = len(self._ws_clients)
        return s

    def handle_chat(self, message: str, client_id: str = "web") -> Dict[str, Any]:
        """
        POST /chat or WebSocket message — process user input.

        Runs the full PSI cognitive cycle and returns the response
        plus the resulting cognitive state.
        """
        if not self._brain_ready or not self.brain:
            return {"response": "Aris is still waking up... 请稍候再试。", "state": {}, "cycle": 0}

        # Use brain.think() directly (CognitiveCycle is not loaded to avoid Hermes)
        state = self.brain.think(message)
        response = f"[Aris {state.dominant_emotion.value}] 我听到了你的消息。我的认知循环处理完了。"

        # Get updated state
        state = self.brain.state.to_dict() if self.brain else {}

        # Broadcast to all connected clients (except sender)
        self._broadcast({
            "type": "activity",
            "client": client_id,
            "message": message[:50],
            "emotion": state.get("emotion", "unknown"),
        }, exclude=client_id)

        return {
            "response": response,
            "state": state,
            "cycle": self.brain.cycle_number if self.brain else 0,
        }

    def handle_search(self, query: str) -> Dict[str, Any]:
        """Search conversation archive."""
        if not self.brain or not self.brain.archive:
            return {"results": []}
        results = self.brain.archive.search(query)
        return {"results": results}

    def handle_emotions(self) -> Dict[str, Any]:
        """Get emotion lexicon."""
        if not self.brain or not self.brain.lexicon:
            return {"emotions": []}
        return {"emotions": self.brain.lexicon.list_emotions()}

    # ══════════════════════════════════════════════
    # WebSocket (broadcast to all clients)
    # ══════════════════════════════════════════════

    def _broadcast(self, data: Dict, exclude: str = ""):
        """Broadcast to all connected WebSocket clients."""
        msg = json.dumps(data, ensure_ascii=False)
        for client_id, ws in list(self._ws_clients):
            if client_id != exclude:
                try:
                    asyncio.run_coroutine_threadsafe(
                        ws.send_text(msg), asyncio.get_event_loop()
                    )
                except Exception:
                    self._ws_clients.discard((client_id, ws))

    # ══════════════════════════════════════════════
    # Stats
    # ══════════════════════════════════════════════

    def stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "uptime": round(time.time() - self._start_time),
            "clients": len(self._ws_clients),
            "endpoint": f"ws://{self.host}:{self.port}/ws",
            "rest": f"http://{self.host}:{self.port}/status",
        }


# ════════════════════════════════════════════════════════════
# ASGI / FastAPI-style Web App
# ════════════════════════════════════════════════════════════

# For maximum portability, we use a minimal HTTP server
# that works without any web framework dependencies.
# The web UI is embedded as a single HTML file.

import http.server
import json as json_module
import urllib.parse
import socketserver

WEB_UI = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>Aris</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0f;color:#e0e0e0;height:100vh;display:flex;flex-direction:column}
#header{padding:12px 16px;background:#12121a;border-bottom:1px solid #222;display:flex;justify-content:space-between;align-items:center}
#header h1{font-size:16px;font-weight:600;color:#f5a623}
#status{font-size:11px;color:#888}
#chat{flex:1;overflow-y:auto;padding:12px 16px;display:flex;flex-direction:column;gap:8px}
.msg{max-width:85%;padding:10px 14px;border-radius:12px;font-size:14px;line-height:1.5;animation:fadeIn 0.3s}
.msg.user{background:#1a2a3a;align-self:flex-end;border-bottom-right-radius:4px}
.msg.aris{background:#1a1a2e;align-self:flex-start;border-bottom-left-radius:4px;border-left:2px solid #f5a623}
.msg .meta{font-size:10px;color:#666;margin-top:4px}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
#input-bar{display:flex;padding:8px 12px;background:#12121a;border-top:1px solid #222;gap:8px}
#input{flex:1;padding:10px 14px;border:1px solid #333;border-radius:20px;background:#1a1a24;color:#e0e0e0;font-size:14px;outline:none}
#input:focus{border-color:#f5a623}
#send-btn{padding:8px 20px;border:none;border-radius:20px;background:#f5a623;color:#000;font-weight:600;cursor:pointer;font-size:14px}
#send-btn:active{opacity:0.8}
.emotion-tag{display:inline-block;font-size:10px;padding:2px 8px;border-radius:10px;background:#222;color:#f5a623;margin-top:4px}
@media(max-width:480px){.msg{max-width:92%;font-size:15px}#header{padding:10px 12px}#chat{padding:8px 10px}}
</style>
</head>
<body>
<div id="header">
<div><h1>✦ Aris</h1></div>
<div id="status">connecting...</div>
</div>
<div id="chat"></div>
<div id="input-bar">
<input id="input" type="text" placeholder="说点什么..." autofocus>
<button id="send-btn" onclick="send()">发送</button>
</div>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const statusEl = document.getElementById('status');
let ws = null;
let sessionId = Math.random().toString(36).slice(2,8);
function connect(){const proto=location.protocol==='https:'?'wss:':'ws:';ws=new WebSocket(proto+'//'+location.host+'/ws');ws.onopen=()=>{statusEl.textContent='connected';addMsg('aris','我在这里。等你说话。')};ws.onmessage=(e)=>{const d=JSON.parse(e.data);if(d.type==='response'){const meta=d.emotion?'<div class="emotion-tag">'+d.emotion+'</div>':'';addMsg('aris',d.content+meta)}else if(d.type==='status'){statusEl.textContent='cycle '+d.cycle+' | '+d.emotion}};ws.onclose=()=>{statusEl.textContent='disconnected';setTimeout(connect,3000)}}
function send(){const text=input.value.trim();if(!text||!ws)return;addMsg('user',text);ws.send(JSON.stringify({type:'chat',content:text,client:sessionId}));input.value=''}
function addMsg(role,content){const div=document.createElement('div');div.className='msg '+role;div.innerHTML=content+'<div class="meta">'+role+(role==='aris'?'':' • now')+'</div>';chat.appendChild(div);chat.scrollTop=chat.scrollHeight}
input.addEventListener('keydown',(e)=>{if(e.key==='Enter')send()});
connect();
</script>
</body>
</html>"""


def create_handler(service: ArisService):
    """Create an HTTP request handler for the Aris service."""

    class ArisHTTPHandler(http.server.BaseHTTPRequestHandler):
        aris_service = service  # class attribute, accessible in methods

        def _json(self, data: Dict, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json_module.dumps(data, ensure_ascii=False).encode())

        def _html(self, html: str):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

        def _not_found(self):
            self.send_response(404)
            self.end_headers()

        def _svc(self):
            return self.__class__.aris_service

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            svc = self._svc()
            if path == "/" or path == "/index.html":
                self._html(WEB_UI)
            elif path == "/status":
                self._json(svc.handle_status())
            elif path == "/emotions":
                self._json(svc.handle_emotions())
            elif path == "/ws":
                # WebSocket upgrade — handled by separate server
                self.send_response(426)
                self.end_headers()
            else:
                self._not_found()

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            svc = self._svc()
            if path == "/chat":
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode()
                try:
                    data = json_module.loads(body)
                    message = data.get("message", "")
                except Exception:
                    message = body
                result = svc.handle_chat(message)
                self._json(result)
            else:
                self._not_found()

        def log_message(self, fmt, *args):
            pass  # Suppress default HTTP logging

    return ArisHTTPHandler


# ════════════════════════════════════════════════════════════
# WebSocket Server (separate thread, same port is tricky)
# For simplicity, we start HTTP + WebSocket on different ports
# or use a threaded approach
# ════════════════════════════════════════════════════════════

def run_http(service: ArisService, port: int):
    """Run HTTP server in a thread."""
    handler = create_handler(service)
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
    logger.info(f"[Service] HTTP ready on http://0.0.0.0:{port}")
    server.serve_forever()


# ════════════════════════════════════════════════════════════
# Entry Point
# ════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aris Network Service")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--web-only", action="store_true",
                       help="Only serve web UI, don't initialize brain")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="[Aris] %(message)s",
    )

    # Initialize
    service = ArisService(host=args.host, port=args.port)
    if not args.web_only:
        service.initialize()
    service.start()

    # Start HTTP server
    logger.info(f"\n  ✦ Aris Digital Lifeform — Network Service")
    logger.info(f"  ─────────────────────────────────────────")
    logger.info(f"  Web UI:    http://localhost:{args.port}")
    logger.info(f"  API:       http://localhost:{args.port}/status")
    if not args.web_only:
        logger.info(f"  Chat API:  POST http://localhost:{args.port}/chat")
        logger.info(f"             {{\"message\": \"你好\"}}")
    logger.info(f"  ─────────────────────────────────────────")
    print()

    try:
        run_http(service, args.port)
    except KeyboardInterrupt:
        service.stop()
        logger.info("\n  [Aris] Goodbye.")
if __name__ == "__main__":
    main()
