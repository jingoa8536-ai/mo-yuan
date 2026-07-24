"""
LAAP Web Avatar - HTTP(8081) + WebSocket(8766) + TTS
Model display mode. EdgeTTS for speech synthesis.
"""
import os, sys, json, time, threading, base64
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

HTTP_PORT = 8081
WS_PORT = 8766
STATIC_DIR = Path(__file__).parent / "laap" / "web" / "static"
sys.path.insert(0, str(Path(__file__).parent))

_ws_clients = set()
_ws_lock = threading.Lock()

# TTS
try:
    from laap.web.voice_bridge import tts_to_base64
    HAS_TTS = True
except: HAS_TTS = False

MIME = {'.vrm':'application/octet-stream','.glb':'model/gltf-binary','.gltf':'model/gltf+json',
        '.js':'application/javascript','.css':'text/css','.html':'text/html; charset=utf-8',
        '.json':'application/json','.png':'image/png','.wasm':'application/wasm'}

class H(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(STATIC_DIR),**kw)
    def guess_type(self,p): return MIME.get(os.path.splitext(p)[1].lower()) or super().guess_type(p)
    def log_message(self,*a): pass
    def end_headers(self): self.send_header("Access-Control-Allow-Origin","*"); SimpleHTTPRequestHandler.end_headers(self)

def ws_broadcast(data):
    msg = json.dumps(data, ensure_ascii=False)
    with _ws_lock:
        for ws in list(_ws_clients):
            try: ws.send(msg)
            except: _ws_clients.discard(ws)

def ws_handle(ws):
    _ws_clients.add(ws)
    ws.send(json.dumps({"type":"status","status":"ready","mode":"model_display","tts":HAS_TTS}))
    try:
        for raw in ws:
            data = json.loads(raw)
            tp = data.get("type")
            if tp == "chat":
                ws.send(json.dumps({"type":"token","text":"[TTS] "+data.get("text","")}))
                ws.send(json.dumps({"type":"response","text":"Model display mode.\n\nFull chat: python -m laap.web.server"}))
            elif tp == "tts":
                text = data.get("text","")
                if HAS_TTS:
                    try:
                        b64 = tts_to_base64(text)
                        ws.send(json.dumps({"type":"tts_audio","data":b64,"format":"mp3"}))
                    except Exception as e:
                        ws.send(json.dumps({"type":"error","message":f"TTS: {e}"}))
                else:
                    ws.send(json.dumps({"type":"error","message":"TTS unavailable"}))
            elif tp == "command" and data.get("cmd") == "ping":
                ws.send(json.dumps({"type":"pong"}))
    except: pass
    finally: _ws_clients.discard(ws)

def main():
    httpd = HTTPServer(("0.0.0.0", HTTP_PORT), H)
    threading.Thread(target=httpd.serve_forever,daemon=True).start()
    import websockets.sync.server
    def run_ws():
        with websockets.sync.server.serve(ws_handle,"0.0.0.0",WS_PORT) as s: s.serve_forever()
    threading.Thread(target=run_ws,daemon=True).start()
    print(f"\n  LAAP Web Avatar - Model Display + TTS")
    print(f"  HTTP: http://localhost:{HTTP_PORT}")
    print(f"  WS:   ws://localhost:{WS_PORT}")
    print(f"  TTS:  {'✅ EdgeTTS' if HAS_TTS else '❌ Not available'}")
    print(f"\n  Open browser: http://localhost:{HTTP_PORT}\n")
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Stopped")

if __name__ == "__main__":
    main()
