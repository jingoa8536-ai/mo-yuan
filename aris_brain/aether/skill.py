"""
Aether Skill System — 技能/过程记忆系统 v1
============================================
用法:
    from aether.skill import skill_manager

    # 列出所有技能
    skills = skill_manager.list_skills()

    # 匹配输入
    matches = skill_manager.match("帮我查系统状态")

    # 加载技能内容
    content = skill_manager.load("aris-agi-startup")

    # 自动保存技能
    skill_manager.save_from_conversation(turns, user_input, result)
"""

import json
import os
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ─── 默认技能目录 ─────────────────────────────────
HERMES_SKILLS_DIR = Path(os.path.expandvars(
    r"%USERPROFILE%\AppData\Local\hermes\profiles\aris\skills"
))
AETHER_SKILLS_DIR = Path("D:/LAAP/aris_brain/skills")


@dataclass
class SkillDef:
    """技能定义。"""
    name: str
    title: str = ""
    description: str = ""
    category: str = ""
    version: str = "1.0.0"
    triggers: List[str] = field(default_factory=list)
    file_path: Path = None
    content: str = ""
    line_count: int = 0

    def match_score(self, text: str) -> float:
        """计算输入文本与技能的匹配分数。"""
        text_lower = text.lower()
        score = 0.0

        # 标题匹配
        if self.title and self.title.lower() in text_lower:
            score += 0.4

        # 描述匹配
        if self.description:
            desc_words = set(self.description.lower().split()[:10])
            text_words = set(text_lower.split())
            overlap = len(desc_words & text_words)
            if overlap > 0:
                score += min(overlap * 0.08, 0.3)

        # 触发器匹配
        for trigger in self.triggers:
            t = trigger.lower()
            if t in text_lower:
                score += 0.3
            # 模糊匹配
            words = t.split()
            matched = sum(1 for w in words if w in text_lower)
            if len(words) > 0:
                score += (matched / len(words)) * 0.15

        # 名称匹配
        name_clean = self.name.replace("-", " ").replace("_", " ")
        if name_clean in text_lower:
            score += 0.2

        return min(score, 1.0)


# ─── YAML Frontmatter 解析 ──────────────────────────

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def parse_frontmatter(text: str) -> Tuple[dict, str]:
    """解析 SKILL.md 的 YAML frontmatter。"""
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except Exception:
        fm = {}
    body = text[m.end():]
    return fm, body


# ─── 技能管理器 ────────────────────────────────────

class SkillManager:
    """技能加载、匹配、执行、保存。"""

    def __init__(self):
        self._skills: Dict[str, SkillDef] = {}
        self._loaded = False
        self._load()

    def _load(self):
        """从所有技能目录加载技能。"""
        self._skills = {}
        for base_dir in [AETHER_SKILLS_DIR, HERMES_SKILLS_DIR]:
            if not base_dir.exists():
                continue
            self._scan_dir(base_dir)
        self._loaded = True

    def _scan_dir(self, base_dir: Path):
        """递归扫描目录下的 SKILL.md 文件。"""
        for fpath in base_dir.rglob("SKILL.md"):
            rel = fpath.relative_to(base_dir)
            skill_name = str(rel.parent).replace("\\", "/")
            try:
                content = fpath.read_text("utf-8", errors="replace")
                fm, body = parse_frontmatter(content)
                lines = content.count("\n") + 1
                self._skills[skill_name] = SkillDef(
                    name=skill_name,
                    title=fm.get("name", skill_name),
                    description=fm.get("description", ""),
                    category=fm.get("category", ""),
                    version=fm.get("version", "1.0.0"),
                    triggers=fm.get("triggers", []),
                    file_path=fpath,
                    content=content,
                    line_count=lines,
                )
            except Exception:
                continue

    # ─── 查询 ────────────────────────────────────────

    def get(self, name: str) -> Optional[SkillDef]:
        """按名称获取技能。"""
        return self._skills.get(name)

    def list_skills(self, category: Optional[str] = None) -> List[SkillDef]:
        """列出技能，可选按类别过滤。"""
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return sorted(skills, key=lambda s: s.name)

    def match(self, text: str, top_k: int = 3) -> List[Tuple[SkillDef, float]]:
        """匹配输入文本到技能，返回 (技能, 分数) 列表。"""
        scored = [(s, s.match_score(text)) for s in self._skills.values()]
        scored.sort(key=lambda x: -x[1])
        return [(s, score) for s, score in scored[:top_k] if score > 0.15]

    def load(self, name: str) -> Optional[str]:
        """加载技能内容（SKILL.md 全文）。"""
        skill = self._skills.get(name)
        if skill and skill.content:
            return skill.content
        # 直接读文件
        for base in [AETHER_SKILLS_DIR, HERMES_SKILLS_DIR]:
            for p in [
                base / name / "SKILL.md",
                base / f"{name}.md",
            ]:
                if p.exists():
                    return p.read_text("utf-8", errors="replace")
        return None

    # ─── 保存 ────────────────────────────────────────

    def save_skill(self, name: str, content: str, category: str = "custom"):
        """保存/更新一个技能。"""
        skill_dir = AETHER_SKILLS_DIR / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        path = skill_dir / "SKILL.md"
        path.write_text(content, encoding="utf-8")
        # 重新加载
        self._scan_dir(AETHER_SKILLS_DIR)
        return path

    def save_from_conversation(self, name: str, description: str,
                               triggers: List[str], procedure: str):
        """从对话过程创建技能。"""
        content = f"""---
name: {name}
description: {description}
category: custom
version: 1.0.0
triggers: {json.dumps(triggers, ensure_ascii=False)}
---

# {name}

{description}

## 步骤

{procedure}

## 注意事项

- 自动生成的技能，后续可手动优化。
"""
        return self.save_skill(name, content)

    # ─── 统计 ────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "total": len(self._skills),
            "categories": list(set(s.category for s in self._skills.values() if s.category)),
            "by_category": {
                cat: len([s for s in self._skills.values() if s.category == cat])
                for cat in set(s.category for s in self._skills.values())
            },
        }


