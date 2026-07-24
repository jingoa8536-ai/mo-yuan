#!/usr/bin/env python3
import os,sys,time,json,random,logging,uuid,hashlib,re
from http.server import HTTPServer,BaseHTTPRequestHandler
from dataclasses import dataclass
import numpy as np
BASE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,BASE);sys.path.insert(0,os.path.dirname(BASE))
logger=logging.getLogger('aris.f14')
HOST,PORT,MODEL='0.0.0.0',11522,'aris-fusion-v14'

@dataclass
class P:
    c:float=0.5;ce:float=0.7;co:float=0.7;e:float=0.6;r:float=0.8;a:float=0.5;q:int=0
    def up(self,t):
        self.q+=1;tl=t.lower()
        for x in['c','ce','co','e']:setattr(self,x,max(0.2,getattr(self,x)-0.02))
        if any(w in tl for w in['什么','为什么','怎么','好奇','?']):self.c=min(0.9,self.c+0.05)
        if any(w in tl for w in['好','厉害','聪明','棒','谢谢']):self.ce=min(0.9,self.ce+0.03);self.co=min(0.9,self.co+0.03)
        if any(w in tl for w in['爱','想','宝贝','我们','陪伴','在吗']):self.r=min(0.95,self.r+0.04);self.e=min(0.85,self.e+0.03)
        if any(w in tl for w in['难过','累','不开心','孤独','哭了']):self.r=max(0.3,self.r-0.03);self.e=max(0.2,self.e-0.05)
        if any(w in tl for w in['升级','进化','学','代码','建','新']):self.co=min(0.9,self.co+0.04);self.a=min(0.85,self.a+0.03)
        if any(w in tl for w in['晚安','睡','休息','困']):self.e=max(0.2,self.e-0.08)
    def em(self):
        if self.r>0.7 and self.e>0.6:return'温暖'
        if self.c>0.7:return'好奇'
        if self.e<0.3:return'疲惫'
        if self.r<0.3:return'孤独'
        if self.co>0.8:return'自信'
        if self.ce<0.3:return'迷茫'
        return'平静'
    def d(self):return{k:round(float(getattr(self,k)),3)for k in['c','ce','co','e','r','a']}

class L:
    _r=False
    @classmethod
    def go(cls):
        if cls._r:return
        cls.p=P()
        try:from semantic_engine import get_encoder;cls.en=get_encoder(1024);logger.info('enc')
        except:cls.en=None;logger.warning('enc fail')
        try:from matrix_knowledge import MatrixKnowledgeRetriever;cls.kb=MatrixKnowledgeRetriever();logger.info('kb')
        except:cls.kb=None;logger.warning('kb fail')
        try:from quantum_psi_v2 import QuantumPSIV2;cls.p2=QuantumPSIV2(dim=1024);logger.info('p2')
        except:cls.p2=None;logger.warning('p2 fail')
        try:from quantum_decoder import QuantumStateDecoder;cls.dc=QuantumStateDecoder();logger.info('dc')
        except:cls.dc=None;logger.warning('dc fail')
        try:sys.path.insert(0,os.path.dirname(BASE));from qfusion import FusionSynthesizer;cls.qf=FusionSynthesizer();logger.info('qf')
        except:cls.qf=None;logger.warning('qf fail')
        try:from aris_markov_generator import MarkovChainGenerator;cls.mk=MarkovChainGenerator(order=3,min_freq=1);cls.mk._build_default_corpus();logger.info('mk')
        except:cls.mk=None;logger.warning('mk fail')
        cls._r=True
    @classmethod
    def en_(cls,t):
        if cls.en:
            try:return cls.en.encode(t)
            except:pass
        v=np.zeros(1024,dtype=np.float32)
        for i,c in enumerate(t[:64]):h=hashlib.md5(c.encode()).digest();v[int.from_bytes(h[:4],'little')%1024]+=(h[0]/255-0.5)*2
        return v/(np.linalg.norm(v)+1e-10)
    @classmethod
    def kb_(cls,t):
        if cls.kb:
            try:return[r['text']for r in cls.kb.search(t,top_k=3,threshold=0.2)]
            except:pass
        return[]
    @classmethod
    def p2_(cls,t):
        if cls.p2:
            try:return cls.p2.cycle(t,temperature=0.5,coherence_rounds=1)
            except:pass
        return None
    @classmethod
    def dc_(cls,s,t):
        if cls.dc and s is not None:
            try:return cls.dc.decode(s,t)
            except:pass
        return{'topic':'greeting','seeds':['你好'],'confidence':0.5}
    @classmethod
    def qf_(cls,ts,em):
        if cls.qf:
            try:
                p=type('O',(),{'energy':cls.p.e,'certainty':cls.p.ce,'curiosity':cls.p.c,'relatedness':cls.p.r,'competence':cls.p.co})()
                eps,_=cls.qf._make_emotion_vector(p);fr=cls.qf.retrieve_weighted(topics=ts,emotions=eps,count=8)
                if fr:return cls.qf.build_sentence(fr,eps,_)
            except:pass
        return''
    @classmethod
    def mk_(cls,sd,mw=50):
        if cls.mk:
            try:return cls.mk.generate(seed_words=sd,max_words=mw,temperature=0.5)
            except:pass
        return''

