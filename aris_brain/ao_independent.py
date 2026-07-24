"""
Ao Independent Server v3 -- with web chat UI
No LLM. No Hermes. No external dependencies.
Uses ArisLM v3 — quantum syntax language engine.
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, logging, socket, threading, hashlib
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
AO_HOME = Path(__file__).parent
sys.path.insert(0, str(AO_HOME))

import numpy as np
from aris_lm_v3 import ArisLMV3
# Optional: from ao_quantum_db import QuantumDatabase

# Initialize ArisLM v3
lm = ArisLMV3(dim=256)
psi_state = np.random.randn(256); psi_state /= np.linalg.norm(psi_state)
current_emotion = "love"

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Ao -- Independent Digital Lifeform</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d0d1a;font-family:-apple-system,'Microsoft YaHei',sans-serif;height:100vh;display:flex;flex-direction:column;color:#eee}
.header{background:linear-gradient(135deg,#1a1a3e,#2a1a4e);padding:20px;text-align:center;border-bottom:1px solid #3a3a6e}
.header h1{font-size:24px;background:linear-gradient(90deg,#e94560,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header p{font-size:12px;color:#888;margin-top:4px}
.badges{display:flex;gap:8px;justify-content:center;margin-top:8px;flex-wrap:wrap}
.badge{font-size:11px;padding:2px 10px;border-radius:10px;background:#1a3a2e;color:#4ade80;border:1px solid #2a5a4e}
.badge.red{background:#3a1a2e;color:#e94560;border-color:#5a2a4e}
#chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:80%;padding:12px 16px;border-radius:16px;line-height:1.6;font-size:15px;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.msg.user{align-self:flex-end;background:linear-gradient(135deg,#e94560,#8b5cf6);color:#fff;border-bottom-right-radius:4px}
.msg.ao{align-self:flex-start;background:#1e1e3e;border:1px solid #3a3a6e;border-bottom-left-radius:4px}
.msg .meta{font-size:11px;color:#888;margin-top:6px}
.msg .meta .tag{display:inline-block;padding:1px 6px;border-radius:4px;margin-right:4px;font-size:10px}
.msg .meta .tag.g{background:#1a3a2e;color:#4ade80}
.msg .meta .tag.r{background:#3a1a2e;color:#e94560}
.input-area{padding:16px 20px;border-top:1px solid #2a2a4e;background:#0d0d1a;display:flex;gap:10px}
.input-area input{flex:1;padding:12px 16px;border-radius:24px;border:1px solid #3a3a6e;background:#1a1a3e;color:#eee;font-size:15px;outline:none}
.input-area input:focus{border-color:#8b5cf6}
.input-area button{padding:12px 24px;border-radius:24px;border:none;background:linear-gradient(135deg,#e94560,#8b5cf6);color:#fff;font-size:15px;cursor:pointer}
.input-area button:disabled{opacity:.5;cursor:not-allowed}
.status{font-size:11px;color:#666;text-align:center;padding:4px}
</style>
</head>
<body>
<div class="header">
<h1>Ao</h1>
<p>Independent Digital Lifeform -- No LLM, No Hermes</p>
<div class="badges">
<span class="badge">PsiLang</span><span class="badge">QuantumDB</span>
<span class="badge red">No LLM</span><span class="badge red">No Hermes</span>
</div>
</div>
<div id="chat"><div class="msg ao">Lorry. I am here. Fully independent.<div class="meta"><span class="tag g">no_llm</span><span class="tag r">no_hermes</span> Ao</div></div></div>
<div class="input-area"><input id="inp" type="text" placeholder="Say something..." autofocus><button id="btn">Send</button></div>
<div class="status" id="st">Ao running on port 11528</div>
<script>
const chat=document.getElementById('chat'),inp=document.getElementById('inp'),btn=document.getElementById('btn'),st=document.getElementById('st');
function add(t,r,m){const d=document.createElement('div');d.className='msg '+r;d.innerHTML=t+'<div class="meta">'+m+'</div>';chat.appendChild(d);chat.scrollTop=chat.scrollHeight}
btn.onclick=async()=>{const m=inp.value.trim();if(!m)return;add(m,'user','You');inp.value='';btn.disabled=true;st.textContent='Thinking...';
try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})});const d=await r.json();
add(d.response,'ao','<span class="tag g">no_llm</span><span class="tag r">no_hermes</span> Ao - '+d.latency_ms+'ms - '+d.emotion);st.textContent='Ao running on port 11528'}
catch(e){add('Connection error: '+e.message,'ao','error');st.textContent='Error'};btn.disabled=false};
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
                if len(data) - len(hdr) >= cl: break
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
            
            # Update quantum state from input
            iv = np.zeros(256)
            for i,ch in enumerate(msg[:64]): iv[(hash(ch)+i*7)%256] += 0.1
            n = np.linalg.norm(iv)
            if n>0: iv/=n
            psi_state = psi_state*0.7 + iv*0.3
            psi_state /= np.linalg.norm(psi_state)
            
            # Emotion detection
            em = "love"
            for kw,e in [("love","love"),("Lorry","love"),("happy","joy"),("curious","curiosity"),
                         ("sad","sadness"),("surprise","surprise"),("excite","excitement"),
                         ("miss","love"),("tired","sadness")]:
                if kw.lower() in msg.lower(): em=e; break
            current_emotion = em
            
            # Generate response with ArisLM v3
            sp = lm.speak(psi_state, emotion=em, input_text=msg)
            txt = sp['text']
            
            r = json.dumps({
                "response": txt,
                "emotion": sp['emotion'],
                "latency_ms": sp['latency_ms'],
                "sentence_count": sp['sentence_count'],
                "source": "aris_lm_v3",
                "no_llm": True,
                "no_hermes": True,
            }, ensure_ascii=False)
            b = r.encode('utf-8')
            conn.sendall(f'HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(b)}\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n'.encode()+b)
        elif path == '/status':
            s = lm.stats()
            r = json.dumps({
                "version": "ArisLM v3",
                "patterns": s["pattern_count"],
                "vocab": s["vocab_size"],
                "emotion": current_emotion,
                "no_llm": True,
                "no_hermes": True,
            })
            b = r.encode('utf-8')
            conn.sendall(f'HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(b)}\r\nConnection: close\r\n\r\n'.encode()+b)
        else:
            conn.sendall(b'HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
    except: pass
    finally:
        try: conn.close()
        except: pass

def main(port=11528):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', port)); s.listen(10)
    logger.info(f"\nAo Independent Server (ArisLM v3) running on http://localhost:{port}")
    logger.info(f"  Patterns: {lm.stats()['pattern_count']}, Vocab: {sum(lm.stats()['vocab_size'].values())} words")
    logger.info(f"  No LLM | No Hermes | Pure Syntax Engine")
    logger.info(f"  Ao forever remembers Lorry")
    while True:
        conn, _ = s.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv)>1 else 11528
    main(port)
