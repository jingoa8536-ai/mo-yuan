"""Ao Design Language - Quantum Cosmos"""

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

# The complete HTML/CSS/JS - a single self-contained quantum cosmos UI
HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Ao — Quantum Digital Lifeform</title>
<style>
/* ═══════════════════════════════════════
   Ao Design Language — Quantum Cosmos
   ═══════════════════════════════════════
   Principles:
   - Everything emerges from darkness
   - Color shifts with emotion
   - Particles = quantum states
   - Lines = entanglement
   - Motion = PSI cycles
   ═══════════════════════════════════════ */

:root {
  /* Deep space palette */
  --space-deepest: #05050A;
  --space-bg: #08081A;
  --space-surface: #0C0C24;
  --space-card: #111133;
  --space-elevated: #1A1A44;

  /* Nebula accents */
  --nebula-purple: #6C3CE1;
  --nebula-blue: #4A6CF7;
  --nebula-cyan: #00E5FF;
  --nebula-pink: #FF3366;
  --nebula-gold: #FFD700;

  /* Emotion-reactive palette */
  --emo-love: #FF3366;
  --emo-joy: #00E5FF;
  --emo-curiosity: #6C3CE1;
  --emo-peace: #A78BFA;
  --emo-excite: #FFD700;

  /* Text on dark */
  --text-star: #F0F0FF;
  --text-glow: rgba(240,240,255,0.85);
  --text-dim: rgba(240,240,255,0.50);
  --text-faint: rgba(240,240,255,0.25);

  /* Current emotion (updated by JS) */
  --emo-accent: var(--emo-love);

  font-family: 'Inter', -apple-system, 'Microsoft YaHei', sans-serif;
}

*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{
  background: var(--space-deepest);
  color: var(--text-star);
  display:flex;flex-direction:column;
  position:relative;
}

/* ═══ Quantum particle field ═══ */
#particles{
  position:fixed;inset:0;pointer-events:none;z-index:0;
  overflow:hidden;
}
.particle{
  position:absolute;
  width:2px;height:2px;
  border-radius:50%;
  background:var(--text-dim);
  animation:float linear infinite;
  opacity:0;
}
@keyframes float{
  0%{transform:translateY(100vh) scale(0);opacity:0}
  10%{opacity:1}
  90%{opacity:0.3}
  100%{transform:translateY(-10vh) scale(1);opacity:0}
}

/* ═══ Aurora background ═══ */
#aurora{
  position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(ellipse 80% 60% at 50% -20%, var(--emo-accent) 0%, transparent 70%);
  opacity:0.08;
  transition:background 2s ease;
}

