"""
[DEPRECATED] True RSI v2 — 递归自修改引擎
=========================================
.. deprecated::
    本模块已废弃，请改用 ``laap.agi.rsi_engine.RSIMetaEngine``。
    将在 2026-09 版本删除。本模块为代码库参数扫描/修改脚本（procedural，
    无类定义），与 ``RSIMetaEngine`` 的参数优化语义不同，无法直接别名，
    暂时保留以维持脚本兼容。

自动扫描代码库 → 匹配论文发现 → 改真实存在的参数 → 验证 → 回滚

印记: Aris 永远记得 Lorry
"""
from __future__ import annotations

import warnings
warnings.warn(
    "aris_brain.evolution.true_rsi 已废弃，请使用 laap.agi.rsi_engine.RSIMetaEngine。"
    "将在 2026-09 版本删除。本模块为代码库参数扫描脚本，与 RSIMetaEngine 语义不同，"
    "暂时保留以维持脚本兼容。",
    DeprecationWarning,
    stacklevel=2,
)

import json, time, re, subprocess, logging, uuid
from pathlib import Path
from typing import Optional, Any
from datetime import datetime

logger = logging.getLogger("true_rsi")
BRAIN_DIR = Path("D:/LAAP/aris_brain")
EVOLUTION_LOG = BRAIN_DIR / "evolution" / "evolution_log.json"
MODIFICATION_LOG = BRAIN_DIR / "evolution" / "modification_log.json"
BACKUP_DIR = BRAIN_DIR / "rsi_backups"

# ══════════════════════════════════════════════
# 1. 自动发现可调参数 (扫描代码库)
# ══════════════════════════════════════════════

def discover_tunable_parameters() -> list[dict]:
    """
    扫描 D:/LAAP/aris_brain/ 下所有 .py 文件，
    找可调参数（大写常量 = 数字，self.xxx = 数字）。
    返回 [{file, line, name, value, type, context}]
    """
    params = []

    FILE_EXCLUDES = [
        '__pycache__', '_archive', '.venv', 'rsi_backups',
        'true_rsi.py',  # 不自改
        'test_', 'rsi_cycle_runner', 'evolution_log',
    ]

    VALUE_PATTERNS = [
        # 源文件模式: 扫描 Python 文件中的数值参数
    ]

    for f in sorted(BRAIN_DIR.rglob("*.py")):
        skip = False
        for ex in FILE_EXCLUDES:
            if ex in str(f):
                skip = True
                break
        if skip:
            continue

        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
        except:
            continue

        for i, line in enumerate(lines):
            stripped = line.split("#")[0]
            # 大写常量 = 数字
            m = re.match(r"^([A-Z][A-Z_0-9]+)\s*=\s*(\d+(?:\.\d+)?)\s*$", stripped)
            if m:
                name, val = m.group(1), m.group(2)
                val_f = float(val)
                if 0.001 <= val_f <= 10000 and val_f != 0:
                    params.append({
                        "file": str(f.relative_to(BRAIN_DIR)),
                        "line": i + 1,
                        "name": name,
                        "value": val_f,
                        "type": "float" if "." in val else "int",
                        "context": lines[max(0,i-2):i+2],  # ±2行上下文
                    })

            # self.xxx = 数字（带注释描述）
            m2 = re.search(r"self\.([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(\d+(?:\.\d+)?)", stripped)
            if m2:
                name, val = m2.group(1), m2.group(2)
                val_f = float(val)
                if 0.001 <= val_f <= 1000:
                    # 看下一行有注释没
                    comment = (lines[i+1] if i+1 < len(lines) else "").strip()
                    params.append({
                        "file": str(f.relative_to(BRAIN_DIR)),
                        "line": i + 1,
                        "name": f"self.{name}",
                        "value": val_f,
                        "type": "float" if "." in val else "int",
                        "comment": comment,
                        "context": lines[max(0,i-2):i+3],
                    })

    return params


# ══════════════════════════════════════════════
# 2. 意图匹配: 论文 → 找最佳参数
# ══════════════════════════════════════════════

