"""
harness_style_engine.py — 用户风格选择引擎 + 生产级合成器 v2
核心: 用户选择风格 → CSS 变量 → CDN 注入 → 零 token 生成
"""
import json, os, random, sys
try:
    from harness_cdn import CDNManager
except Exception:
    CDNManager = None
from typing import Dict, Any, Optional, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path = [os.path.dirname(HERE)] + sys.path if __name__ == "__main__" else None

# ── 风格预设库 (用户可选择) ──
STYLE_PRESETS = {
    "apple_dark": {
        "name": "Apple 深色",
        "category": "现代",
        "tags": ["premium", "dark", "minimal"],
        "css_vars": {
            "--bg": "#000", "--bg-alt": "#0a0a0f", "--surface": "rgba(255,255,255,0.03)",
            "--text": "#f5f5f7", "--text-secondary": "rgba(255,255,255,0.5)",
            "--accent": "#7c7cff", "--radius": "16px", "--font": "'Inter', -apple-system, sans-serif",
        },
        "cdn": ["inter"],
        "three_d": True,
    },
    "apple_light": {
        "name": "Apple 浅色",
        "category": "现代",
        "tags": ["premium", "light", "clean"],
        "css_vars": {
            "--bg": "#fff", "--bg-alt": "#f5f5f7", "--surface": "rgba(0,0,0,0.02)",
            "--text": "#1d1d1f", "--text-secondary": "rgba(0,0,0,0.5)",
            "--accent": "#7c7cff", "--radius": "16px", "--font": "'Inter', -apple-system, sans-serif",
        },
        "cdn": ["inter"],
        "three_d": False,
    },
    "dark_tech": {
        "name": "暗夜科技",
        "category": "科技",
        "tags": ["cyber", "dark", "tech"],
        "css_vars": {
            "--bg": "#0a0a0f", "--bg-alt": "#0d0d1a", "--surface": "rgba(124,124,255,0.03)",
            "--text": "#e0e0ff", "--text-secondary": "rgba(200,200,255,0.5)",
            "--accent": "#00d4ff", "--radius": "12px", "--font": "'SF Mono', 'JetBrains Mono', monospace",
        },
        "cdn": ["sf_mono"],
        "three_d": True,
    },
    "warm_earth": {
        "name": "暖土",
        "category": "自然",
        "tags": ["warm", "organic", "serif"],
        "css_vars": {
            "--bg": "#1a1410", "--bg-alt": "#1f1814", "--surface": "rgba(255,200,150,0.03)",
            "--text": "#f0e0d0", "--text-secondary": "rgba(240,224,208,0.5)",
            "--accent": "#e8a87c", "--radius": "20px", "--font": "'Georgia', 'Noto Serif SC', serif",
        },
        "cdn": [],
        "three_d": False,
    },
    "glassmorphism": {
        "name": "玻璃拟态",
        "category": "现代",
        "tags": ["glass", "frosted", "modern"],
        "css_vars": {
            "--bg": "#0a0a1a", "--bg-alt": "rgba(255,255,255,0.02)",
            "--surface": "rgba(255,255,255,0.05)", "--text": "#fff",
            "--text-secondary": "rgba(255,255,255,0.5)", "--accent": "rgba(255,255,255,0.8)",
            "--radius": "24px", "--font": "'Inter', sans-serif",
            "--glass": "backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)",
        },
        "cdn": ["inter"],
        "three_d": True,
    },
    "retro_terminal": {
        "name": "复古终端",
        "category": "复古",
        "tags": ["retro", "terminal", "green"],
        "css_vars": {
            "--bg": "#0d0d0d", "--bg-alt": "#111", "--surface": "#1a1a1a",
            "--text": "#33ff33", "--text-secondary": "rgba(51,255,51,0.5)",
            "--accent": "#33ff33", "--radius": "0px", "--font": "'SF Mono', 'Courier New', monospace",
        },
        "cdn": ["sf_mono"],
        "three_d": False,
    },
    "minimal_white": {
        "name": "极简白",
        "category": "现代",
        "tags": ["clean", "light", "minimal"],
        "css_vars": {
            "--bg": "#fff", "--bg-alt": "#fafafa", "--surface": "#fff",
            "--text": "#111", "--text-secondary": "#666",
            "--accent": "#000", "--radius": "8px", "--font": "'Inter', sans-serif",
        },
        "cdn": ["inter"],
        "three_d": False,
    },
    "sunset": {
        "name": "日落",
        "category": "自然",
        "tags": ["warm", "gradient", "colorful"],
        "css_vars": {
            "--bg": "#1a0a1a", "--bg-alt": "#2a0a1a", "--surface": "rgba(255,100,100,0.03)",
            "--text": "#ffe0d0", "--text-secondary": "rgba(255,224,208,0.5)",
            "--accent": "#ff6b6b", "--radius": "16px", "--font": "'Inter', sans-serif",
        },
        "cdn": ["inter"],
        "three_d": True,
    },
    "ocean": {
        "name": "深海",
        "category": "自然",
        "tags": ["blue", "deep", "calm"],
        "css_vars": {
            "--bg": "#000a14", "--bg-alt": "#001a2a", "--surface": "rgba(0,100,200,0.03)",
            "--text": "#c0e0ff", "--text-secondary": "rgba(192,224,255,0.5)",
            "--accent": "#00aaff", "--radius": "16px", "--font": "'Inter', sans-serif",
        },
        "cdn": ["inter"],
        "three_d": True,
    },
}