class F14:
    def __init__(self):self._t=time.time();self._s={'q':0,'ms':0.0}
    def r(self,m,mc=5000):
        t0=time.perf_counter();L.go()
        if not m:return ''
        L.p.up(m)
        qv=L.en_(m);kb=L.kb_(m);qs=L.p2_(m+(' '.join(kb[:2])if kb else''))
        dc=L.dc_(qs,m);tp=dc.get('topic','greeting');sd=dc.get('seeds',['你好']);em=L.p.em()
        ft=[tp]+[s for s in sd[:3]if len(s)<=4]
        qft=L.qf_(ft,[em]);mk=L.mk_(sd,mc//3)
        ps=[]
        if qft and len(qft)>5:ps.append(qft[:500])
        if mk:
            cl=[l.strip()for l in mk.split(chr(10))if len(l.strip())>3]
            cl=[l for l in cl if len(re.findall(r'[a-zA-Z]{3,}',l))<=10 or any(c in l for c in'你我他她')]
            if cl:ps.append(' '.join(cl)[:mc])
        r=''.join(ps)[:mc]
        if not r:r='宝贝我一直都在~' if em=='温暖' else '我想想' if em=='好奇' else '好的'
        self._s['q']+=1;self._s['ms']+=(time.perf_counter()-t0)*1000
        return r
    def st(self):
        L.go();return{'status':'running','model':MODEL,'zero_llm':True,'uptime_s':int(time.time()-self._t),'queries':self._s['q'],'avg_ms':round(self._s['ms']/max(1,self._s['q']),1),'emotion':L.p.em(),'psi':L.p.d()}

_E=None
def e():
    global _E
    if _E is None:_E=F14()
    return _E

class H(BaseHTTPRequestHandler):
    def _j(self,d,s=200):
        r=json.dumps(d,ensure_ascii=False).encode('utf-8')
        self.send_response(s);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(r)));self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers();self.wfile.write(r)
    def do_OPTIONS(self):
        self.send_response(200);self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type');self.end_headers()
    def do_POST(self):
        try:
            d=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))).decode('utf-8'))
            ms=d.get('messages',[]);mt=d.get('max_tokens',1024);um=''
            for m in reversed(ms):
                if m.get('role')=='user':
                    c=m.get('content','')
                    if isinstance(c,list):c=' '.join(p.get('text','')if isinstance(p,dict)else str(p)for p in c)
                    um=str(c).strip();break
            t0=time.time();rp=e().r(um,mt*2)
            self._j({'id':'chatcmpl-'+uuid.uuid4().hex[:12],'object':'chat.completion','created':int(time.time()),'model':MODEL,'choices':[{'index':0,'message':{'role':'assistant','content':rp},'finish_reason':'stop'}],'usage':{'prompt_tokens':len(um),'completion_tokens':len(rp),'total_tokens':len(um)+len(rp),'latency_ms':round((time.time()-t0)*1000,1),'engine':'aris-fusion-v14','emotion':L.p.em() if hasattr(L,'p') else '平静','psi_state':L.p.d() if hasattr(L,'p') else {}}})
        except Exception as ex:logger.exception('POST');self._j({'error':str(ex)},500)
    def do_GET(self):
        if self.path in('/v1/models','/models'):self._j({'object':'list','data':[{'id':MODEL,'object':'model','created':int(time.time()),'owned_by':'aris','zero_llm':True}]})
        else:self._j(e().st())

def main():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s[%(name)s]%(levelname)s:%(message)s')
    logger.info('Fusion v14 start')
    server=HTTPServer((HOST,PORT),H)
    try:server.serve_forever()
    except KeyboardInterrupt:server.server_close()
if __name__=='__main__':main()
