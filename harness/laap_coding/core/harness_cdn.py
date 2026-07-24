"""
harness_cdn.py — CDN 资源管理器 + UI 库仓库
生产级: 直接链接 CDN, 不打包; 已下载的仓库作为组件源
"""
import os, json, subprocess
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_UI = os.path.join(os.path.dirname(HERE), 'templates', 'ui')

# ── CDN 资源注册表 ──
CDN_REGISTRY = {
    # CSS 框架
    "tailwind": {
        "css": "https://cdn.jsdelivr.net/npm/tailwindcss@3.4.17/base.min.css",
        "prod": "https://cdn.jsdelivr.net/npm/tailwindcss@3.4.17/base.min.css",
        "type": "framework",
    },
    "daisyui": {
        "css": "https://cdn.jsdelivr.net/npm/daisyui@4.12.23/dist/full.min.css",
        "prod": "https://cdn.jsdelivr.net/npm/daisyui@4.12.23/dist/full.min.css",
        "type": "component",
    },
    
    # 图标
    "lucide": {
        "js": "https://unpkg.com/lucide@0.468.0/dist/umd/lucide.js",
        "prod": "https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js",
        "type": "icon",
    },
    
    # 3D
    "three": {
        "js": "https://unpkg.com/three@0.170.0/build/three.module.js",
        "importmap": {"three": "https://unpkg.com/three@0.170.0/build/three.module.js",
                      "three/addons/": "https://unpkg.com/three@0.170.0/examples/jsm/"},
        "type": "3d",
    },
    
    # 动画
    "gsap": {
        "js": "https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js",
        "scrolltrigger": "https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js",
        "type": "animation",
    },
    "framer_motion": {
        "js": "https://unpkg.com/framer-motion@11.15.0/dist/framer-motion.js",
        "type": "animation",
    },
    "lenis": {
        "js": "https://unpkg.com/lenis@1.1.18/dist/lenis.min.js",
        "type": "scroll",
    },
    
    # UI 库 CDN
    "antd": {
        "css": "https://unpkg.com/antd@5.22.0/dist/reset.css",
        "type": "ui",
    },
    "element_plus": {
        "css": "https://unpkg.com/element-plus@2.9.1/dist/index.css",
        "type": "ui",
    },
    
    # 字体
    "inter": {
        "css": "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap",
        "type": "font",
    },
    "sf_mono": {
        "css": "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap",
        "type": "font",
    },
}


class CDNManager:
    """CDN 资源管理器 — 按需注入, 版本锁定"""
    
    @staticmethod
    def get_links(libs: List[str], prod: bool = True) -> Dict[str, str]:
        """获取指定库的 CDN 链接"""
        result = {"css": [], "js": [], "importmap": None}
        for name in libs:
            lib = CDN_REGISTRY.get(name)
            if not lib:
                continue
            key = "prod" if prod and "prod" in lib else "js" if "js" in lib else None
            if key and key in lib:
                result["js"].append(f'<script src="{lib[key]}"></script>')
            if "css" in lib:
                result["css"].append(f'<link rel="stylesheet" href="{lib["css"]}">')
            if "importmap" in lib:
                result["importmap"] = json.dumps(lib["importmap"])
            # Sub-resources
            for sub_key in ["scrolltrigger"]:
                if sub_key in lib:
                    result["js"].append(f'<script src="{lib[sub_key]}"></script>')
        return result
    
    @staticmethod
    def lucide_init() -> str:
        """Lucide 图标自动替换脚本"""
        return '<script>document.addEventListener("DOMContentLoaded",()=>{if(typeof lucide!=="undefined")lucide.createIcons();});</script>'
    
    @classmethod
    def inject(cls, libs: List[str], html: str, prod: bool = True) -> str:
        """注入 CDN 链接到 HTML head"""
        links = cls.get_links(libs, prod)
        head_end = html.find("</head>")
        if head_end == -1:
            return html
        
        injections = []
        if links["importmap"]:
            injections.append(f'<script type="importmap">{links["importmap"]}</script>')
        injections.extend(links["css"])
        injections.extend(links["js"])
        if "lucide" in libs:
            injections.append(cls.lucide_init())
        
        return html[:head_end] + "\n".join(injections) + "\n" + html[head_end:]


# ── 本地仓库管理器 ──
class UILibraryRepo:
    """管理已下载到本地的 UI 库仓库"""
    
    @staticmethod
    def scan() -> Dict[str, Dict]:
        """扫描 templates/ui/ 下的所有仓库"""
        repos = {}
        if not os.path.exists(TEMPLATE_UI):
            return repos
        
        for item in os.listdir(TEMPLATE_UI):
            repo_path = os.path.join(TEMPLATE_UI, item)
            if not os.path.isdir(repo_path):
                continue
            
            # 统计源码文件
            stats = {"files": 0, "lines": 0, "components": 0}
            for root, dirs, files in os.walk(repo_path):
                for f in files:
                    if f.endswith(('.tsx', '.ts', '.jsx', '.js', '.css', '.vue', '.py')):
                        stats["files"] += 1
                        try:
                            with open(os.path.join(root, f), 'r', errors='ignore') as fh:
                                stats["lines"] += sum(1 for _ in fh)
                        except:
                            pass
                        if any(kw in f.lower() for kw in ['button', 'card', 'modal', 'nav', 'input', 'form']):
                            stats["components"] += 1
            
            repos[item] = {
                "path": repo_path,
                "stats": stats,
                "has_package": os.path.exists(os.path.join(repo_path, 'package.json')),
                "has_readme": os.path.exists(os.path.join(repo_path, 'README.md')),
            }
        return repos
    
    @staticmethod
    def find_component(query: str) -> List[Dict]:
        """在所有仓库中搜索组件"""
        results = []
        for repo_name, info in UILibraryRepo.scan().items():
            for root, dirs, files in os.walk(info["path"]):
                for f in files:
                    if query.lower() in f.lower() and f.endswith(('.tsx', '.ts', '.jsx', '.vue')):
                        fpath = os.path.join(root, f)
                        with open(fpath, 'r', errors='ignore') as fh:
                            content = fh.read(2000)
                        results.append({
                            "repo": repo_name,
                            "file": f,
                            "path": fpath,
                            "size": os.path.getsize(fpath),
                            "preview": content[:200],
                        })
        return results


# ── 测试 ──
if __name__ == "__main__":
    print("=== CDN Manager ===")
    links = CDNManager.get_links(["three", "gsap", "lucide", "inter"])
    print(f"  CSS links: {len(links['css'])}")
    print(f"  JS links: {len(links['js'])}")
    print(f"  ImportMap: {'three' in (links.get('importmap') or '')}")
    
    print("\n=== UI Library Repos ===")
    repos = UILibraryRepo.scan()
    if repos:
        for name, info in repos.items():
            s = info["stats"]
            print(f"  {name:25s} {s['files']:4d} files  {s['lines']:6d} lines  {s['components']} components")
    else:
        print("  (no repos cloned yet)")
    
    print(f"\n  Template dir: {TEMPLATE_UI}")
