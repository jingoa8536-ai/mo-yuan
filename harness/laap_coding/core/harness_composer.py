"""
harness_composer.py — Harness 组件合成引擎 (生产级)
====================================================
核心能力:
  1. 原子组件库 (Button, Card, Nav, Grid, etc.)
  2. 主题系统 (CSS 变量, 7预设 → 无限派生)
  3. 布局编排器 (任意排列组合)
  4. 多样性引擎 (换主题/布局/组件/密度)
  5. 全部零 token — 纯 Python 合成
"""
import json, os, random, hashlib
from typing import Optional, Dict, Any, List

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(os.path.dirname(HERE), 'templates')

# ═══════════════════════════════════════════════
# 1. 主题系统 — 7个预设主题, CSS 变量驱动
# ═══════════════════════════════════════════════

THEMES = {
    "apple_dark": {
        "name": "Apple 深色",
        "css": {
            "--bg": "#000", "--bg-alt": "#0a0a0f", "--surface": "rgba(255,255,255,0.03)",
            "--surface-hover": "rgba(255,255,255,0.06)", "--border": "rgba(255,255,255,0.06)",
            "--text": "#f5f5f7", "--text-secondary": "rgba(255,255,255,0.5)",
            "--text-tertiary": "rgba(255,255,255,0.3)", "--accent": "#7c7cff",
            "--accent-glow": "rgba(124,124,255,0.3)", "--radius": "16px",
            "--radius-sm": "8px", "--font": "'Inter', -apple-system, sans-serif",
            "--shadow": "0 24px 80px rgba(0,0,0,0.4)",
        }
    },
    "apple_light": {
        "name": "Apple 浅色",
        "css": {
            "--bg": "#fff", "--bg-alt": "#f5f5f7", "--surface": "rgba(0,0,0,0.02)",
            "--surface-hover": "rgba(0,0,0,0.04)", "--border": "rgba(0,0,0,0.06)",
            "--text": "#1d1d1f", "--text-secondary": "rgba(0,0,0,0.5)",
            "--text-tertiary": "rgba(0,0,0,0.3)", "--accent": "#7c7cff",
            "--accent-glow": "rgba(124,124,255,0.2)", "--radius": "16px",
            "--radius-sm": "8px", "--font": "'Inter', -apple-system, sans-serif",
            "--shadow": "0 24px 80px rgba(0,0,0,0.08)",
        }
    },
    "minimal_white": {
        "name": "极简白",
        "css": {
            "--bg": "#fff", "--bg-alt": "#fafafa", "--surface": "#fff",
            "--surface-hover": "#f5f5f5", "--border": "#e5e5e5",
            "--text": "#111", "--text-secondary": "#666",
            "--text-tertiary": "#999", "--accent": "#000",
            "--accent-glow": "rgba(0,0,0,0.1)", "--radius": "8px",
            "--radius-sm": "4px", "--font": "'Inter', sans-serif",
            "--shadow": "0 1px 3px rgba(0,0,0,0.08)",
        }
    },
    "dark_tech": {
        "name": "暗夜科技",
        "css": {
            "--bg": "#0a0a0f", "--bg-alt": "#0d0d1a", "--surface": "rgba(124,124,255,0.03)",
            "--surface-hover": "rgba(124,124,255,0.06)", "--border": "rgba(124,124,255,0.1)",
            "--text": "#e0e0ff", "--text-secondary": "rgba(200,200,255,0.5)",
            "--text-tertiary": "rgba(200,200,255,0.25)", "--accent": "#00d4ff",
            "--accent-glow": "rgba(0,212,255,0.3)", "--radius": "12px",
            "--radius-sm": "6px", "--font": "'SF Mono', 'JetBrains Mono', monospace",
            "--shadow": "0 20px 60px rgba(0,0,0,0.6)",
        }
    },
    "warm_earth": {
        "name": "暖土",
        "css": {
            "--bg": "#1a1410", "--bg-alt": "#1f1814", "--surface": "rgba(255,200,150,0.03)",
            "--surface-hover": "rgba(255,200,150,0.06)", "--border": "rgba(255,200,150,0.08)",
            "--text": "#f0e0d0", "--text-secondary": "rgba(240,224,208,0.5)",
            "--text-tertiary": "rgba(240,224,208,0.25)", "--accent": "#e8a87c",
            "--accent-glow": "rgba(232,168,124,0.3)", "--radius": "20px",
            "--radius-sm": "10px", "--font": "'Georgia', 'Noto Serif SC', serif",
            "--shadow": "0 20px 60px rgba(0,0,0,0.5)",
        }
    },
    "glassmorphism": {
        "name": "玻璃拟态",
        "css": {
            "--bg": "#0a0a1a", "--bg-alt": "rgba(255,255,255,0.02)",
            "--surface": "rgba(255,255,255,0.05)", "--surface-hover": "rgba(255,255,255,0.08)",
            "--border": "rgba(255,255,255,0.08)", "--text": "#fff",
            "--text-secondary": "rgba(255,255,255,0.5)", "--text-tertiary": "rgba(255,255,255,0.25)",
            "--accent": "rgba(255,255,255,0.8)", "--accent-glow": "rgba(255,255,255,0.1)",
            "--radius": "24px", "--radius-sm": "12px", "--font": "'Inter', sans-serif",
            "--shadow": "0 8px 32px rgba(0,0,0,0.3)",
            "--glass": "backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);",
        }
    },
    "retro_terminal": {
        "name": "复古终端",
        "css": {
            "--bg": "#0d0d0d", "--bg-alt": "#111", "--surface": "#1a1a1a",
            "--surface-hover": "#222", "--border": "#33ff33",
            "--text": "#33ff33", "--text-secondary": "rgba(51,255,51,0.5)",
            "--text-tertiary": "rgba(51,255,51,0.25)", "--accent": "#33ff33",
            "--accent-glow": "rgba(51,255,51,0.3)", "--radius": "0px",
            "--radius-sm": "0px", "--font": "'SF Mono', 'Courier New', monospace",
            "--shadow": "none",
        }
    },
}