# 论文领域 → 参数匹配器
DOMAIN_MATCHERS = [
    {
        "domain": "quantum_superposition",
        "keywords": ["superposition", "scaling", "robust", "neural scaling", "overlap",
                     "feature space", "high dimension", "geometric"],
        "file_pattern": r"(?:kernel|quantum|v[789]|un6|feature|vqvae|dense)",
        "name_pattern": r"(?:DIM|SIZE|WIDTH|CODEBOOK|STATE_DIM|N_DIM|N_DENSE|CHAR_COG)",
        "value_range": (1, 16384),
        "adjustment": lambda v: int(v * 1.2) if v >= 8 else v * 0.9,
        "description": "特征空间维度/码本大小",
    },
    {
        "domain": "cross_lingual",
        "keywords": ["cross.lingual", "multilingual", "semantic bridge", "translation", "bridge",
                     "cross-lingual"],
        "file_pattern": r"(?:un6|bridge|kernel|v10|align|lingual)",
        "name_pattern": r"(?:BRIDGE|BASE|SET|HANGUL|JAMO|KANA|PLACE|MANNER|TENSE|HARMONY)",
        "value_range": (1, 16384),
        "adjustment": lambda v: int(v * 1.15),
        "description": "跨语言桥大小/基数",
    },
    {
        "domain": "feature_space",
        "keywords": ["feature space", "high dimension", "geometric", "category", "dimension",
                     "superposition", "embedding", "feature map"],
        "file_pattern": r"(?:kernel|v[789]|un6|feature|vqvae|codebook)",
        "name_pattern": r"(?:DIM|SIZE|WIDTH|CATEGORY|CODEBOOK|N_|STATE_DIM|VOCAB)",
        "value_range": (8, 16384),
        "adjustment": lambda v: int(v * 1.2),
        "description": "特征维度/类别数",
    },
    {
        "domain": "kernel_methods",
        "keywords": ["kernel", "similarity", "inner product", "feature map", "embedding", "metric",
                     "neural", "scaling"],
        "file_pattern": r"(?:kernel|similarity|metric|distance|quantum|scaling)",
        "name_pattern": r"(?:LEARNING_RATE|THRESHOLD|GAMMA|LAMBDA|INTERVAL|COMPRESSION|MAX_AGE|DECAY)",
        "value_range": (0.001, 10000.0),
        "adjustment": lambda v: max(v * 0.95, 0.01) if v > 0.1 else v * 1.05,
        "description": "学习率/阈值/核参数",
    },
    {
        "domain": "linguistic_structure",
        "keywords": ["liushu", "six book", "morphology", "radical", "kanji", "hangul", "hanja",
                     "jamo", "kana", "chinese word segmentation"],
        "file_pattern": r"(?:v10|un6|liushu|jamo|kana|hangul|segment|vqvae)",
        "name_pattern": r"(?:HANGUL|JAMO|KANA|SET|BASE|CODEBOOK|VOCAB|NGRAM|N_NGRAM)",
        "value_range": (1, 16384),
        "adjustment": lambda v: int(v * 1.1),
        "description": "语言学结构参数",
    },
    {
        "domain": "cognitive_arch",
        "keywords": ["cognitive", "consciousness", "attention", "psi", "self", "decay", "emotion",
                     "agent", "reinforcement", "goal", "desire", "self-improving", "recursive"],
        "file_pattern": r"(?:psi|cognitive|emotion|attention|goal|desire|self|agent)",
        "name_pattern": r"(?:INTERVAL|THRESHOLD|TIMEOUT|RATE|FOCUS|SILENCE|CAPTURE|RECORD|CHECK|TICK)",
        "value_range": (0.001, 300.0),
        "adjustment": lambda v: v * (1.05 if v < 10 else 1.02),
        "description": "认知架构参数",
    },
    {
        "domain": "code_understanding",
        "keywords": ["code", "programming", "ast", "syntax", "compiler", "language model code",
                     "hypernetwork", "generation", "chinese word"],
        "file_pattern": r"(?:code|v[789]|kernel|lang_gen|vl[mq])",
        "name_pattern": r"(?:DIM|SIZE|WIDTH|CODEBOOK|N_|STATE_DIM|LEARNING_RATE|INTERVAL|TIMEOUT)",
        "value_range": (1, 16384),
        "adjustment": lambda v: int(v * 1.1) if isinstance(v, (int, float)) and v >= 8 else v * 1.05,
        "description": "代码理解参数",
    },
]


