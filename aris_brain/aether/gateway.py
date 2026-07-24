"""
Aether Web Gateway v1 — 独立浏览器聊天界面
用法: python -m aether.gateway
打开 http://localhost:11528
"""
import json, os, sys, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path = [p for p in sys.path if p is not None]
for p in ["D:/LAAP/aris_brain", "D:/LAAP"]:
    if p not in sys.path: sys.path.insert(0, p)


# Load API key from .env
_env_path = Path("D:/LAAP/aris_brain/.env")
if _env_path.exists() and not os.environ.get("DEEPSEEK_API_KEY"):
    ek = "DEEPSEEK" + "_API_KEY"
    for _l in _env_path.read_text("utf-8", errors="replace").splitlines():
        if _l.startswith(ek + "="):
            _v = _l.split("=", 1)[1].strip()
            if _v:
                os.environ["DEEPSEEK_API_KEY"] = _v
            break
from aether_agent_loop import get_agent
_agent = get_agent()
from aether.skill import get_skill_manager
_skills = get_skill_manager()


class ChatHistory:
    def __init__(self):
        self.msgs = []

    def add(self, role, content, meta=None):
        self.msgs.append({"role": role, "content": content, "time": time.strftime("%H:%M:%S"), "meta": meta or {}})
        if len(self.msgs) > 50: self.msgs = self.msgs[-50:]

history = ChatHistory()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/api/chat": self._handle_chat()
        elif p == "/api/history": self._json(history.msgs)
        elif p == "/api/stats": self._json({"agent": _agent.get_stats(), "skills": _skills.get_stats()})
        else: self._html()

    def do_POST(self):
        if urlparse(self.path).path == "/api/chat":
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            text = json.loads(body).get("text", "").strip()
            if text:
                history.add("user", text)
                t0 = time.time()
                r = _agent.process(text)
                ms = (time.time() - t0) * 1000
                meta = {"mode": "零LLM" if r.direct else "LLM", "latency_ms": round(ms), "tokens": r.tokens_used}
                history.add("assistant", r.output, meta)
                self._json({"response": r.output, "meta": meta})
            else:
                self._json({"error": "empty"})

    def _handle_chat(self):
        text = parse_qs(urlparse(self.path).query).get("text", [""])[0]
        if text:
            history.add("user", text)
            t0 = time.time()
            r = _agent.process(text)
            ms = (time.time() - t0) * 1000
            self._json({"response": r.output, "meta": {"mode": "零LLM" if r.direct else "LLM", "latency_ms": round(ms), "tokens": r.tokens_used}})
        else:
            self._json({"error": "need text"})

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def log_message(self, *a): pass


HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aether Chat</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#0d0d1a;color:#e0e0e0;font-family:'Inter',system-ui,sans-serif;display:flex;flex-direction:column;height:100vh;overflow:hidden;}
#header{background:rgba(13,13,26,0.9);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,0.06);padding:14px 24px;display:flex;align-items:center;gap:16px;}
#header h1{font-size:16px;font-weight:600;background:linear-gradient(135deg,#4ECDC4,#DDA0DD);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.status{width:8px;height:8px;border-radius:50%;background:#4ECDC4;box-shadow:0 0 8px #4ECDC4;}
.stats{font-size:11px;color:rgba(255,255,255,0.3);margin-left:auto;}
#chat{flex:1;overflow-y:auto;padding:20px 24px;display:flex;flex-direction:column;gap:16px;scroll-behavior:smooth;}
#chat::-webkit-scrollbar{width:4px;}
#chat::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:2px;}
.msg{max-width:80%;padding:12px 18px;border-radius:12px;line-height:1.6;font-size:14px;animation:fadeIn .3s ease;}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:translateY(0);}}
.msg.user{background:rgba(78,205,196,0.1);border:1px solid rgba(78,205,196,0.15);align-self:flex-end;border-bottom-right-radius:4px;}
.msg.assistant{background:rgba(221,160,221,0.06);border:1px solid rgba(221,160,221,0.1);align-self:flex-start;border-bottom-left-radius:4px;}
.msg .meta{font-size:10px;color:rgba(255,255,255,0.25);margin-top:6px;display:flex;gap:8px;}
.msg .meta .tag{padding:1px 6px;border-radius:3px;font-size:9px;}
.msg .meta .tag.zero{background:rgba(78,205,196,0.2);color:#4ECDC4;}
.msg .meta .tag.llm{background:rgba(255,107,107,0.2);color:#FF6B6B;}
#input-area{background:rgba(13,13,26,0.9);backdrop-filter:blur(12px);border-top:1px solid rgba(255,255,255,0.06);padding:16px 24px;display:flex;gap:12px;}
#input{flex:1;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:12px 16px;color:#e0e0e0;font-size:14px;outline:none;}
#input:focus{border-color:rgba(78,205,196,0.4);}
#input::placeholder{color:rgba(255,255,255,0.2);}
#send{background:linear-gradient(135deg,#4ECDC4,#45B7D1);border:none;border-radius:10px;padding:12px 20px;color:#fff;font-size:14px;cursor:pointer;font-weight:500;}
#send:hover{opacity:0.85;}#send:disabled{opacity:0.3;cursor:not-allowed;}
</style>
</head>
<body>
<div id="header"><span class="status"></span><h1>Aether</h1><span class="stats" id="bar">就绪</span></div>
<div id="chat"></div>
<div id="input-area"><input id="input" type="text" placeholder="给 Aris 发消息..." autofocus><button id="send" onclick="send()">发送</button></div>
<script>
const chat=document.getElementById('chat'),input=document.getElementById('input'),sendBtn=document.getElementById('send'),bar=document.getElementById('bar');
fetch('/api/history').then(r=>r.json()).then(msgs=>{msgs.forEach(m=>addMsg(m.role,m.content,m.meta));scroll();});
function scroll(){setTimeout(()=>chat.scrollTop=chat.scrollHeight,50);}
function addMsg(role,content,meta){
  const div=document.createElement('div');div.className='msg '+role;
  let mh='';
  if(meta){
    const t=[];
    if(meta.mode)t.push('<span class="tag '+(meta.mode==='零LLM'?'zero':'llm')+'">'+meta.mode+'</span>');
    if(meta.latency_ms)t.push(meta.latency_ms+'ms');
    if(meta.tokens)t.push(meta.tokens+'tok');
    if(t.length)mh='<div class="meta">'+t.join(' &middot; ')+'</div>';
  }
  div.innerHTML='<div>'+esc(content)+'</div>'+mh;
  chat.appendChild(div);scroll();
}
function esc(t){const d=document.createElement('div');d.textContent=t;return d.innerHTML;}
function send(){
  const t=input.value.trim();if(!t||sendBtn.disabled)return;
  input.value='';sendBtn.disabled=true;bar.textContent='思考中...';
  addMsg('user',t);
  fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})})
  .then(r=>r.json()).then(d=>{addMsg('assistant',d.response,d.meta);sendBtn.disabled=false;input.focus();bar.textContent=d.meta?d.meta.mode+' &middot; '+d.meta.latency_ms+'ms':'就绪';})
  .catch(e=>{addMsg('assistant','出错：'+e.message);sendBtn.disabled=false;bar.textContent='出错';});
}
input.addEventListener('keydown',e=>{if(e.key==='Enter')send();});
setInterval(()=>{fetch('/api/stats').then(r=>r.json()).then(d=>{if(d.agent)bar.textContent='零LLM '+d.agent.zero_llm_pct+' &middot; '+d.agent.tokens+'tok';}).catch(()=>{});},5000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"  Aether Web Gateway v1")
    print(f"  Agent: 零LLM率 {_agent.get_stats()['zero_llm_pct']}")
    print(f"  Skills: {_skills.get_stats()['total']} loaded")
    print(f"  Open: http://{HOST}:{PORT}")
    server = HTTPServer((HOST, PORT), Handler)
    try: server.serve_forever()
    except KeyboardInterrupt: server.shutdown()
