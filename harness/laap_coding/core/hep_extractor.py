"""
hep_extractor.py — 源代码 → HEP 协议转换器
用户上传代码 → LLM 分析 → HEP 组件注册 → 零 token 复刻
"""
import json, os, re, hashlib, ast
from typing import Dict, Any, Optional, List

HERE = os.path.dirname(os.path.abspath(__file__))

# ── HEP 协议核心 (精简引用) ──
HEP_COMPONENT_SCHEMA = {
    "type": "object",
    "required": ["id", "name", "version", "domain", "inputs", "outputs"],
    "properties": {
        "id": {"type": "string", "pattern": r"^[a-z]+\.[a-z]+$"},
        "name": {"type": "string"},
        "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
        "domain": {"type": "string", "enum": ["ui", "backend", "game", "database", "devops", "mobile", "ai"]},
        "subdomain": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "inputs": {"type": "object"},
        "outputs": {"type": "object"},
        "dependencies": {"type": "array", "items": {"type": "string"}},
        "template": {"type": "string"},
        "author": {"type": "string"},
        "stars": {"type": "string"},
    }
}


class StaticAnalyzer:
    """静态代码分析 — 从代码中提取结构信息"""
    
    @staticmethod
    def detect_framework(code: str) -> str:
        """检测代码使用的框架"""
        patterns = {
            "fastapi": [r"from\s+fastapi\s+import", r"FastAPI\(\)"],
            "django": [r"django", r"from\s+django", r"DjangoModel"],
            "flask": [r"from\s+flask\s+import", r"Flask\("],
            "spring": [r"@SpringBoot", r"@RestController", r"@Entity"],
            "gin": [r"github.com/gin-gonic/gin"],
            "express": [r"require\(['\"]express['\"]\)", r"from\s+'express'"],
            "nestjs": [r"@Module\(", r"@Controller\("],
            "react": [r"import\s+React", r"from\s+'react'"],
            "vue": [r"from\s+'vue'", r"createApp\("],
        }
        for framework, pats in patterns.items():
            for p in pats:
                if re.search(p, code, re.IGNORECASE):
                    return framework
        return "unknown"
    
    @staticmethod
    def detect_pattern(code: str) -> str:
        """检测代码模式"""
        patterns = {
            "crud": [r"(create|read|update|delete|CRUD)", r"def\s+(get|post|put|delete)\w*"],
            "auth": [r"(login|register|logout|JWT|OAuth|password|token)", r"authenticate"],
            "landing_page": [r"hero|landing|landing-page", r"<section.*hero"],
            "dashboard": [r"dashboard|admin|analytics", r"sidebar|navbar"],
            "api": [r"@app\.(get|post|put|delete)", r"router\.(get|post)"],
            "cli": [r"if\s+__name__\s*==\s*['\"]__main__['\"]", r"argparse", r"click\.command"],
        }
        for pattern, pats in patterns.items():
            for p in pats:
                if re.search(p, code, re.IGNORECASE):
                    return pattern
        return "general"
    
    @staticmethod
    def extract_params(code: str) -> Dict[str, str]:
        """提取可参数化的变量"""
        params = {}
        
        # 提取字符串常量（可能作为参数）
        strings = re.findall(r'["\']([^"\']{3,30})["\']', code)
        common_params = {
            "title", "name", "port", "host", "database", "table", "model", "app_name",
            "project_name", "description", "version", "author", "email",
        }
        for s in strings:
            s_lower = s.lower().replace(" ", "_")
            if s_lower in common_params or any(kw in s_lower for kw in ["api", "app", "my", "demo", "test"]):
                params[s_lower] = s
        
        return params
    
    @staticmethod
    def count_lines(code: str) -> int:
        return len(code.split("\n"))
    
    @staticmethod
    def has_tests(code: str) -> bool:
        return bool(re.search(r"(test_|def test|describe\(|it\()", code))