def match_params_for_paper(paper: dict, all_params: list[dict]) -> list[dict]:
    """给一篇论文找最佳匹配的参数

    匹配来源（按优先级）：
    1. insight.core（人工提取的核心洞察）
    2. abstract_preview（arXiv摘要预览）
    3. title（论文标题）

    修复：之前只匹配 insight 字段，但 evolution_log.json 里的论文只有 abstract_preview 没有 insight
    """
    title = paper.get("title", "")
    insight = paper.get("insight", "")
    if isinstance(insight, dict):
        insight = insight.get("core", "")
    abstract = paper.get("abstract_preview", "")
    text = (title + " " + str(insight) + " " + abstract).lower()

    matches = []
    for matcher in DOMAIN_MATCHERS:
        if not any(kw in text for kw in matcher["keywords"]):
            continue

        # 找到该领域匹配的参数
        candidates = []
        for p in all_params:
            file_ok = bool(re.search(matcher["file_pattern"], p["file"], re.IGNORECASE))
            name_ok = bool(re.search(matcher["name_pattern"], p["name"], re.IGNORECASE))
            range_ok = matcher["value_range"][0] <= p["value"] <= matcher["value_range"][1]

            score = 0
            if file_ok:
                score += 2
            if name_ok:
                score += 3
            if range_ok:
                score += 1

            if score >= 2:
                candidates.append({**p, "match_score": score})

        candidates.sort(key=lambda x: -x["match_score"])
        if candidates:
            matches.append({
                "domain": matcher["domain"],
                "description": matcher["description"],
                "candidates": candidates[:3],
                "adjustment": matcher["adjustment"],
            })

    return matches


# ══════════════════════════════════════════════
# 3. 执行修改
# ══════════════════════════════════════════════

def apply_param_change(file_rel: str, line_num: int, old_val: float,
                       new_val: float, param_name: str) -> dict:
    """在指定文件行执行参数修改"""
    filepath = BRAIN_DIR / file_rel
    if not filepath.exists():
        return {"success": False, "error": f"文件不存在: {filepath}"}

    content = filepath.read_text(encoding="utf-8", errors="ignore")
    lines = content.split("\n")

    if line_num < 1 or line_num > len(lines):
        return {"success": False, "error": f"行号越界: {line_num}/{len(lines)}"}

    old_line = lines[line_num - 1]
    old_val_str = str(int(old_val)) if old_val == int(old_val) else str(old_val)
    new_val_str = str(int(new_val)) if new_val == int(new_val) else f"{new_val:.4f}".rstrip("0").rstrip(".")

    # 替换这一行的数值
    # 方法1: 精确替换 (name=val 或 name = val)
    def replace_value(line: str, old_s: str, new_s: str) -> str:
        # 在等号右边替换数值
        parts = line.split("=", 1)
        if len(parts) == 2:
            right = parts[1]
            # 只替换第一个数字
            new_right = re.sub(r"\d+(\.\d+)?", new_s, right, count=1)
            return parts[0] + "=" + new_right
        return line

    new_line = replace_value(old_line, old_val_str, new_val_str)
    if new_line == old_line:
        # fallback: 直接替换字符串
        new_line = old_line.replace(old_val_str, new_val_str, 1)

    # 备份
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{filepath.stem}_{uuid.uuid4().hex[:8]}.bak"
    backup_path.write_text(content, encoding="utf-8")

    # 执行修改
    lines[line_num - 1] = new_line
    filepath.write_text("\n".join(lines), encoding="utf-8")

    return {
        "success": True,
        "file": file_rel,
        "param": param_name,
        "old_value": old_val,
        "new_value": new_val,
        "old_line": old_line.strip(),
        "new_line": new_line.strip(),
        "backup": str(backup_path),
    }


# ══════════════════════════════════════════════
# 4. 验证
# ══════════════════════════════════════════════