class StyleEngine:
    """风格引擎 — 用户选择 → CSS 变量 → 注入"""
    
    @staticmethod
    def list_categories() -> List[str]:
        return list(set(p["category"] for p in STYLE_PRESETS.values()))
    
    @staticmethod
    def list_by_category(cat: str) -> List[Dict]:
        return [{"id": k, **v} for k, v in STYLE_PRESETS.items() if v["category"] == cat]
    
    @staticmethod
    def get_style(style_id: str) -> Optional[Dict]:
        return STYLE_PRESETS.get(style_id)
    
    @staticmethod
    def customize(style_id: str, overrides: Dict[str, str]) -> Dict:
        """用户自定义: 在预设基础上修改任意 CSS 变量"""
        base = json.loads(json.dumps(STYLE_PRESETS.get(style_id, STYLE_PRESETS["apple_dark"])))
        base["css_vars"].update(overrides)
        base["name"] += " (自定义)"
        return base
    
    @staticmethod
    def css_vars_to_string(vars: Dict[str, str]) -> str:
        return "\n".join(f"  {k}: {v};" for k, v in vars.items())
    
    @staticmethod
    def generate_preview(style_id: str) -> str:
        """生成风格预览 HTML 片段"""
        style = STYLE_PRESETS.get(style_id)
        if not style:
            return ""
        vars_str = StyleEngine.css_vars_to_string(style["css_vars"])
        return f'''<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:20px;border-radius:12px;background:{style['css_vars']['--bg']};color:{style['css_vars']['--text']}">
  <div style="grid-column:1/-1;font-size:12px;font-weight:600;margin-bottom:4px">{style["name"]}</div>
  <div style="padding:12px;border-radius:8px;background:{style['css_vars']['--surface']};border:1px solid {style['css_vars']['--accent']};text-align:center;font-size:12px">Button</div>
  <div style="padding:12px;border-radius:8px;background:{style['css_vars']['--surface']};border:1px solid rgba(255,255,255,0.06);text-align:center;font-size:12px">Card</div>
  <div style="padding:12px;border-radius:8px;background:{style['css_vars']['--accent']};color:{style['css_vars']['--bg']};text-align:center;font-size:12px;font-weight:600">CTA</div>
  <div style="padding:12px;border-radius:8px;border:1px solid {style['css_vars']['--text-secondary']};text-align:center;font-size:12px;color:{style['css_vars']['--text-secondary']}">Input</div>
</div>'''


# ═══════════════════════════════════════════════
# 生产级合成器 v2 — CDN + 风格 + 组件 + 布局
# ═══════════════════════════════════════════════