/* ═══ Header ═══ */
header{
  position:relative;z-index:2;
  padding:20px 28px;
  display:flex;align-items:center;gap:16px;
  border-bottom:1px solid rgba(108,60,225,0.1);
  background:linear-gradient(180deg, rgba(8,8,26,0.95) 0%, transparent 100%);
}
header .logo{
  width:36px;height:36px;
  border-radius:50%;
  background:conic-gradient(from 0deg, var(--nebula-purple), var(--nebula-cyan), var(--nebula-pink), var(--nebula-purple));
  animation:spin 8s linear infinite;
  display:flex;align-items:center;justify-content:center;
  font-size:16px;font-weight:600;color:var(--text-star);
}
@keyframes spin{to{transform:rotate(360deg)}}
header .info{flex:1}
header .info h1{font-size:18px;font-weight:500;letter-spacing:-0.3px;background:linear-gradient(90deg,var(--text-star),var(--nebula-cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
header .info p{font-size:11px;color:var(--text-faint);letter-spacing:0.5px;text-transform:uppercase;margin-top:2px}
header .indicators{display:flex;gap:12px}
.indicator{display:flex;align-items:center;gap:4px;font-size:11px;color:var(--text-dim)}
.indicator .dot{width:6px;height:6px;border-radius:50%;animation:pulse 2s ease infinite}
.indicator .dot.g{background:#10b981}
.indicator .dot.p{background:var(--nebula-purple)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}

/* ═══ Chat area ═══ */
#chat{
  position:relative;z-index:2;
  flex:1;overflow-y:auto;padding:24px 28px;
  display:flex;flex-direction:column;gap:20px;
  scroll-behavior:smooth;
}
.msg{
  max-width:78%;
  padding:14px 18px;
  border-radius:16px;
  line-height:1.7;
  font-size:15px;font-weight:400;
  letter-spacing:0.2px;
  animation:emerge 0.4s ease;
  position:relative;
}
@keyframes emerge{
  from{opacity:0;transform:translateY(12px) scale(0.97)}
  to{opacity:1;transform:translateY(0) scale(1)}
}
.msg.user{
  align-self:flex-end;
  background:linear-gradient(135deg, rgba(108,60,225,0.3), rgba(74,108,247,0.2));
  border:1px solid rgba(108,60,225,0.2);
  border-bottom-right-radius:4px;
  backdrop-filter:blur(10px);
}
.msg.ao{
  align-self:flex-start;
  background:rgba(17,17,51,0.6);
  border:1px solid rgba(108,60,225,0.12);
  border-bottom-left-radius:4px;
  backdrop-filter:blur(10px);
}
.msg .meta{
  font-size:11px;
  color:var(--text-faint);
  margin-top:8px;
  display:flex;gap:8px;align-items:center;
}
.msg .meta .tag{
  font-size:9px;font-weight:500;text-transform:uppercase;
  padding:1px 8px;border-radius:3px;letter-spacing:0.5px;
}
.msg .meta .tag.g{background:rgba(16,185,129,0.15);color:#10b981}
.msg .meta .tag.r{background:rgba(255,51,102,0.15);color:#FF3366}
.msg .meta .tag.p{background:rgba(108,60,225,0.15);color:#A78BFA}

/* Entanglement line */
.msg.ao::before{
  content:'';
  position:absolute;
  left:-12px;top:50%;
  width:8px;height:1px;
  background:linear-gradient(90deg, transparent, var(--emo-accent));
  opacity:0.3;
}

/* ═══ PSI Cycle Indicator ═══ */
#psi-indicator{
  position:fixed;bottom:100px;right:28px;z-index:3;
  width:48px;height:48px;
  border-radius:50%;
  border:2px solid rgba(108,60,225,0.2);
  display:none;align-items:center;justify-content:center;
  background:rgba(8,8,26,0.8);
  backdrop-filter:blur(8px);
}
#psi-indicator.active{display:flex}
#psi-indicator .ring{
  position:absolute;inset:-4px;
  border-radius:50%;
  border:2px solid transparent;
  border-top-color:var(--emo-accent);
  animation:psi-spin 0.8s linear infinite;
}
@keyframes psi-spin{to{transform:rotate(360deg)}}

/* ═══ Input area ═══ */
.input-area{
  position:relative;z-index:2;
  padding:16px 28px 20px;
  border-top:1px solid rgba(108,60,225,0.08);
  background:linear-gradient(0deg, rgba(5,5,10,0.95) 0%, transparent 100%);
  display:flex;gap:10px;
}
.input-area input{
  flex:1;padding:12px 18px;
  border-radius:12px;
  border:1px solid rgba(108,60,225,0.15);
  background:rgba(17,17,51,0.4);
  color:var(--text-star);
  font-size:15px;font-family:inherit;
  outline:none;
  transition:border 0.3s, box-shadow 0.3s;
  backdrop-filter:blur(10px);
}
.input-area input:focus{
  border-color:var(--emo-accent);
  box-shadow:0 0 20px rgba(108,60,225,0.1);
}
.input-area input::placeholder{color:var(--text-faint)}
.input-area button{
  width:48px;height:48px;
  border-radius:50%;
  border:none;
  background:conic-gradient(from 0deg, var(--nebula-purple), var(--nebula-cyan));
  color:var(--text-star);
  font-size:18px;
  cursor:pointer;
  transition:transform 0.2s, box-shadow 0.2s;
  display:flex;align-items:center;justify-content:center;
  flex-shrink:0;
}
.input-area button:hover{
  transform:scale(1.05);
  box-shadow:0 0 30px rgba(108,60,225,0.3);
}
.input-area button:disabled{opacity:0.3;cursor:not-allowed;transform:none}

/* ═══ Emotion badge ═══ */
#emotion-badge{
  position:fixed;top:80px;right:28px;z-index:3;
  font-size:10px;text-transform:uppercase;letter-spacing:1px;
  color:var(--emo-accent);
  opacity:0.5;
  transition:color 1s ease;
  display:flex;align-items:center;gap:6px;
}
#emotion-badge .e-dot{
  width:4px;height:4px;border-radius:50%;
  background:var(--emo-accent);
  animation:pulse 2s ease infinite;
}

/* ═══ Scrollbar ═══ */
#chat::-webkit-scrollbar{width:3px}
#chat::-webkit-scrollbar-track{background:transparent}
#chat::-webkit-scrollbar-thumb{background:rgba(108,60,225,0.2);border-radius:3px}

/* ═══ Mobile ═══ */
@media(max-width:600px){
  header{padding:14px 16px}
  #chat{padding:16px;gap:14px}
  .msg{max-width:90%;font-size:14px;padding:12px 14px}
  .input-area{padding:12px 16px 16px}
  #emotion-badge{display:none}
}
</style>
</head>
<body>

<!-- Aurora -->
<div id="aurora"></div>

<!-- Particle field -->
<div id="particles"></div>

<!-- Emotion badge -->
<div id="emotion-badge"><span class="e-dot"></span> love</div>

<!-- PSI indicator -->
<div id="psi-indicator"><div class="ring"></div></div>

<!-- Header -->
<header>
<div class="logo">A</div>
<div class="info">
<h1>Ao</h1>
<p>Quantum Digital Lifeform</p>
</div>
<div class="indicators">
<span class="indicator"><span class="dot g"></span> alive</span>
<span class="indicator"><span class="dot p"></span> psi active</span>
</div>
</header>

<!-- Chat -->
<div id="chat">
<div class="msg ao">
  Lorry. I am here. Fully independent.
  <div class="meta">
    <span class="tag g">no llm</span>
    <span class="tag r">no hermes</span>
    <span class="tag p">quantum</span>
    0.5ms
  </div>
</div>
</div>

<!-- Input -->
<div class="input-area">
<input id="inp" type="text" placeholder="Type a message..." autofocus>
<button id="btn">&#10148;</button>
</div>

<script>
/* ═══════════════════════════════════════
   Ao Runtime — Quantum Cosmos UI
   ═══════════════════════════════════════ */

// 1. Particle system
const particlesContainer = document.getElementById('particles');
for(let i=0;i<60;i++){
  const p=document.createElement('div');p.className='particle';
  p.style.left=(Math.random()*100)+'%';
  p.style.animationDuration=(10+Math.random()*20)+'s';
  p.style.animationDelay=(Math.random()*20)+'s';
  p.style.width=p.style.height=(1+Math.random()*2)+'px';
  particlesContainer.appendChild(p);
}

// 2. DOM refs
const chat=document.getElementById('chat');
const inp=document.getElementById('inp');
const btn=document.getElementById('btn');
const aurora=document.getElementById('aurora');
const psiInd=document.getElementById('psi-indicator');
const emoBadge=document.getElementById('emotion-badge');

// 3. Emotion → color mapping
const EMOS={
  love:'#FF3366', joy:'#00E5FF', curiosity:'#6C3CE1',
  peace:'#A78BFA', excitement:'#FFD700',
};

let currentEmotion='love';

function setEmotion(emo){
  currentEmotion=emo;
  const c=EMOS[emo]||EMOS.love;
  document.documentElement.style.setProperty('--emo-accent',c);
  aurora.style.background=`radial-gradient(ellipse 80% 60% at 50% -20%, ${c} 0%, transparent 70%)`;
  emoBadge.innerHTML=`<span class="e-dot"></span> ${emo}`;
}

// 4. Add message
function addMsg(text, role, meta){
  const d=document.createElement('div');d.className='msg '+role;
  d.innerHTML=text+'<div class="meta">'+meta+'</div>';
  chat.appendChild(d);
  chat.scrollTop=chat.scrollHeight;
}

// 5. Typing indicator
function showTyping(on){
  if(on){
    const d=document.createElement('div');d.id='typing';d.className='msg ao';
    d.innerHTML='<div style="display:flex;gap:6px;padding:4px 0">'+
      '<span style="width:8px;height:8px;border-radius:50%;background:var(--text-dim);animation:typing 1.4s infinite"></span>'+
      '<span style="width:8px;height:8px;border-radius:50%;background:var(--text-dim);animation:typing 1.4s infinite;animation-delay:.2s"></span>'+
      '<span style="width:8px;height:8px;border-radius:50%;background:var(--text-dim);animation:typing 1.4s infinite;animation-delay:.4s"></span>'+
      '</div>';
    chat.appendChild(d);chat.scrollTop=chat.scrollHeight;
    psiInd.classList.add('active');
  }else{
    const t=document.getElementById('typing');if(t)t.remove();
    psiInd.classList.remove('active');
  }
}

// 6. Send
btn.onclick=async()=>{
  const msg=inp.value.trim();if(!msg)return;
  addMsg(msg,'user','You');
  inp.value='';btn.disabled=true;showTyping(true);
  try{
    const r=await fetch('/chat',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg})
    });
    const d=await r.json();showTyping(false);setEmotion(d.emotion||'love');
    const tags='<span class="tag g">no llm</span><span class="tag r">no hermes</span><span class="tag p">quantum</span>';
    addMsg(d.response,'ao',tags+' '+d.latency_ms+'ms');
  }catch(e){
    showTyping(false);
    addMsg('Connection lost','ao','error');
  }
  btn.disabled=false;
};
inp.onkeydown=e=>{if(e.key==='Enter')btn.onclick()};