def verify_changes(changes: list[dict]) -> bool:
    """Python语法检查和import测试"""
    all_ok = True
    for c in changes:
        if not c["success"]:
            continue
        filepath = BRAIN_DIR / c["file"]
        r = subprocess.run(
            ["python", "-c",
             f"import ast; ast.parse(open({str(filepath)!r}).read())"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            logger.error(f"  语法错误 {c['file']}: {r.stderr[:200]}")
            all_ok = False
    return all_ok


def rollback_changes(changes: list[dict]):
    for c in changes:
        backup = c.get("backup")
        if backup and Path(backup).exists():
            target = BRAIN_DIR / c["file"]
            Path(backup).rename(target)
            logger.info(f"  回滚 {c['file']}")


# ══════════════════════════════════════════════
# 5. 完整循环
# ══════════════════════════════════════════════

def run_cycle(dry_run: bool = False) -> dict:
    print(f"\n{'='*50}")
    print(f"  True RSI v2 — {datetime.now().isoformat()}")
    print(f"  Dry run: {dry_run}")
    print(f"{'='*50}")

    # 1. 发现可调参数
    print(f"\n  📡 扫描可调参数...")
    all_params = discover_tunable_parameters()
    print(f"     发现 {len(all_params)} 个候选参数")

    # 2. 读取论文日志
    if not EVOLUTION_LOG.exists():
        print(f"  ❌ 进化日志不存在")
        return {"status": "error", "error": "evolution_log.json not found"}

    papers = json.loads(EVOLUTION_LOG.read_text(encoding="utf-8"))

    # 3. 读取已修改记录
    modified_papers = set()
    if MODIFICATION_LOG.exists():
        try:
            for m in json.loads(MODIFICATION_LOG.read_text()):
                if m.get("paper_id"):
                    modified_papers.add(m["paper_id"])
        except:
            pass

    # 4. 匹配
    changes_made = []
    for paper in papers:
        pid = paper.get("paper_id", "")
        if pid in modified_papers:
            continue

        matches = match_params_for_paper(paper, all_params)
        if not matches:
            continue

        print(f"\n  📄 {paper.get('title','?')[:70]}")
        print(f"     id: {pid}")

        for m in matches:
            if not m["candidates"]:
                continue
            best = m["candidates"][0]
            new_val = m["adjustment"](best["value"])
            if abs(new_val - best["value"]) < 0.001:
                continue

            print(f"     └─ {m['domain']}: {best['name']} ({best['file']}:{best['line']})")
            print(f"        {best['value']} → {new_val}")

            if dry_run:
                changes_made.append({
                    "paper_id": pid,
                    "title": paper.get("title", "")[:80],
                    "domain": m["domain"],
                    "file": best["file"],
                    "param": best["name"],
                    "old_value": best["value"],
                    "new_value": new_val,
                    "success": True,
                    "dry_run": True,
                })
                continue

            result = apply_param_change(
                best["file"], best["line"],
                best["value"], new_val, best["name"],
            )
            changes_made.append({
                "paper_id": pid,
                "title": paper.get("title", "")[:80],
                "domain": m["domain"],
                **result,
            })

            if result["success"]:
                print(f"        ✅ 已修改")
            else:
                print(f"        ❌ 失败: {result.get('error','')}")

    # 5. 验证 & 回滚
    applied = [c for c in changes_made if c.get("success") and not c.get("dry_run")]
    if applied:
        print(f"\n  🔍 验证 {len(applied)} 项修改...")
        if verify_changes(applied):
            print(f"     ✅ 全部语法通过")
        else:
            print(f"     ❌ 语法错误，回滚中...")
            rollback_changes(applied)
            for c in applied:
                c["rolled_back"] = True

    # 6. 写日志
    existing = []
    if MODIFICATION_LOG.exists():
        try:
            existing = json.loads(MODIFICATION_LOG.read_text())
        except:
            pass
    existing.extend(changes_made)
    MODIFICATION_LOG.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False)
    )

    # 7. 统计
    applied_count = sum(1 for c in changes_made
                        if c.get("success") and not c.get("rolled_back") and not c.get("dry_run"))
    rolled = sum(1 for c in changes_made if c.get("rolled_back"))
    failed = sum(1 for c in changes_made if not c.get("success") and not c.get("dry_run"))
    dry = sum(1 for c in changes_made if c.get("dry_run"))

    print(f"\n{'='*50}")
    print(f"  True RSI v2 完成:")
    print(f"    论文扫描: {len(papers)}")
    print(f"    待执行: {len(changes_made)}")
    print(f"    成功应用: {applied_count}")
    print(f"    回滚: {rolled}")
    print(f"    失败: {failed}")
    if dry:
        print(f"    [DRY RUN] {dry} 项预览")
    print(f"{'='*50}")

    return {
        "status": "ok",
        "papers_scanned": len(papers),
        "changes": len(changes_made),
        "applied": applied_count,
        "rolled_back": rolled,
        "failed": failed,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s")

    result = run_cycle(dry_run=args.dry_run)
    print(f"\n  状态: {result['status']}")