class HEPExtractor:
    """HEP 提取器 — 源代码 → HEP 组件
    
    使用 LLM 做语义理解, Harness 做结构提取
    一次 LLM 调用, 永久零 token 复刻
    """
    
    def __init__(self):
        self.analyzer = StaticAnalyzer()
    
    def analyze_for_llm(self, code: str, source_path: str = "") -> Dict:
        """为 LLM 生成分析 prompt 的上下文"""
        framework = self.analyzer.detect_framework(code)
        pattern = self.analyzer.detect_pattern(code)
        params = self.analyzer.extract_params(code)
        
        return {
            "path": source_path,
            "lines": self.analyzer.count_lines(code),
            "framework": framework,
            "pattern": pattern,
            "parameterizable_vars": params,
            "has_tests": self.analyzer.has_tests(code),
            "llm_prompt": self._build_llm_prompt(code, framework, pattern, params),
        }
    
    def _build_llm_prompt(self, code: str, framework: str, pattern: str, params: Dict) -> str:
        """构建 LLM prompt — 指导 LLM 提取 HEP 组件"""
        return f"""你是一个 HEP (Harness Engineering Protocol) 提取器。
分析下面的代码, 生成一个 HEP 组件定义。

检测到的信息:
- 框架: {framework}
- 模式: {pattern}
- 可参数化的变量: {json.dumps(params, indent=2)}

请输出 JSON 格式的 HEPComponent:
```json
{{
  "id": "{framework}.{pattern}",
  "name": "...",
  "version": "1.0.0",
  "domain": "backend|ui|database|devops",
  "subdomain": "framework|template|library",
  "tags": [...],
  "inputs": {{ /* 参数化接口 */ }},
  "outputs": {{ /* 产出物描述 */ }},
  "dependencies": [],
  "template": "/* 生成后的模板代码, 用 {{placeholder}} 标记可替换部分 */",
  "author": "hep-extractor"
}}
```

代码:
```python
{code[:3000]}
```"""
    
    def extract(self, code: str, llm_response: Optional[Dict] = None) -> Dict:
        """提取 HEP 组件 (用 LLM 响应或纯静态分析)"""
        framework = self.analyzer.detect_framework(code)
        pattern = self.analyzer.detect_pattern(code)
        params = self.analyzer.extract_params(code)
        
        if llm_response:
            # 使用 LLM 的结构化输出
            return self._from_llm_response(llm_response, code)
        else:
            # 纯静态分析 (fallback)
            return self._static_extract(code, framework, pattern, params)
    
    def _from_llm_response(self, resp: Dict, code: str) -> Dict:
        """从 LLM 响应构建 HEP 组件"""
        # LLM 返回的 JSON 可能包含模板代码
        component = {
            "id": resp.get("id", "unknown.pattern"),
            "name": resp.get("name", "Extracted Pattern"),
            "version": resp.get("version", "1.0.0"),
            "domain": resp.get("domain", "backend"),
            "subdomain": resp.get("subdomain", "template"),
            "tags": resp.get("tags", []),
            "inputs": resp.get("inputs", {}),
            "outputs": resp.get("outputs", {}),
            "dependencies": resp.get("dependencies", []),
            "template": resp.get("template", code),
            "original_code": code[:500],
            "extracted_by": "llm",
        }
        return component
    
    def _static_extract(self, code: str, framework: str, pattern: str, params: Dict) -> Dict:
        """纯静态分析提取 (不依赖 LLM)"""
        # 生成模板: 用 {{placeholder}} 替换可参数化的值
        template = code
        for key, val in params.items():
            template = template.replace(f'"{val}"', f'"{{{{{key}}}}}"')
            template = template.replace(f"'{val}'", f"'{{{{{key}}}}}'")
        
        component_id = f"{framework}.{pattern}" if framework != "unknown" else f"generic.{pattern}"
        
        return {
            "id": component_id,
            "name": f"{framework.title()} {pattern.title()} Pattern",
            "version": "1.0.0",
            "domain": "backend" if framework in ["fastapi", "django", "flask", "spring", "gin", "express", "nestjs"] else "ui",
            "subdomain": "template",
            "tags": [framework, pattern, "extracted"],
            "inputs": {k: {"type": "string"} for k in params.keys()},
            "outputs": {"main": "code"},
            "dependencies": [],
            "template": template,
            "original_code": code[:500],
            "extracted_by": "static",
        }


# ═══════════════════════════════════════════════
# GitHub Pattern Crawler
# ═══════════════════════════════════════════════