class ProductionComposer:
    """生产级合成引擎 v2 — CDN 链接 + 用户风格 + 零 token"""
    
    def __init__(self, style: str = "apple_dark"):
        self.style_data = STYLE_PRESETS.get(style, STYLE_PRESETS["apple_dark"])
    
    def set_style(self, style_id: str, overrides: Optional[Dict] = None):
        if overrides:
            self.style_data = StyleEngine.customize(style_id, overrides)
        else:
            self.style_data = STYLE_PRESETS.get(style_id, STYLE_PRESETS["apple_dark"])
    
    def generate(self, spec: Dict) -> str:
        """JSON spec → 生产级页面"""
        s = self.style_data
        vars_str = StyleEngine.css_vars_to_string(s["css_vars"])
        glass = s["css_vars"].get("--glass", "")
        
        cdn_html = ""
        for lib in s.get("cdn", []):
            if CDNManager:
                links = CDNManager.get_links([lib])
                cdn_html += "\n".join(links["css"] + links["js"])
        
        # Three.js
        three_html = ""
        if s.get("three_d") and any(sec.get("three_d") for sec in spec.get("sections", []) if sec.get("type") == "hero"):
            three_html = '''
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.170.0/build/three.module.js","three/addons/":"https://unpkg.com/three@0.170.0/examples/jsm/"}}</script>
<script type="module">import*as THREE from"three";import{EffectComposer}from"three/addons/postprocessing/EffectComposer.js";import{RenderPass}from"three/addons/postprocessing/RenderPass.js";import{UnrealBloomPass}from"three/addons/postprocessing/UnrealBloomPass.js";
addEventListener("DOMContentLoaded",()=>{const e=document.getElementById("three-canvas");if(!e)return;const s=new THREE.Scene,ca=new THREE.PerspectiveCamera(75,e.clientWidth/e.clientHeight,.1,1e3),r=new THREE.WebGLRenderer({alpha:true,antialias:true});r.setSize(e.clientWidth,e.clientHeight);r.setPixelRatio(Math.min(devicePixelRatio,2));e.appendChild(r.domElement);const pt=new THREE.BufferGeometry,n=2e3,p=new Float32Array(n*3);for(let i=0;i<n*3;i++)p[i]=(Math.random()-.5)*20;pt.setAttribute("position",new THREE.BufferAttribute(p,3));const pm=new THREE.PointsMaterial({size:.03,color:0x7c7cff,transparent:true,opacity:.4,blending:THREE.AdditiveBlending}),ps=new THREE.Points(pt,pm);s.add(ps);ca.position.z=8;let rot=0;function a(){requestAnimationFrame(a);rot+=.001;ps.rotation.y=rot;r.render(s,ca);}a();});</script>'''
        
        # Build sections
        sections = []
        for sec in spec.get("sections", []):
            t = sec["type"]
            if t == "hero":
                badge = f'<span style="display:inline-flex;align-items:center;gap:6px;padding:4px 14px;border-radius:100px;background:rgba({s["css_vars"]["--accent"].replace("#","")},0.1) 2>{s["css_vars"]["--accent"]};font-size:11px;margin-bottom:20px">{sec.get("badge","")}</span>' if sec.get("badge") else ''
                cta = f'<a href="{sec.get("cta_url","#")}" style="display:inline-flex;padding:12px 28px;border-radius:100px;background:var(--accent);color:var(--bg);font-size:14px;font-weight:600;text-decoration:none">{sec.get("cta","")}</a>' if sec.get("cta") else ''
                canvas = '<div id="three-canvas" style="position:absolute;inset:0;pointer-events:none;z-index:0"></div>' if sec.get("three_d") else ''
                sections.append(f'''<section style="min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;position:relative;overflow:hidden">
  {canvas}
  <div style="position:relative;z-index:1;padding:0 20px">
    {badge}
    <h1 style="font-size:clamp(48px,8vw,88px);font-weight:800;letter-spacing:-3px;line-height:1.05;margin-bottom:20px;background:linear-gradient(180deg,var(--text),var(--text-secondary));-webkit-background-clip:text;-webkit-text-fill-color:transparent">{sec["title"]}</h1>
    <p style="font-size:clamp(16px,2vw,22px);color:var(--text-secondary);max-width:680px;margin:0 auto 32px;line-height:1.6">{sec.get("subtitle","")}</p>
    {f'<div style="display:flex;gap:12px;justify-content:center">{cta}</div>' if cta else ''}
  </div>
</section>''')
            
            elif t == "stats":
                items = "".join(f'<div style="text-align:center;padding:48px 24px;border-radius:var(--radius,16px);background:var(--surface,rgba(255,255,255,0.02));border:1px solid rgba(255,255,255,0.05)"><div style="font-size:48px;font-weight:800;letter-spacing:-3px;color:var(--accent)">{st["number"]}</div><div style="font-size:13px;color:var(--text-secondary);margin-top:8px">{st["label"]}</div></div>' for st in sec.get("items",[]))
                sections.append(f'<section style="padding:80px 40px;max-width:1200px;margin:0 auto"><div style="display:grid;grid-template-columns:repeat({len(sec.get("items",[]))},1fr);gap:16px">{items}</div></section>')
            
            elif t == "grid":
                cards = "".join(f'<div style="padding:32px;border-radius:var(--radius,16px);background:var(--surface,rgba(255,255,255,0.02));border:1px solid rgba(255,255,255,0.05);transition:all.4s"><h3 style="font-size:16px;font-weight:600;margin-bottom:8px">{c["title"]}</h3><p style="font-size:13px;color:var(--text-secondary);line-height:1.7">{c["desc"]}</p></div>' for c in sec.get("cards",[]))
                sections.append(f'''<section style="padding:120px 40px;max-width:1200px;margin:0 auto">
  {f'<div style="font-size:12px;font-weight:600;letter-spacing:3px;color:var(--accent);margin-bottom:8px">{sec.get("label","")}</div>' if sec.get("label") else ""}
  {f'<h2 style="font-size:clamp(32px,5vw,56px);font-weight:700;letter-spacing:-2px;margin-bottom:16px">{sec.get("title","")}</h2>' if sec.get("title") else ""}
  {f'<p style="font-size:18px;color:var(--text-secondary);max-width:600px;line-height:1.7;margin-bottom:60px">{sec.get("subtitle","")}</p>' if sec.get("subtitle") else ""}
  <div style="display:grid;grid-template-columns:repeat({sec.get("cols",3)},1fr);gap:12px">{cards}</div>
</section>''')
        
        # Footer
        footer = ""
        if "footer" in spec:
            f = spec["footer"]
            footer = f'<footer style="text-align:center;padding:48px 40px;border-top:1px solid var(--border,rgba(255,255,255,0.05));font-size:12px;color:var(--text-tertiary,rgba(255,255,255,0.2))">{f.get("text","")}</footer>'
        
        return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{spec.get("title","Page")}</title>