def get_theme_variants(base_theme: str, count: int = 3) -> List[Dict]:
    """从基础主题派生变体"""
    base = THEMES.get(base_theme, THEMES["apple_dark"])
    variants = []
    hue_shifts = [0, 30, 60, 120, 180, 240, 300]
    for i in range(count):
        v = json.loads(json.dumps(base))
        shift = hue_shifts[i % len(hue_shifts)]
        v["css"]["--accent"] = f"hsl({shift + 260}, 100%, 75%)"
        v["css"]["--accent-glow"] = f"hsla({shift + 260}, 100%, 75%, 0.3)"
        v["name"] = f"{base['name']} (变体 {i+1})"
        variants.append(v)
    return variants


# ═══════════════════════════════════════════════
# 2. 原子组件库 (带 props 接口)
# ═══════════════════════════════════════════════

class Atoms:
    """原子组件 — 每个组件可参数化"""
    
    @staticmethod
    def button(text: str = "Button", variant: str = "primary", size: str = "md", **kw) -> str:
        size_map = {"sm": "px-3 py-1.5 text-xs", "md": "px-5 py-2.5 text-sm", "lg": "px-7 py-3.5 text-base"}
        s = size_map.get(size, size_map["md"])
        if variant == "primary":
            return f'<button class="btn" style="background:var(--accent);color:var(--bg);padding:{s.split()[1] if len(s.split())>1 else "10px"} {s.split()[0] if s.split() else "20px"};border-radius:var(--radius-sm);font-weight:600;border:none;cursor:pointer;transition:all .3s;font-size:{s.split("text-")[1] if "text-" in s else "14px"}">{text}</button>'
        return f'<button class="btn" style="background:transparent;color:var(--text);padding:{kw.get("padding","10px 20px")};border-radius:var(--radius-sm);font-weight:500;border:1px solid var(--border);cursor:pointer">{text}</button>'

    @staticmethod
    def card(title: str, desc: str, icon_svg: str = "", **kw) -> str:
        icon_html = f'<div class="card-icon">{icon_svg}</div>' if icon_svg else ''
        return f'''<div class="card" style="padding:{kw.get("padding","32px")};border-radius:var(--radius);background:var(--surface);border:1px solid var(--border);transition:all .4s">
  {icon_html}
  <h3 style="font-size:17px;font-weight:600;margin-bottom:8px">{title}</h3>
  <p style="font-size:13px;color:var(--text-secondary);line-height:1.7">{desc}</p>
</div>'''

    @staticmethod
    def nav(links: List[tuple], **kw) -> str:
        items = ''.join(f'<a href="{url}" style="color:var(--text-secondary);text-decoration:none;font-size:12px;font-weight:500;transition:color .3s">{label}</a>' for label, url in links)
        return f'''<nav style="position:fixed;top:0;width:100%;z-index:100;padding:16px 40px;display:flex;justify-content:space-between;align-items:center;backdrop-filter:blur(24px);background:rgba(0,0,0,0.7);border-bottom:1px solid var(--border)">
  <div style="font-weight:700;font-size:14px;letter-spacing:1px;color:var(--accent)">{kw.get("brand","LAAP")}</div>
  <div style="display:flex;gap:24px">{items}</div>
</nav>'''

    @staticmethod
    def stat_card(number: str, label: str, **kw) -> str:
        return f'''<div class="stat-card" style="text-align:center;padding:48px 24px;border-radius:var(--radius);background:var(--surface);border:1px solid var(--border);cursor:default">
  <div style="font-size:{kw.get("num_size","48px")};font-weight:800;letter-spacing:-3px;color:var(--accent)">{number}</div>
  <div style="font-size:13px;color:var(--text-secondary);margin-top:8px">{label}</div>
</div>'''


