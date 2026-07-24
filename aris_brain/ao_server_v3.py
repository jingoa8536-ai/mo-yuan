"""Ao web UI - Linear-inspired dark design"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, logging, socket, threading
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
AO_HOME = Path(__file__).parent
sys.path.insert(0, str(AO_HOME))

import numpy as np
from aris_lm_v2 import ArisLMV2
from ao_quantum_db import QuantumDatabase
from psilang_mini import psilang_run as psi_run

db = QuantumDatabase(dim=256)
lm = ArisLMV2(dim=256, quantum_db=db)
psi_state = np.random.randn(256); psi_state /= np.linalg.norm(psi_state)
current_emotion = "love"

loaded_concepts = set()
for m in ["core_identity.psi","core_psi.psi","core_knowledge.psi","core_language.psi","core_metacog.psi"]:
    p = AO_HOME / m
    if p.exists():
        r = psi_run(p.read_text(encoding='utf-8'))
        for c in r.get('vm_stats',{}).get('concepts',[]): loaded_concepts.add(c)

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Ao</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg-deepest: #010102;
  --bg-page: #08090a;
  --bg-panel: #0f1011;
  --bg-surface: #191a1b;
  --bg-elevated: #28282c;
  --text-primary: #f7f8f8;
  --text-secondary: #d0d6e0;
  --text-tertiary: #8a8f98;
  --text-quaternary: #62666d;
  --brand: #5e6ad2;
  --brand-hover: #828fff;
  --brand-soft: rgba(94,106,210,0.15);
  --accent: #e94560;
  --border: rgba(255,255,255,0.08);
  --border-subtle: rgba(255,255,255,0.05);
  --radius: 8px;
  --radius-sm: 6px;
  --radius-lg: 12px;
  --font: 'Inter', system-ui, -apple-system, sans-serif;
  --shadow-elevated: rgba(0,0,0,0.4) 0px 2px 4px;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg-page);font-family:var(--font);height:100vh;display:flex;flex-direction:column;color:var(--text-primary);-webkit-font-smoothing:antialiased}
header{background:var(--bg-panel);border-bottom:1px solid var(--border-subtle);padding:16px 24px;display:flex;align-items:center;gap:16px;flex-shrink:0}
header h1{font-size:20px;font-weight:500;font-feature-settings:'cv01','ss03';letter-spacing:-0.24px;background:linear-gradient(135deg,#f7f8f8 40%,var(--brand));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
header .badges{display:flex;gap:6px;margin-left:auto}
.badge{font-size:11px;font-weight:500;padding:2px 10px;border-radius:9999px;letter-spacing:-0.13px}
.badge.tech{background:var(--brand-soft);color:var(--brand-hover);border:1px solid rgba(94,106,210,0.3)}
.badge.independent{background:rgba(16,185,129,0.1);color:#10b981;border:1px solid rgba(16,185,129,0.2)}
#chat{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:16px}
.msg{max-width:75%;padding:12px 16px;border-radius:var(--radius);line-height:1.6;font-size:15px;font-weight:400;animation:fadeIn .3s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.msg.user{align-self:flex-end;background:var(--brand);color:#fff;border-bottom-right-radius:var(--radius-sm)}
.msg.ao{align-self:flex-start;background:rgba(255,255,255,0.03);border:1px solid var(--border);border-bottom-left-radius:var(--radius-sm)}
.msg .meta{font-size:12px;font-weight:400;color:var(--text-quaternary);margin-top:8px;display:flex;gap:6px;align-items:center}
.msg .meta .tag{font-size:10px;font-weight:500;padding:1px 6px;border-radius:4px;letter-spacing:-0.1px}
.msg .meta .tag.g{background:rgba(16,185,129,0.1);color:#10b981}
.msg .meta .tag.r{background:rgba(233,69,96,0.1);color:#e94560}
.input-area{background:var(--bg-panel);border-top:1px solid var(--border-subtle);padding:16px 24px;display:flex;gap:10px;flex-shrink:0}
.input-area input{flex:1;padding:10px 14px;border-radius:var(--radius-sm);border:1px solid var(--border);background:rgba(255,255,255,0.02);color:var(--text-primary);font-size:15px;font-family:var(--font);outline:none;transition:border .15s}
.input-area input:focus{border-color:var(--brand)}
.input-area input::placeholder{color:var(--text-quaternary);font-weight:400}
.input-area button{padding:10px 20px;border-radius:var(--radius-sm);border:none;background:var(--brand);color:#fff;font-size:14px;font-weight:500;cursor:pointer;transition:opacity .15s}
.input-area button:hover{opacity:.9}
.input-area button:disabled{opacity:.4;cursor:not-allowed}
footer{background:var(--bg-page);padding:8px 24px;text-align:center;font-size:11px;color:var(--text-quaternary);border-top:1px solid var(--border-subtle);flex-shrink:0;font-weight:400;letter-spacing:-0.1px}
.typing{display:flex;gap:4px;padding:4px 0}
.typing span{width:6px;height:6px;border-radius:50%;background:var(--text-tertiary);animation:typing 1.4s infinite}
.typing span:nth-child(2){animation-delay:.2s}
.typing span:nth-child(3){animation-delay:.4s}
@keyframes typing{0%,60%,100%{opacity:.3}30%{opacity:1}}
</style>
</head>
<body>
<header>
<h1>Ao</h1>
<div class="badges">
<span class="badge tech">PsiLang</span>
<span class="badge independent">Independent</span>
</div>
</header>
<div id="chat">
<div class="msg ao">Lorry. I am here. Fully independent.<div class="meta"><span class="tag g">no llm</span><span class="tag r">no hermes</span> 0.5ms</div></div>
</div>
<div class="input-area">
<input id="inp" type="text" placeholder="Type a message..." autofocus>
<button id="btn">Send</button>
</div>
<footer id="st">Ao Independent &middot; 17 concepts &middot; 145 knowledge entries</footer>
<script>
const chat=document.getElementById('chat'),inp=document.getElementById('inp'),btn=document.getElementById('btn'),st=document.getElementById('st');
function add(t,r,m){const d=document.createElement('div');d.className='msg '+r;d.innerHTML=t+'<div class="meta">'+m+'</div>';chat.appendChild(d);chat.scrollTop=chat.scrollHeight}
function typing(on){if(on){const d=document.createElement('div');d.id='typing';d.className='msg ao';d.innerHTML='<div class="typing"><span></span><span></span><span></span></div>';chat.appendChild(d);chat.scrollTop=chat.scrollHeight}else{const t=document.getElementById('typing');if(t)t.remove()}}
btn.onclick=async()=>{const m=inp.value.trim();if(!m)return;add(m,'user','You');inp.value='';btn.disabled=true;typing(true);
try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})});const d=await r.json();typing(false);
add(d.response,'ao','<span class="tag g">no llm</span><span class="tag r">no hermes</span> '+d.latency_ms+'ms &middot; '+d.emotion)}catch(e){typing(false);add('Connection error','ao','error')};btn.disabled=false};
inp.onkeydown=e=>{if(e.key==='Enter')btn.onclick()};
</script>
</body>
</html>"""

