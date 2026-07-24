"""
harness_crawler.py — Harness 工程爬虫
从 GitHub 发现热门模式, 提取 HEP 组件, 注册到本地数据库
"""
import sys, os, json, time, re
from typing import Dict, List, Optional
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

try:
    import urllib.request
    HAS_NETWORK = True
except:
    HAS_NETWORK = False

from hep_protocol import HEPRegistry, HEPComponent, REGISTRY
from hep_extractor import HEPExtractor, GitHubPatternCrawler

# ── 模式发现种子 ──
TOPICS = {
    # 后端
    "backend": ["fastapi", "django", "flask-rest-api", "spring-boot", "gin", "expressjs", "nestjs", "laravel", "axum", "actix-web"],
    # 前端
    "frontend": ["react", "vue", "nextjs", "nuxt", "svelte", "shadcn-ui", "tailwindcss"],
    # 数据库
    "database": ["postgresql-template", "mongodb-template", "redis-cache", "sqlalchemy"],
    # DevOps
    "devops": ["dockerfile", "docker-compose", "github-actions", "kubernetes", "terraform"],
    # 全栈
    "fullstack": ["fullstack-template", "saas-boilerplate", "startup-template", "nextjs-boilerplate"],
}

# ── 本地已知模式库 (离线fallback) ──
KNOWN_PATTERNS = {
    "fastapi_crud": {
        "id": "fastapi.crud",
        "stars": "78k+",
        "description": "FastAPI CRUD with Pydantic, 5 endpoints",
        "inputs": {"model_name": "str", "fields": "List[Dict]"}, 
        "template_size": "2.5 KB",
    },
    "react_landing": {
        "id": "react.landing",
        "stars": "100k+",
        "description": "React landing page with Tailwind",
        "inputs": {"title": "str", "sections": "List[Dict]"},
        "template_size": "8 KB",
    },
    "django_admin": {
        "id": "django.admin",
        "stars": "80k+",
        "description": "Django admin with custom models",
        "inputs": {"models": "List[Dict]", "app_name": "str"},
        "template_size": "3 KB",
    },
    "spring_crud": {
        "id": "spring.crud",
        "stars": "75k+",
        "description": "Spring Boot CRUD with JPA",
        "inputs": {"entity": "str", "fields": "List[Dict]"},
        "template_size": "4 KB",
    },
    "nextjs_fullstack": {
        "id": "nextjs.fullstack",
        "stars": "120k+",
        "description": "Next.js fullstack app with API routes",
        "inputs": {"pages": "List[Dict]", "api_routes": "List[Dict]"},
        "template_size": "10 KB",
    },
    "docker_compose_web": {
        "id": "devops.docker-compose",
        "stars": "50k+",
        "description": "Docker Compose: web + db + cache",
        "inputs": {"services": "List[Dict]", "ports": "Dict"},
        "template_size": "1 KB",
    },
}