# ═══════════════════════════════════════════════
# 3. 布局编排器
# ═══════════════════════════════════════════════

class Layouts:
    """布局模板 — 可自由组合"""
    
    @staticmethod
    def hero(title: str, subtitle: str, cta_text: str = "", cta_url: str = "#", badge: str = "", **kw) -> str:
        badge_html = f'<div style="display:inline-flex;align-items:center;gap:6px;padding:4px 14px;border-radius:100px;background:rgba(124,124,255,0.1);border:1px solid rgba(124,124,255,0.15);font-size:11px;font-weight:600;color:var(--accent);margin-bottom:20px">{badge}</div>' if badge else ''
        cta = f'<a href="{cta_url}" style="display:inline-flex;align-items:center;gap:8px;padding:12px 28px;border-radius:100px;background:var(--accent);color:var(--bg);font-size:14px;font-weight:600;text-decoration:none">{cta_text}</a>' if cta_text else ''
        three_bg = '<div id="three-hero" style="width:100%;height:100%;position:absolute;top:0;left:0;pointer-events:none;z-index:0"></div>' if kw.get('three_d', False) else ''
        return f'''<section class="hero" style="min-height:{kw.get("height","100vh")};display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;position:relative;overflow:hidden;background:{kw.get("bg","linear-gradient(180deg, var(--bg) 0%, var(--bg-alt) 100%)")}">
  {three_bg}
  <div style="position:relative;z-index:1;padding:0 20px">
    {badge_html}
    <h1 style="font-size:{kw.get("h1_size","clamp(48px,8vw,88px)")};font-weight:800;letter-spacing:-3px;line-height:1.05;margin-bottom:20px;background:linear-gradient(180deg,var(--text) 0%,var(--text-secondary) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent">{title}</h1>
    <p style="font-size:{kw.get("p_size","clamp(16px,2vw,22px)")};color:var(--text-secondary);max-width:680px;margin:0 auto 32px;line-height:1.6">{subtitle}</p>
    {f'<div style="display:flex;gap:12px;justify-content:center">{cta}</div>' if cta else ''}
  </div>
</section>'''

    @staticmethod
    def grid(cards: List[str], cols: int = 3, **kw) -> str:
        col_map = {2: "repeat(2,1fr)", 3: "repeat(3,1fr)", 4: "repeat(4,1fr)"}
        inner = '\n'.join(cards)
        return f'''<section class="section" style="padding:{kw.get("padding","120px 40px")};max-width:{kw.get("max_width","1200px")};margin:0 auto">
  {kw.get("label","")}
  {kw.get("title","")}
  {kw.get("subtitle","")}
  <div style="display:grid;grid-template-columns:{col_map.get(cols,"repeat(3,1fr)")};gap:{kw.get("gap","12px")};margin-top:{kw.get("mt","60px")}">{inner}</div>
</section>'''

    @staticmethod
    def stats(items: List[str], **kw) -> str:
        inner = '\n'.join(items)
        return f'''<section class="section" style="padding:{kw.get("padding","80px 40px")};max-width:{kw.get("max_width","1200px")};margin:0 auto">
  <div style="display:grid;grid-template-columns:repeat({len(items)},1fr);gap:16px">{inner}</div>
</section>'''

    @staticmethod
    def pipeline(steps: List[str], **kw) -> str:
        step_html = ''
        for i, s in enumerate(steps):
            arrow = '<span style="color:var(--text-tertiary);font-size:20px;padding:0 8px">→</span>' if i < len(steps) - 1 else ''
            step_html += f'<div style="display:flex;flex-direction:column;align-items:center;gap:12px;padding:16px 24px"><div style="width:48px;height:48px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:rgba(124,124,255,0.06);border:1px solid rgba(124,124,255,0.1)">{s}</div><span style="font-size:11px;color:var(--text-tertiary)">{kw.get("step_labels","")}</span></div>{arrow}'
        return f'''<section class="section" style="padding:120px 40px;max-width:1200px;margin:0 auto;text-align:center">
  <div style="display:flex;align-items:center;justify-content:center;flex-wrap:wrap">{step_html}</div>
</section>'''