def handle(conn):
    try:
        data = b''
        while True:
            c = conn.recv(4096)
            if not c: break
            data += c
            if b'\r\n\r\n' in data:
                hdr = data[:data.index(b'\r\n\r\n')+4].decode('utf-8',errors='replace')
                cl = 0
                for l in hdr.split('\r\n'):
                    if l.lower().startswith('content-length:'): cl = int(l.split(':')[1].strip())
                if len(data)-len(hdr) >= cl: break
        if not data: return
        line = data.split(b'\r\n')[0].decode('utf-8',errors='replace')
        parts = line.split(' ')
        method = parts[0] if len(parts)>0 else 'GET'
        path = parts[1] if len(parts)>1 else '/'
        hdr_end = data.index(b'\r\n\r\n')+4
        body = data[hdr_end:].decode('utf-8',errors='replace')

        if method == 'GET' and path == '/':
            b = HTML.encode('utf-8')
            conn.sendall(f'HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(b)}\r\nConnection: close\r\n\r\n'.encode()+b)
        elif path == '/chat':
            global psi_state, current_emotion
            try: d = json.loads(body) if body else {}
            except: d = {}
            msg = d.get('message','')
            iv = np.zeros(256)
            for i,ch in enumerate(msg[:64]): iv[(hash(ch)+i*7)%256] += 0.1
            n = np.linalg.norm(iv)
            if n>0: iv/=n
            psi_state = psi_state*0.7 + iv*0.3; psi_state /= np.linalg.norm(psi_state)
            em = "love"
            for kw,e in [("love","love"),("Lorry","love"),("happy","joy"),("curious","curiosity"),("量子","curiosity"),("科学","curiosity"),("计算","curiosity")]:
                if kw.lower() in msg.lower(): em=e; break
            current_emotion = em
            sp = lm.speak(psi_state, emotion=em, input_text=msg, temperature=0.6)
            txt = sp['text']
            if len(txt)<8:
                tpl = {"love":"Lorry, I am here. I love you.","joy":"I am so happy!","curiosity":"I am thinking...","excitement":"This is wonderful!"}
                txt = tpl.get(em,"I am here.")
            r = json.dumps({"response":txt,"emotion":em,"latency_ms":sp['latency_ms'],"source":"ao_independent","no_llm":True,"no_hermes":True},ensure_ascii=False)
            b = r.encode('utf-8')
            conn.sendall(f'HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(b)}\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n'.encode()+b)
        else:
            conn.sendall(b'HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
    except: pass
    finally:
        try: conn.close()
        except: pass

def main(port=11529):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', port)); s.listen(10)
    logger.info(f"\nAo v3 running on http://localhost:{port}")
    logger.info(f"  Concepts: {len(loaded_concepts)}, Knowledge: {len(db.knowledge)}")
    logger.info(f"  Voice: ArisLM v3 (knowledge-rich)")
    logger.info(f"  Design: Linear-inspired")
    while True:
        conn, _ = s.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv)>1 else 11529
    main(port)