class HarnessCrawler:
    """Harness 工程爬虫主控"""
    
    def __init__(self):
        self.registry = REGISTRY
        self.extractor = HEPExtractor()
        self.github_crawler = GitHubPatternCrawler(self.extractor)
        self.stats = {"searched": 0, "extracted": 0, "registered": 0, "failed": 0}
    
    def scan_local_patterns(self):
        """从本地已知模式库注册 HEP 组件"""
        for pid, pattern in KNOWN_PATTERNS.items():
            comp = HEPComponent(
                id=pattern["id"],
                name=pattern["id"].replace(".", " ").title(),
                version="1.0.0",
                domain=pattern["id"].split(".")[0],
                subdomain="pattern",
                tags=[pattern["id"].split(".")[0], pattern["id"].split(".")[1], "discovered"],
                inputs={k: {"type": v} for k, v in pattern["inputs"].items()},
                outputs={f"{pid}.output": "code"},
                dependencies=[],
                stars=pattern["stars"],
                description=pattern["description"],
            )
            self.registry.register(comp)
            self.stats["registered"] += 1
            print(f"  ✅ {comp.id:30s} ⭐{comp.stars:8s} | {pattern['description']}")
    
    def crawl_github(self, domain: str = "backend", limit: int = 3):
        """爬取 GitHub 发现模式"""
        if not HAS_NETWORK:
            print("  ⚠️  无网络连接, 跳过 GitHub 爬取")
            return
        
        topics = TOPICS.get(domain, [])
        print(f"\n  爬取 {domain} 领域, {len(topics)} 个主题...")
        
        for topic in topics[:2]:  # Limit to 2 topics to avoid timeout
            print(f"\n    🔍 搜索: {topic}")
            try:
                repos = self.github_crawler.crawl_by_topic(topic, limit=limit)
                self.stats["searched"] += 1
                
                for repo in repos:
                    # 为每个发现的仓库注册一个 HEP 组件引用
                    name = repo.get("full_name", topic).replace("/", ".")
                    comp_id = f"discovered.{name.lower().replace(' ','-')[:40]}"
                    
                    comp = HEPComponent(
                        id=comp_id,
                        name=repo.get("full_name", topic),
                        version="1.0.0",
                        domain=domain,
                        subdomain="discovered",
                        tags=[domain, topic, repo.get("language", "").lower()],
                        inputs={"repo_url": repo.get("html_url", "")},
                        outputs={"clone": "git"},
                        dependencies=[],
                        stars=str(repo.get("stargazers_count", 0)),
                        url=repo.get("html_url", ""),
                    )
                    self.registry.register(comp)
                    self.stats["registered"] += 1
                
                time.sleep(1)  # Rate limit
            except Exception as e:
                print(f"    ❌ {topic}: {e}")
                self.stats["failed"] += 1
    
    def extract_from_directory(self, directory: str):
        """从本地目录提取 HEP 组件"""
        if not os.path.exists(directory):
            print(f"  ❌ 目录不存在: {directory}")
            return
        
        components = self.github_crawler.extract_components(directory)
        for comp_data in components:
            try:
                comp = HEPComponent(
                    id=comp_data.get("id", "extracted.pattern"),
                    name=comp_data.get("name", "Extracted Pattern"),
                    version="1.0.0",
                    domain=comp_data.get("domain", "backend"),
                    subdomain=comp_data.get("subdomain", "template"),
                    tags=comp_data.get("tags", ["extracted"]),
                    inputs=comp_data.get("inputs", {}),
                    outputs=comp_data.get("outputs", {"main": "code"}),
                    dependencies=comp_data.get("dependencies", []),
                    template=comp_data.get("template", ""),
                    author="hep-extractor",
                )
                self.registry.register(comp)
                self.stats["extracted"] += 1
                self.stats["registered"] += 1
            except Exception as e:
                print(f"    ❌ 注册失败: {e}")
                self.stats["failed"] += 1
        
        print(f"  📦 从 {directory} 提取了 {len(components)} 个组件")
    
    def report(self) -> Dict:
        counts = self.registry.count()
        return {
            "searched": self.stats["searched"],
            "extracted": self.stats["extracted"],
            "registered": self.stats["registered"],
            "failed": self.stats["failed"],
            "components_by_domain": counts,
            "total_components": sum(counts.values()),
        }


def run_crawler():
    """运行完整爬虫流程"""
    print("=" * 60)
    print("  Harness 工程爬虫 v1.0")
    print("  从 GitHub 发现模式 → HEP 组件 → 本地数据库")
    print("=" * 60)
    
    crawler = HarnessCrawler()
    
    # Phase 1: 本地已知模式
    print("\n📦 Phase 1: 本地已知模式注册")
    crawler.scan_local_patterns()
    
    # Phase 2: GitHub 爬取
    print("\n🌐 Phase 2: GitHub 模式发现")
    for domain in ["backend", "frontend", "database"]:
        crawler.crawl_github(domain, limit=3)
    
    # Phase 3: 提取已有 Harness 模板
    harness_dir = os.path.join(os.path.dirname(__file__))
    print(f"\n🔍 Phase 3: 从 Harness 自身提取")
    crawler.extract_from_directory(harness_dir)
    
    # Report
    print("\n" + "=" * 60)
    print("  爬虫运行报告")
    print("=" * 60)
    report = crawler.report()
    for k, v in report.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for dk, dv in v.items():
                print(f"    {dk}: {dv}")
        else:
            print(f"  {k}: {v}")
    
    # 保存注册表快照
    snapshot = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "components": [
            {
                "id": c.id,
                "name": c.name,
                "domain": c.domain,
                "tags": c.tags,
                "inputs": list(c.inputs.keys()),
            }
            for c in crawler.registry._components.values()
        ],
    }
    snapshot_path = os.path.join(os.path.dirname(__file__), "templates", "hep_snapshot.json")
    os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    print(f"\n  💾 注册表快照: {snapshot_path}")
    
    return crawler


if __name__ == "__main__":
    run_crawler()
