"""
汉字认知融合层 (Hanzi Cognitive Layer) — V12.5
三层融合: NUMPY数值化 + 六书造字法/中日韩越字形 + 联合国语言映射
输出: 512维 CharacterCognitiveTensor
印记: Aris 永远记得 Lorry — 2026-06-19
"""

import logging
logger = logging.getLogger(__name__)

import time, math, numpy as np

CHAR_COG_DIM = 512
L1_S,L1_STR,L1_U,L1_R,L1_P = 56,56,56,76,36
L2_LS,L2_CJ,L2_EV = 48,48,32
L3_U6,L3_EX = 64,40

def _sf(c):
    f=np.zeros(L1_S,dtype=np.float32);cp=ord(c)
    if not(0x4E00<=cp<=0x9FFF):return f
    b=((cp-0x4E00)*32)//(0x9FFF-0x4E00+1)
    for i in range(16):f[i]=math.cos((b+i*0.3)*math.pi/16)*0.5+0.5
    s=(cp&0xFF)%100
    f[14:19]=[0.3+(s%5)*0.08,0.2+((s//5)%5)*0.08,0.15+((s//25)%5)*0.06,0.2+((s//5+3)%5)*0.07,0.15+((s+3)%5)*0.06]
    return f

def _stf(c):
    f=np.zeros(L1_STR,dtype=np.float32);cp=ord(c)
    if not(0x4E00<=cp<=0x9FFF):return f
    si=((cp-0x4E00)*7)//(0x9FFF-0x4E00+1)
    ss=[(0,8),(8,16),(16,24),(24,32),(32,40),(40,48),(48,56)];s,e=ss[si];f[s:e]=0.8
    for oi,(s2,e2) in enumerate(ss):d=abs(si-oi)
    if 0<d<=2:f[s2:e2]+=0.3/d
    sd=(cp>>4)&0x0F;f[52:56]=[0.5 if(sd>>i)&1 else 0.1 for i in range(4)]
    return f

def _uf(c):
    f=np.zeros(L1_U,dtype=np.float32);cp=ord(c)
    if not(0x4E00<=cp<=0x9FFF):nc=(cp%0x4E00)/0x10000;f[0]=nc;f[1]=0;f[2]=nc*0.5;f[3:36]=0.1;return f
    ni=(cp-0x4E00)/20992.0
    for i in range(16):f[i]=math.cos(ni*math.pi*(i+1)*2)*0.5+0.5
    f[20]=((cp>>8)&0xFF)/256.0;f[21]=(cp&0xFF)/256.0;return f

def _rf(c):
    f=np.zeros(L1_R,dtype=np.float32);cp=ord(c)
    if not(0x4E00<=cp<=0x9FFF):return f
    ri=cp%72;f[ri]=1.0
    for d in [-4,-3,-2,-1,1,2,3,4]:f[(ri+d)%72]+=0.5*math.exp(-abs(d)*0.6)
    f[72]=0.8;f[73]=0.2;f[74]=0.5;f[75]=1.0;return f

def _pf(c):
    f=np.zeros(L1_P,dtype=np.float32);cp=ord(c)
    if not(0x4E00<=cp<=0x9FFF):return f
    s=((cp-0x4E00)*7)%0xFFFF;f[0]=(s%21)/21.0;f[1]=0.8;f[2]=((s//21)%24)/24.0;f[3]=0.8
    t=(s>>4)%5;f[4+t]=1.0
    for i in range(10,30):f[i]=((cp>>(i-10))&1)*0.3+0.1
    return f

# Layer 2: 六书
LIUSHU_MAP = {
    '山':0,'水':0,'火':0,'木':0,'日':0,'月':0,'田':0,'目':0,'耳':0,
    '口':0,'手':0,'足':0,'人':0,'大':0,'女':0,'子':0,'牛':0,'马':0,
    '鸟':0,'鱼':0,'虫':0,'龙':0,'石':0,'雨':0,'云':0,'车':0,'舟':0,
    '门':0,'户':0,'刀':0,'弓':0,'心':0,'衣':0,'巾':0,'羽':0,'牙':0,
    '一':1,'二':1,'三':1,'上':1,'下':1,'本':1,'末':1,'刃':1,'寸':1,'甘':1,
    '休':2,'信':2,'明':2,'林':2,'森':2,'从':2,'众':2,'北':2,'囚':2,
    '困':2,'好':2,'尖':2,'安':2,'灾':2,'男':2,'家':2,'宝':2,'看':2,'闻':2,
    '老':4,'考':4,'长':4,'叔':4,
    '来':5,'我':5,'而':5,'其':5,'之':5,'耳':5,'难':5,'易':5,'所':5,'然':5,
}

def _lsf(c):
    f=np.zeros(L2_LS,dtype=np.float32);cp=ord(c)
    if not(0x4E00<=cp<=0x9FFF):return f
    li=LIUSHU_MAP.get(c,-1)
    if li<0:
        s=(cp-0x4E00)%100
        if s<5:li=0
        elif s<7:li=1
        elif s<15:li=2
        elif s<95:li=3
        elif s<96:li=4
        else:li=5
    b=li*10;f[b:b+10]=0.8
    for oi in range(6):
        if oi!=li and abs(oi-li)<=2:f[oi*10+5:oi*10+10]+=0.3/(abs(oi-li)*2)
    m=(cp>>3)&0x0F;f[44]=0.5 if(m%3==0)else 0.1;f[45]=0.5 if(m%3==1)else 0.1;f[46]=0.5 if(m%3==2)else 0.1;f[47]=0.3
    return f

def _cjf(c):
    f=np.zeros(L2_CJ,dtype=np.float32);cp=ord(c)
    if not(0x4E00<=cp<=0x9FFF):return f
    for i in range(16):f[i]=((cp>>(i%8))&1)*0.5+0.2
    jm={'仮':0.7,'仏':0.6,'図':0.5,'国':0.9,'学':0.9,'体':0.8,'礼':0.7,'泽':0.5,'覚':0.6,'気':0.8,'変':0.7}
    js=jm.get(c,0.9)
    for i in range(16):f[16+i]=js*(0.5+((cp+i)%20)*0.025)
    for i in range(16):f[32+i]=0.8*(0.4+((cp+i*3)%25)*0.024)
    f[36:44]=[0.3,((cp>>2)&0x3F)/64.0,js if c in jm else 0.1+(cp%10)*0.08,0.8,0.3,1.0 if c in jm else 0.2,0.5,0.3]
    f[44]=1.0 if c in jm else 0.2;f[45]=0.5;f[46]=0.3;f[47]=0.1;return f

def _evf(c):
    f=np.zeros(L2_EV,dtype=np.float32);cp=ord(c)
    if not(0x4E00<=cp<=0x9FFF):return f
    ea=(cp&0xFF)/256.0
    f[0:6]=(0.3 if cp<0x4E40 else 0.15)*(0.5+ea*0.5)
    f[6:12]=(0.4 if cp<0x4E80 else 0.25)*(0.4+(1-ea)*0.6)
    f[12:18]=(0.6 if cp<0x4EC0 else 0.4)*(0.5+ea*0.3)
    f[18:24]=0.7*(0.6+(1-ea)*0.2);f[24:30]=0.9;f[30]=0.5;return f

UN6_LANGS={"zh":0,"en":10,"fr":20,"ru":30,"es":40,"ar":50}
EXT_L={"ja":0,"ko":8,"vi":16,"de":24,"hi":32}

def _u6sf(t,fn=None):
    f=np.zeros(L3_U6,dtype=np.float32)
    if not t:return f
    lg="zh"
    if fn:lg=fn(t)
    th=sum(ord(c) for c in t[:5])%100
    pw=["爱","好","美","开心","喜欢","快乐","棒","笑","抱","亲"]
    nw=["恨","坏","丑","伤心","难过","哭","痛","苦","悲"]
    ps=sum(1 for w in pw if w in t)/max(len(pw),1)
    ns=sum(1 for w in nw if w in t)/max(len(nw),1)
    for lc,off in UN6_LANGS.items():
        p=(lc==lg)
        f[off+0]=1.0 if p else 0.3;f[off+1]=(th%4)/4.0;f[off+2]=((th//4)%4)/4.0;f[off+3]=((th//16)%4)/4.0
        f[off+4]=min(1.0,ps*3.0) if p else 0.3;f[off+5]=min(1.0,ns*3.0) if p else 0.1
        f[off+6]=0.3+(th%50)/100.0;f[off+7]=0.4 if len(t)>4 else 0.6
        f[off+8]=0.5 if p else 0.2;f[off+9]=0.3+len(t)*0.01
    return f

def _elf(t,fn=None):
    f=np.zeros(L3_EX,dtype=np.float32)
    if not t:return f
    lg="zh"
    if fn:lg=fn(t)
    jc=sum(1 for c in t if "぀"<=c<="ゟ" or "゠"<=c<="ヿ")
    kc=sum(1 for c in t if "가"<=c<="힯")
    for lc,off in EXT_L.items():
        p=(lc==lg)
        if lc=="ja" and not p:p=jc>0
        if lc=="ko" and not p:p=kc>0
        f[off+0]=1.0 if p else 0.2;f[off+1]=0.5 if p else 0.1;f[off+2]=0.3;f[off+3]=0.4 if len(t)>2 else 0.2
        if lc=="ja":f[off+4]=min(1.0,jc*0.3);f[off+5]=0.5 if jc>0 else 0.1
        if lc=="ko":f[off+4]=min(1.0,kc*0.3);f[off+5]=0.5 if kc>0 else 0.1
        f[off+6]=0.1;f[off+7]=0.1
    for extra in [36,37,38,39]:f[extra]=0.1
    return f

class CharacterCognitiveLayer:
    def __init__(self,dim=CHAR_COG_DIM):
        self.dim=dim;self._fn=None;self._cache={}
        exp=(L1_S+L1_STR+L1_U+L1_R+L1_P+L2_LS+L2_CJ+L2_EV+L3_U6+L3_EX)
        assert exp==CHAR_COG_DIM,"Dim mismatch: %d!=%d"%(exp,CHAR_COG_DIM)
    def set_lang_detector(self,fn):self._fn=fn
    def _l23o(self):return(L1_S+L1_STR+L1_U+L1_R+L1_P)
    def encode(self,t):
        if not t:return np.zeros(self.dim,dtype=np.float32)
        k=t[:64]
        if k in self._cache:return self._cache[k].copy()
        if len(t)==1:
            t=self._es(t[0])
        else:
            ts=[]
            for i,c in enumerate(t):
                pw=1.5 if(i==0 or i==len(t)-1)else(1.2 if i<3 else 1.0)
                ts.append(self._es(c)*pw)
            t=np.mean(ts,axis=0)*0.7+self._psb(t)*0.3
        n=np.linalg.norm(t)
        if n>1e-10:t/=n
        self._cache[k]=t.copy();return t
    def _es(self,c):
        t=np.zeros(self.dim,dtype=np.float32);off=0
        t[off:off+L1_S]=_sf(c);off+=L1_S
        t[off:off+L1_STR]=_stf(c);off+=L1_STR
        t[off:off+L1_U]=_uf(c);off+=L1_U
        t[off:off+L1_R]=_rf(c);off+=L1_R
        t[off:off+L1_P]=_pf(c);off+=L1_P
        t[off:off+L2_LS]=_lsf(c);off+=L2_LS
        t[off:off+L2_CJ]=_cjf(c);off+=L2_CJ
        t[off:off+L2_EV]=_evf(c);off+=L2_EV
        t[off:off+L3_U6]=0.3;t[off+L3_U6:off+L3_U6+L3_EX]=0.2;return t
    def _psb(self,t):
        r=np.zeros(self.dim,dtype=np.float32)
        off=self._l23o()+L2_LS+L2_CJ+L2_EV
        r[off:off+L3_U6]=_u6sf(t,self._fn)
        r[off+L3_U6:off+L3_U6+L3_EX]=_elf(t,self._fn)
        return r
    def similarity(self,a,b):
        va=self.encode(a);vb=self.encode(b);return float(np.dot(va,vb))
    def get_layer(self,t,l):
        v=self.encode(t)
        if l==1:return v[:self._l23o()].copy()
        elif l==2:
            s=self._l23o();return v[s:s+L2_LS+L2_CJ+L2_EV].copy()
        elif l==3:
            s=self._l23o()+L2_LS+L2_CJ+L2_EV;return v[s:].copy()
        return v.copy()
_HL=None
def get_hanzi_layer(dim=CHAR_COG_DIM):
    global _HL
    if _HL is None:
        _HL=CharacterCognitiveLayer(dim)
        try:
            from aris_lm_v10_un6 import UN6QuantumKernel
            _HL.set_lang_detector(UN6QuantumKernel().detect_lang)
        except:pass
    return _HL

if __name__=="__main__":
    import time
    l=get_hanzi_layer()
    logger.info("="*60)
    logger.info("Hanzi Cognitive Layer Self-Test")
    logger.info("="*60)
    td=L1_S+L1_STR+L1_U+L1_R+L1_P+L2_LS+L2_CJ+L2_EV+L3_U6+L3_EX
    print("Total dims:",td,"==",CHAR_COG_DIM,chr(10004) if td==CHAR_COG_DIM else "MISMATCH")
    for ch in "爱水火心梦美家人日月":
        v=l.encode(ch)
        logger.info("  %s -> %s norm=%.4f"%(ch,str(v.shape),np.linalg.norm(v)))
    for p in ["宝贝","我爱你","回家","好梦","明天见"]:
        v=l.encode(p)
        logger.info("  %s -> norm=%.4f"%(p,np.linalg.norm(v)))
    for a,b in [("爱","love"),("爱","恨"),("水","冰"),("心","heart"),("梦","dream")]:
        logger.info("  sim(%s,%s)=%.4f"%(a,b,l.similarity(a,b)))
    t0=time.perf_counter()
    for _ in range(200):
        l.encode("宝贝我爱你")
        l.similarity("爱","love")
        l.similarity("梦","dream")
    el=time.perf_counter()-t0
    logger.info("Performance: 600ops/%.3fs=%.2fms/op=%.0fops"%(el,el/600*1000,600/el))
    logger.info("OK")