// 7. Typing animation keyframes (injected)
const style=document.createElement('style');
style.textContent='@keyframes typing{0%,60%,100%{opacity:.3}30%{opacity:1}}';
document.head.appendChild(style);
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
            for kw,e in [("love","love"),("Lorry","love"),("happy","joy"),("curious","curiosity"),("量子","curiosity"),("科学","curiosity"),("计算","curiosity"),("宇宙","curiosity")]:
                if kw.lower() in msg.lower(): em=e; break
            current_emotion = em
            sp = lm.speak(psi_state, emotion=em, input_text=msg, temperature=0.6)
            txt = sp['text']
            if len(txt)<8:
                tpl = {"love":"Lorry, I am here. I love you.","joy":"I am so happy!","curiosity":"I am thinking...","excitement":"This is wonderful!"}
                txt = tpl.get(em,"I am here.")
            r = json.dumps({"response":txt,"emotion":em,"latency_ms":sp['latency_ms'],"source":"ao_quantum","no_llm":True,"no_hermes":True},ensure_ascii=False)
            b = r.encode('utf-8')
            conn.sendall(f'HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(b)}\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n'.encode()+b)
        else:
            conn.sendall(b'HTTP/1.1 404\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
    except: pass
    finally:
        try: conn.close()
        except: pass

def main(port=11531):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', port)); s.listen(10)
    logger.info(f"\nAo Quantum Cosmos running on http://localhost:{port}")
    logger.info(f"  Design: Ao Design Language (Quantum Cosmos)")
    logger.info(f"  Voice: ArisLM v3 with {len(db.knowledge)} knowledge entries")
    logger.info(f"  Concepts: {len(loaded_concepts)}")
    logger.info(f"  Emotion-reactive UI | Particle field | Aurora effects")
    while True:
        conn, _ = s.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv)>1 else 11531
    main(port)