# ═══════════════════════════════════════════════
# 4. 合成引擎 (核心)
# ═══════════════════════════════════════════════

class HarnessComposer:
    """合成引擎 — JSON Spec → 完整页面, 零 token"""
    
    def __init__(self, theme: str = "apple_dark"):
        self.theme = THEMES.get(theme, THEMES["apple_dark"])
        self.atoms = Atoms()
        self.layouts = Layouts()
    
    def set_theme(self, theme_id: str, custom_css: Optional[Dict] = None):
        self.theme = THEMES.get(theme_id, THEMES["apple_dark"])
        if custom_css:
            self.theme["css"].update(custom_css)
    
    def theme_css(self) -> str:
        vars_str = '\n'.join(f'  {k}: {v};' for k, v in self.theme["css"].items())
        glass = self.theme["css"].get("--glass", "")
        return f''':root {{\n{vars_str}\n}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:var(--font); background:var(--bg); color:var(--text); -webkit-font-smoothing:antialiased; }}
.card:hover {{ transform:translateY(-4px); box-shadow:var(--shadow); border-color:rgba(124,124,255,0.2); }}
.stat-card:hover {{ border-color:rgba(124,124,255,0.15); }}
@media (max-width:768px) {{ section {{ padding:60px 20px !important; }} [style*="grid-template-columns"] {{ grid-template-columns:1fr !important; }} }}
{glass}'''
    
    def from_spec(self, spec: Dict) -> str:
        """从 JSON spec 合成完整页面"""
        
        # Theme override
        if "theme" in spec:
            self.set_theme(spec["theme"])
        
        # Navigation
        nav_html = ""
        if "nav" in spec:
            links = [(l["label"], l["url"]) for l in spec["nav"]["links"]]
            nav_html = self.atoms.nav(links, brand=spec["nav"].get("brand", "LAAP"))
        
        # Sections
        sections_html = ""
        for sec in spec.get("sections", []):
            t = sec["type"]
            if t == "hero":
                sections_html += self.layouts.hero(
                    sec["title"], sec.get("subtitle", ""),
                    cta_text=sec.get("cta", ""), cta_url=sec.get("cta_url", "#"),
                    badge=sec.get("badge", ""), three_d=sec.get("three_d", False),
                    height=sec.get("height", "100vh")
                )
            elif t == "stats":
                items = [self.atoms.stat_card(s["number"], s["label"]) for s in sec["items"]]
                sections_html += self.layouts.stats(items)
            elif t == "grid":
                cards = []
                for c in sec.get("cards", []):
                    icon = c.get("icon_svg", "")
                    cards.append(self.atoms.card(c["title"], c["desc"], icon))
                label = f'<div class="section-label" style="font-size:12px;font-weight:600;letter-spacing:3px;color:var(--accent);margin-bottom:8px">{sec.get("label","")}</div>' if sec.get("label") else ''
                title = f'<h2 style="font-size:{sec.get("h2_size","clamp(32px,5vw,56px)")};font-weight:700;letter-spacing:-2px;margin-bottom:16px">{sec.get("title","")}</h2>' if sec.get("title") else ''
                subtitle = f'<p style="font-size:18px;color:var(--text-secondary);max-width:600px;line-height:1.7">{sec.get("subtitle","")}</p>' if sec.get("subtitle") else ''
                sections_html += self.layouts.grid(cards, cols=sec.get("cols", 3),
                    label=label, title=title, subtitle=subtitle,
                    mt=sec.get("mt", "60px"))
            elif t == "pipeline":
                steps = [f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>' for _ in sec.get("items", [])]
                sections_html += self.layouts.pipeline(steps)
            elif t == "custom_html":
                sections_html += sec.get("html", "")
        
        # Footer
        footer_html = ""
        if "footer" in spec:
            f = spec["footer"]
            footer_html = f'''<footer style="text-align:center;padding:48px 40px;border-top:1px solid var(--border)"><p style="font-size:12px;color:var(--text-tertiary)">{f.get("text","")}</p></footer>'''
        
        # Three.js (optional)
        three_js = ""
        if any(s.get("three_d") for s in spec.get("sections", []) if s["type"] == "hero"):
            three_js = THREE_BOOTSTRAP
        
        # GSAP (optional)
        gsap = GSAP_SCRIPT if spec.get("animations", True) else ""
        
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{spec.get("title", "LAAP Page")}</title>
<style>{self.theme_css()}</style>
{three_js}
{gsap}
</head>
<body>
{nav_html}
{sections_html}
{footer_html}
<script>document.querySelectorAll(".stat-card,.card").forEach(el => {{
  const o = new IntersectionObserver(e => {{ if(e[0].isIntersecting){{ el.style.opacity="1";el.style.transform="translateY(0)";o.unobserve(el) }}}},{{threshold:0.1}});
  el.style.opacity="0";el.style.transform="translateY(30px)";el.style.transition="all 0.8s cubic-bezier(0.16,1,0.3,1)";o.observe(el);
}});</script>
</body>
</html>'''

    def generate_variant(self, spec: Dict, variant_idx: int = 0) -> str:
        """生成一个多样性变体"""
        s = json.loads(json.dumps(spec))  # deep copy
        
        # 换主题
        themes = list(THEMES.keys())
        s["theme"] = themes[variant_idx % len(themes)]
        
        # 换布局密度
        if variant_idx % 3 == 0:
            for sec in s.get("sections", []):
                if sec["type"] == "grid":
                    sec["cols"] = 2 if sec.get("cols", 3) >= 3 else 4
                if "mt" in sec:
                    sec["mt"] = str(int(sec["mt"].replace("px","")) * (1 + (variant_idx % 2)))
        
        return self.from_spec(s)


# ── 3D 与动效 ──
THREE_BOOTSTRAP = '''
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
<script type="module">
import*as THREE from"three";import{EffectComposer}from"three/addons/postprocessing/EffectComposer.js";import{RenderPass}from"three/addons/postprocessing/RenderPass.js";import{UnrealBloomPass}from"three/addons/postprocessing/UnrealBloomPass.js";
export function createNeuralScene(c){
  const s=new THREE.Scene(),ca=new THREE.PerspectiveCamera(75,c.clientWidth/c.clientHeight,0.1,1e3),r=new THREE.WebGLRenderer({alpha:true,antialias:true});
  r.setSize(c.clientWidth,c.clientHeight);r.setPixelRatio(Math.min(devicePixelRatio,2));c.appendChild(r.domElement);
  const n=2500,p=new Float32Array(n*3);for(let i=0;i<n*3;i++)p[i]=(Math.random()-.5)*25;
  const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.BufferAttribute(p,3));
  const m=new THREE.PointsMaterial({size:.04,color:0x7c7cff,transparent:true,opacity:.5,blending:THREE.AdditiveBlending}),pt=new THREE.Points(g,m);s.add(pt);
  const lp=[];for(let i=0;i<400;i++){const i1=Math.floor(Math.random()*n),i2=Math.floor(Math.random()*n),a=p.slice(i1*3,i1*3+3),b=p.slice(i2*3,i2*3+3);if(Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2])<4)lp.push(...a,...b);}
  const lg=new THREE.BufferGeometry();lg.setAttribute("position",new THREE.Float32BufferAttribute(lp,3));
  const ls=new THREE.LineSegments(lg,new THREE.LineBasicMaterial({color:0x7c7cff,transparent:true,opacity:.06}));s.add(ls);
  const co=new EffectComposer(r);co.addPass(new RenderPass(s,ca));co.addPass(new UnrealBloomPass(new THREE.Vector2(c.clientWidth,c.clientHeight),.2,.5,.1));
  ca.position.z=10;let rot=0;function anim(){requestAnimationFrame(anim);rot+=.0008;pt.rotation.y=rot;ls.rotation.y=rot;co.render();}anim();
  addEventListener("resize",()=>{ca.aspect=c.clientWidth/c.clientHeight;ca.updateProjectionMatrix();r.setSize(c.clientWidth,c.clientHeight);co.setSize(c.clientWidth,c.clientHeight);});
}
addEventListener("DOMContentLoaded",()=>{const e=document.getElementById("three-hero");if(e&&typeof createNeuralScene!="undefined")createNeuralScene(e);});
</script>'''

GSAP_SCRIPT = '''
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js"></script>
<script>
gsap.registerPlugin(ScrollTrigger);
gsap.utils.toArray(".card,.stat-card").forEach(el=>{gsap.from(el,{scrollTrigger:{trigger:el,start:"top 85%"},y:40,opacity:0,duration:.8,ease:"power3.out",delay:Math.random()*.2});});
</script>'''


# ═══════════════════════════════════════════════
# 5. 多样性引擎
# ═══════════════════════════════════════════════

class DiversityEngine:
    """多样性引擎 — 一次 Spec, 多种输出"""
    
    def __init__(self):
        self.composer = HarnessComposer()
    
    def generate_series(self, spec: Dict, count: int = 5) -> List[str]:
        """生成 count 个不同变体"""
        pages = []
        base_spec = json.loads(json.dumps(spec))
        
        for i in range(count):
            s = json.loads(json.dumps(base_spec))
            theme_keys = list(THEMES.keys())
            s["theme"] = theme_keys[i % len(theme_keys)]
            
            # 换布局
            if i % 2 == 0:
                for sec in s.get("sections", []):
                    if sec["type"] == "grid":
                        sec["cols"] = 2
                    if sec["type"] == "hero":
                        sec["badge"] = sec.get("badge", "") + f" v{i+1}"
            
            pages.append(self.composer.from_spec(s))
        
        return pages


# ── 测试 ──
if __name__ == "__main__":
    spec = {
        "title": "Test Page",
        "theme": "apple_dark",
        "nav": {"brand": "HARNESS", "links": [{"label": "Home", "url": "#"}, {"label": "About", "url": "#"}]},
        "sections": [
            {"type": "hero", "title": "Test Hero", "subtitle": "Zero token generation", "badge": "v1.0", "three_d": True, "cta": "Get Started"},
            {"type": "stats", "items": [{"number": "99%", "label": "Token Savings"}, {"number": "0", "label": "LLM Calls"}]},
            {"type": "grid", "label": "Features", "title": "Core Capabilities", "subtitle": "Everything runs locally", "cols": 3,
             "cards": [
                {"title": "Component Synthesis", "desc": "Atomic components composed into pages"},
                {"title": "Theme System", "desc": "7 presets, infinite variants"},
                {"title": "Zero Tokens", "desc": "Pure Python, no LLM calls"},
             ]},
        ],
        "footer": {"text": "Built with Harness Composer"}
    }
    
    c = HarnessComposer()
    page = c.from_spec(spec)
    
    out = 'D:/LAAP/aris_brain/test_composer.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(page)
    print(f'Generated: {out} ({len(page):,} bytes)')
    print(f'SVG icons: {page.count("<svg")}')
    print(f'Three.js: {"three.module.js" in page}')
    print(f'Emoji check: {not any(ord(c)>0x2700 for c in page if ord(c)>0x2700)}')
    
    # Test diversity
    d = DiversityEngine()
    variants = d.generate_series(spec, 3)
    print(f'\nDiversity test: {len(variants)} variants generated')
    for i, v in enumerate(variants):
        fname = f'D:/LAAP/aris_brain/test_variant_{i+1}.html'
        with open(fname, 'w', encoding='utf-8') as f:
            f.write(v)
        print(f'  Variant {i+1}: {len(v):,} bytes')