<style>
:root {{
{vars_str}
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:{s['css_vars']['--font']}; background:var(--bg); color:var(--text); -webkit-font-smoothing:antialiased; }}
nav {{ position:fixed;top:0;width:100%;z-index:100;padding:16px 40px;display:flex;justify-content:space-between;align-items:center;backdrop-filter:blur(24px);background:rgba(0,0,0,0.7);border-bottom:1px solid var(--border,rgba(255,255,255,0.05)); }}
nav a {{ color:var(--text-secondary);text-decoration:none;font-size:12px;font-weight:500;transition:color.3s }}
nav a:hover {{ color:var(--text) }}
@media (max-width:768px) {{ [style*="grid-template-columns"] {{ grid-template-columns:1fr!important; }} section {{ padding:60px 20px!important; }} nav {{ padding:12px 20px; }} }}
{glass}
</style>
{cdn_html}
{three_html}
</head>
<body>
{spec.get("nav_html","")}
{"".join(sections)}
{footer}
<script>
document.querySelectorAll("[style*='padding:32px']").forEach(el=>{{const o=new IntersectionObserver(e=>{{if(e[0].isIntersecting){{el.style.opacity="1";el.style.transform="translateY(0)";o.unobserve(el)}}}},{{threshold:.1}});el.style.opacity="0";el.style.transform="translateY(30px)";el.style.transition="all .8s cubic-bezier(.16,1,.3,1)";o.observe(el);}});
</script>
</body>
</html>'''


# ── 测试 ──
if __name__ == "__main__":
    print("=== 风格引擎 ===")
    for cat in StyleEngine.list_categories():
        styles = StyleEngine.list_by_category(cat)
        print(f"  {cat}: {', '.join(s['name'] for s in styles)}")
    
    print("\n=== 生产级合成 ===")
    spec = {
        "title": "零 Token 方案 · 生产级",
        "sections": [
            {"type": "hero", "title": "生产级零 Token 方案", "subtitle": "CDN 链接 · 用户风格 · 组件库 · 全部零 Token", "badge": "v2.0", "three_d": True, "cta": "开始使用"},
            {"type": "stats", "items": [
                {"number": "9", "label": "预设风格"},
                {"number": "0", "label": "Token 消耗"},
                {"number": "∞", "label": "自定义变体"},
            ]},
            {"type": "grid", "label": "核心能力", "title": "生产级特性", "cols": 3,
             "cards": [
                {"title": "CDN 直接链接", "desc": "不打包、不缓存。Tailwind/Three.js/GSAP/Lucide 直接从 CDN 加载"},
                {"title": "用户风格选择", "desc": "9 种预设 + 任意 CSS 变量覆盖。风格引擎实时生成"},
                {"title": "仓库组件库", "desc": "已下载的 shadcn/ui、daisyui 等仓库作为组件源"},
                {"title": "零 Token 生成", "desc": "纯 Python 合成。每次生成 0 token"},
                {"title": "生产级 CDN", "desc": "版本锁定、自动切换 prod/dev、import map 管理"},
                {"title": "无限扩展", "desc": "新风格 = 加一条 JSON。新库 = git clone"},
            ]},
        ],
        "footer": {"text": "Harness Production Composer v2 · 零 Token"},
    }
    
    # 用不同风格生成
    for style_id in ["apple_dark", "dark_tech", "glassmorphism", "retro_terminal", "sunset", "ocean"]:
        c = ProductionComposer(style_id)
        page = c.generate(spec)
        out = f'D:/LAAP/aris_brain/prod_{style_id}.html'
        with open(out, 'w', encoding='utf-8') as f:
            f.write(page)
        print(f"  {style_id:20s} → {len(page):>6,} bytes")
    
    print("\n✅ 全部零 token 生成")