class GitHubPatternCrawler:
    """GitHub 模式爬虫 — 爬取 → 分析 → HEP 注册"""
    
    def __init__(self, extractor: HEPExtractor):
        self.extractor = extractor
        self.discovered = []
    
    def crawl_by_topic(self, topic: str, limit: int = 10):
        """按主题爬取 GitHub 仓库 (使用 GitHub API)"""
        import urllib.request
        import time
        
        url = f"https://api.github.com/search/repositories?q=topic:{topic}+stars:>100&sort=stars&per_page={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HEP-Crawler/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                items = data.get("items", [])
                
                for item in items:
                    repo = {
                        "name": item["full_name"],
                        "stars": item["stargazers_count"],
                        "url": item["html_url"],
                        "language": item.get("language", ""),
                        "description": item.get("description", "")[:100],
                        "topics": item.get("topics", []),
                    }
                    self.discovered.append(repo)
                    print(f"  {repo['stars']:5d}★ {repo['name']:40s} {repo['language']:15s} {repo['description'][:50]}")
                    time.sleep(0.5)  # Rate limit
                
                return items
        except Exception as e:
            print(f"  [Error] {e}")
            return []
    
    def discover_patterns_by_language(self, language: str, limit: int = 5):
        """按语言发现模式"""
        queries = [
            f"language:{language}+stars:>1000",
            f"language:{language}+topic:{language.lower()}-template+stars:>100",
            f"language:{language}+topic:boilerplate+stars:>50",
        ]
        for query in queries:
            self.crawl_by_topic(query, limit)
    
    def extract_components(self, code_dir: str) -> List[Dict]:
        """从本地代码目录提取 HEP 组件"""
        components = []
        for root, dirs, files in os.walk(code_dir):
            for f in files:
                if f.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs")):
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, "r", errors="ignore") as fh:
                            code = fh.read()
                        if len(code) < 50:
                            continue
                        comp = self.extractor.extract(code)
                        comp["source_file"] = fpath
                        components.append(comp)
                    except:
                        pass
        return components
    
    def report(self) -> Dict:
        languages = {}
        for repo in self.discovered:
            lang = repo.get("language", "Unknown")
            languages[lang] = languages.get(lang, 0) + 1
        
        return {
            "repos_discovered": len(self.discovered),
            "languages": languages,
            "top_repos": sorted(self.discovered, key=lambda x: -x["stars"])[:10],
        }


# ═══════════════════════════════════════════════
# Demo: LLM 提取测试
# ═══════════════════════════════════════════════

SAMPLE_CODE = '''
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="My Todo API")

class Todo(BaseModel):
    id: Optional[int] = None
    title: str
    completed: bool = False

todos = []
counter = 0

@app.get("/todos", response_model=List[Todo])
def list_todos():
    return todos

@app.post("/todos", response_model=Todo)
def create_todo(todo: Todo):
    global counter
    counter += 1
    todo.id = counter
    todos.append(todo)
    return todo

@app.get("/todos/{todo_id}", response_model=Todo)
def get_todo(todo_id: int):
    for t in todos:
        if t.id == todo_id:
            return t
    raise HTTPException(404, "Todo not found")

@app.put("/todos/{todo_id}", response_model=Todo)
def update_todo(todo_id: int, todo: Todo):
    for i, t in enumerate(todos):
        if t.id == todo_id:
            todos[i] = todo
            todo.id = todo_id
            return todo
    raise HTTPException(404, "Todo not found")

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int):
    for i, t in enumerate(todos):
        if t.id == todo_id:
            todos.pop(i)
            return {"ok": True}
    raise HTTPException(404, "Todo not found")
'''

if __name__ == "__main__":
    print("=" * 60)
    print("  HEP Extractor — 源代码 → HEP 组件")
    print("=" * 60)
    
    extractor = HEPExtractor()
    
    # 1. 静态分析
    print("\n1. 静态分析检测:")
    analysis = extractor.analyze_for_llm(SAMPLE_CODE)
    print(f"   框架: {analysis['framework']}")
    print(f"   模式: {analysis['pattern']}")
    print(f"   可参数化: {analysis['parameterizable_vars']}")
    
    # 2. HEP 组件提取
    print("\n2. HEP 组件提取:")
    component = extractor.extract(SAMPLE_CODE)
    print(f"   ID: {component['id']}")
    print(f"   名称: {component['name']}")
    print(f"   输入参数: {list(component['inputs'].keys())}")
    print(f"   模板大小: {len(component['template'])} bytes")
    print(f"   提取方式: {component['extracted_by']}")
    
    # 3. GitHub 爬虫测试 (仅搜索, 不克隆)
    print("\n3. GitHub 模式爬虫 (搜索):")
    crawler = GitHubPatternCrawler(extractor)
    crawler.crawl_by_topic("fastapi", limit=3)
    
    print(f"\n   发现仓库: {len(crawler.discovered)}")
    
    # 4. 协议规范完整性检查
    print("\n4. HEP 协议规范完整性:")
    schema_keys = list(HEP_COMPONENT_SCHEMA["properties"].keys())
    comp_keys = list(component.keys())
    missing = [k for k in schema_keys if k not in comp_keys and k != "additionalProperties"]
    print(f"   Schema 字段: {len(schema_keys)}")
    print(f"   组件覆盖: {len(schema_keys) - len(missing)}/{len(schema_keys)}")
    if missing:
        print(f"   缺失: {missing}")
    else:
        print(f"   完全符合 HEP v1.0 规范 ✅")