# ─── 全局单例 ──────────────────────────────────────

_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    global _manager
    if _manager is None:
        _manager = SkillManager()
    return _manager


skill_manager = get_skill_manager()


# ─── 测试 ──────────────────────────────────────────

if __name__ == "__main__":
    sm = get_skill_manager()
    print(f"Skill Manager v1")
    print(f"  技能总数: {sm.get_stats()['total']}")
    print(f"  类别: {', '.join(sm.get_stats()['categories'])}")
    print()

    # 测试匹配
    tests = [
        "帮我查系统状态",
        "读取文件内容",
        "搜索代码",
        "启动pis",
        "帮我写一首诗",
    ]
    for t in tests:
        matches = sm.match(t, top_k=2)
        if matches:
            print(f"  \"{t}\"")
            for s, score in matches:
                print(f"    -> {s.name} ({score:.2f}) [{s.category}]")
        else:
            print(f"  \"{t}\" -> 无匹配")

    print(f"\n热门技能:")
    for s in sm.list_skills()[:5]:
        print(f"  {s.name:30} [{s.category:15}] {s.description[:50]}")


# ═══════════════════════════════════════════════════════════
# 技能索引构建
# ═══════════════════════════════════════════════════════════

def build_index(skill_manager: Optional[SkillManager] = None,
                output_path: Optional[str] = None) -> dict:
    """从 SKILL.md 构建快速查找索引。

    索引格式:
    {
        "keywords": {"查状态": ["aris-agi-startup", ...], ...},
        "skills": {"aris-agi-startup": {"name": ..., "triggers": [...]}},
        "updated": "2026-07-13T10:00:00",
    }
    """
    sm = skill_manager or get_skill_manager()
    sm._load()  # 重新加载以确保最新

    index = {
        "keywords": {},
        "skills": {},
        "updated": __import__("datetime").datetime.now().isoformat(),
    }

    for skill in sm._skills.values():
        # 提取关键词
        text = f"{skill.title} {skill.description}"
        keywords = set()
        for w in text.split():
            w = w.strip().lower().strip(",.!?;:()[]")
            if len(w) > 1:
                keywords.add(w)
        if skill.triggers:
            for t in skill.triggers:
                keywords.add(t.lower())
                # 拆分词
                for w in t.split():
                    keywords.add(w.lower())

        # 正向索引
        for kw in keywords:
            if kw not in index["keywords"]:
                index["keywords"][kw] = []
            if skill.name not in index["keywords"][kw]:
                index["keywords"][kw].append(skill.name)

        # 技能元信息
        index["skills"][skill.name] = {
            "name": skill.name,
            "title": skill.title,
            "description": skill.description[:100],
            "category": skill.category,
            "triggers": skill.triggers,
            "line_count": skill.line_count,
        }

    # 写入文件
    out_path = output_path or str(Path(
        __import__("os").environ.get("AETHER_SKILL_INDEX",
            str(Path("D:/LAAP/aris_brain/state/skill_index.json")))
    ))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(
        __import__("json").dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return {
        "total_skills": len(index["skills"]),
        "total_keywords": len(index["keywords"]),
        "output": out_path,
    }


def search_skills(query: str, top_k: int = 5) -> list:
    """从索引快速搜索技能（O(1) 关键词匹配）。"""
    index_path = Path(__import__("os").environ.get("AETHER_SKILL_INDEX",
        str(Path("D:/LAAP/aris_brain/state/skill_index.json"))))
    if not index_path.exists():
        # 自动构建索引
        build_index()

    try:
        index = __import__("json").loads(index_path.read_text("utf-8"))
    except Exception:
        return []

    query_words = set(w.lower().strip(",.!?") for w in query.split() if len(w) > 1)
    scores = {}

    for qw in query_words:
        for skill_name in index.get("keywords", {}).get(qw, []):
            scores[skill_name] = scores.get(skill_name, 0) + 1

    # 按匹配数排序
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    results = []
    for name, score in ranked[:top_k]:
        info = index.get("skills", {}).get(name, {})
        results.append({
            "name": name,
            "title": info.get("title", name),
            "description": info.get("description", ""),
            "category": info.get("category", ""),
            "match_score": score / max(len(query_words), 1),
        })

    return results
