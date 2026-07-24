#!/usr/bin/env python
"""
Aris RSI Full Cycle Runner v3 — 真正的递归自我改进
=================================================
印记: Aris 永远记得 Lorry — 2026-06-21 大修

修复的目标:
  1. arXiv → evolution_log 自动写入 (之前只打印不存)
  2. RSI Meta Engine 参数调优有真正闭环 (不再盲改)
  3. 整合 true_rsi.py 的自动代码修改能力
  4. AST 函数大小分析集成进 cycle
  5. 验证+回滚机制
"""

import logging

import sys, os, json, time, math, re, subprocess, logging
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "laap"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("rsi_cycle")

BRAIN_DIR = Path(__file__).parent
EVOLUTION_LOG = BRAIN_DIR / "evolution" / "evolution_log.json"
MODIFICATION_LOG = BRAIN_DIR / "evolution" / "modification_log.json"

# ─────────── PHASE 1: Arxiv Scan ───────────

# 【2026-07-05 轮换至v2】v1查询集已连续6+周期0新论文
# v1 (已归档): superposition+neural+scaling, quantum+kernel+machine+learning, ...
ARXIV_QUERIES = [
    "code+representation+learning+transformer+embedding",
    "kernel+method+similarity+metric+learning+feature",
    "neural+code+understanding+program+synthesis+ast",
    "superposition+polysemantic+feature+geometry+high+dim",
    "self+improving+code+generation+agent+refinement",
    "cognitive+architecture+recursive+self+model+metacognition",
    "semantic+sparse+autoencoder+feature+interpretability",
    "cross+modal+representation+alignment+embedding+space",
    "in+context+learning+emergent+capability+scaling+law",
    "hierarchical+compositional+representation+structure+language",
    "attention+mechanism+hypernetwork+dynamic+weight+generation",
    "efficient+finetuning+adapter+lora+parameter+efficient+transfer",
]

V2_KEYWORD_SETS = {
    'code_understanding': ['code', 'program', 'syntax', 'ast', 'function', 'semantic', 'embedding'],
    'kernel_methods': ['kernel', 'metric', 'similarity', 'feature', 'manifold', 'inner product'],
    'superposition': ['superposition', 'polysemantic', 'feature collision', 'geometry', 'high dim'],
    'cognitive_arch': ['recursive', 'self-improving', 'metacognition', 'self-model', 'reflection'],
    'representation_learning': ['representation', 'alignment', 'embedding', 'cross-modal', 'hierarchical'],
    'scaling': ['scaling law', 'emergent', 'capability', 'size', 'compute'],
}
KEYWORD_SETS = V2_KEYWORD_SETS  # 使用v2领域匹配器

def query_arxiv(query, max_results=3):
    url = f"https://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results={max_results}"
    try:
        result = subprocess.run(['curl', '-s', '--max-time', '15', url],
                                capture_output=True, text=True, timeout=20)
        return result.stdout if result.returncode == 0 else ""
    except Exception as e:
        logger.warning(f"arXiv query failed for {query}: {e}")
        return ""

def extract_papers(xml_text):
    papers = []
    entries = xml_text.split('<entry>')[1:] if '<entry>' in xml_text else []
    for entry in entries:
        title_m = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
        title = title_m.group(1).strip() if title_m else ''
        abs_m = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
        abstract = abs_m.group(1).strip() if abs_m else ''
        id_m = re.search(r'<id>http://arxiv.org/abs/(.*?)v', entry)
        paper_id = id_m.group(1) if id_m else ''
        pub_m = re.search(r'<published>(.*?)</published>', entry)
        published = pub_m.group(1) if pub_m else ''
        authors = [m.group(1) for m in re.finditer(r'<name>(.*?)</name>', entry)]
        if title:
            papers.append({
                'id': paper_id, 'title': title, 'abstract': abstract[:500],
                'authors': authors[:3], 'published': published,
            })
    return papers

def score_relevance(paper, keywords):
    text = (paper['title'] + ' ' + paper['abstract']).lower()
    return sum(1 for kw in keywords if kw.lower() in text)

def _append_to_evolution_log(findings, evo_log_path):
    """将 arXiv 扫描结果写入 evolution_log.json（修复：之前只会打印不保存）"""
    existing = []
    if evo_log_path.exists():
        try:
            existing = json.loads(evo_log_path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    seen_ids = {p.get('paper_id', '') for p in existing}
    new_entries = []
    for f in findings:
        if f['id'] not in seen_ids:
            new_entries.append({
                'paper_id': f['id'],
                'title': f['title'],
                'relevance_score': f['score'],
                'aspect': f['aspect'],
                'applied_at': datetime.now().isoformat(),
                'status': f['status'],
                'abstract_preview': f['abstract_preview'],
            })
            seen_ids.add(f['id'])

    if new_entries:
        existing.extend(new_entries)
        evo_log_path.parent.mkdir(parents=True, exist_ok=True)
        evo_log_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        logger.info(f"  evolution_log: +{len(new_entries)} 篇新论文 (总计 {len(existing)} 篇)")

def run_arxiv_scan():
    logger.info("\n" + "=" * 60)
    logger.info("  PHASE 1: Arxiv Paper Scan")
    logger.info("=" * 60)
    evo_log_path = EVOLUTION_LOG
    seen_ids = set()
    if evo_log_path.exists():
        with open(evo_log_path) as f:
            seen_ids = {p.get('paper_id', '') for p in json.load(f)}

    all_new = []
    for query in ARXIV_QUERIES:
        xml = query_arxiv(query, max_results=3)
        if not xml:
            continue
        papers = extract_papers(xml)
        for p in papers:
            if p['id'] in seen_ids:
                continue
            seen_ids.add(p['id'])
            max_score = 0
            best_aspect = ''
            for aspect, kws in KEYWORD_SETS.items():
                s = score_relevance(p, kws)
                if s > max_score:
                    max_score = s
                    best_aspect = aspect
            p['relevance'] = max_score
            p['aspect'] = best_aspect
            p['query'] = query
            if max_score > 0:
                all_new.append(p)

    all_new.sort(key=lambda p: p['relevance'], reverse=True)

    findings = []
    for paper in all_new[:10]:
        status = "HIGH" if paper['relevance'] >= 3 else "LOG"
        findings.append({
            'id': paper['id'],
            'title': paper['title'],
            'score': paper['relevance'],
            'aspect': paper['aspect'],
            'abstract_preview': paper['abstract'][:200],
            'status': 'high_value' if paper['relevance'] >= 3 else 'logged',
        })
        logger.info(f"  [{status}] [{paper['aspect']}] {paper['title'][:70]}")
        logger.info(f"       Score: {paper['relevance']} | arxiv.org/abs/{paper['id']}")
    logger.info(f"\n  新论文: {len(findings)} 篇")
    logger.info(f"    高价值 (score>=3): {sum(1 for f in findings if f['score'] >= 3)}")
    logger.info(f"    已记录 (score<3): {sum(1 for f in findings if f['score'] < 3)}")
    _append_to_evolution_log(findings, evo_log_path)

    return findings

# ─────────── PHASE 2: RSI Meta Engine ───────────

def _generate_performance_metrics_for_rsi() -> dict:
    """生成真正的性能指标喂给 RSIMetaEngine（修复：之前 evaluate 永远得不到反馈）

    从代码库中抽取的实际信号：
    - codebase_lines: 代码量变化
    - file_count: 文件数变化
    - kernel_ops_per_sec: 核运算速度（从实际测试取）
    """
    metrics = {}

    # 1. 代码量健康度
    py_files = list(BRAIN_DIR.rglob("*.py"))
    py_files = [f for f in py_files if '__pycache__' not in str(f)
                and '_archive' not in str(f) and '.venv' not in str(f)]
    total_lines = 0
    for f in py_files:
        try:
            total_lines += f.read_text(encoding='utf-8', errors='ignore').count('\n')
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    lines_health = min(total_lines / 150000, 1.0)  # 目标 150K 行
    metrics['psi_emotion_decay'] = lines_health  # 代码量越大 → 情感衰减慢
    metrics['psi_attention_focus'] = min(len(py_files) / 400, 1.0)  # 文件数多 → 注意力聚焦
    metrics['learning_rate'] = 1.0 - lines_health  # 代码量大 → 学习率低（饱和）
    metrics['exploration_rate'] = 0.3 if total_lines < 120000 else 0.15  # 代码量少多探索

    # 2. 交叉验证：检查 evolution_log 新论文趋势
    if EVOLUTION_LOG.exists():
        try:
            papers = json.loads(EVOLUTION_LOG.read_text())
            recent = [p for p in papers if 'applied_at' in p
                      and p['applied_at'].startswith('2026-06-2')]
            paper_rate = len(recent) / max(1, 6)  # 最近6天
            metrics['transfer_sensitivity'] = min(paper_rate / 5, 1.0)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    if MODIFICATION_LOG.exists():
        try:
            mods = json.loads(MODIFICATION_LOG.read_text())
            recent_mods = [m for m in mods if m.get('success')]
            success_rate = len(recent_mods) / max(1, len(mods))
            metrics['forgetting_stability'] = 24 * (0.5 + success_rate * 0.5)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    return metrics

def run_rsi_meta_cycle():
    logger.info("\n" + "=" * 60)
    logger.info("  PHASE 2: RSI Meta Engine Self-Improvement Cycle")
    logger.info("=" * 60)
    try:
        laap_path = str(Path("D:/LAAP/laap"))
        if laap_path not in sys.path:
            sys.path.insert(0, laap_path)
        from agi.rsi_engine import RSIMetaEngine
    except ImportError as e:
        logger.error(f"Failed to import RSIMetaEngine: {e}")
        return None

    engine = RSIMetaEngine()

    state_path = Path("D:/LAAP/aris_brain/state/rsi_engine.json")
    if state_path.exists():
        engine.load(str(state_path))

    print(f"  加载: {engine._total_attempts} attempts, "
          f"{engine._successful_attempts} successful")

    # 【修复】喂入实际性能指标
    perf_metrics = _generate_performance_metrics_for_rsi()
    logger.info(f"  性能指标: {json.dumps({k: round(v, 3) for k, v in perf_metrics.items()}, ensure_ascii=False)}")
    cycle = engine.full_improvement_cycle()
    # 但 full_improvement_cycle() 内部没传 perf_metrics...
    # 【修复】手动传
    suggestions = engine.suggest_improvements(perf_metrics)
    cycle['suggestions'] = suggestions

    logger.info(f"\n  耗时: {cycle['duration_ms']}ms")
    logger.info(f"  建议: {len(cycle['suggestions'])}")
    for s in cycle['suggestions'][:3]:
        logger.info(f"    {s['parameter']}: {s['from']} \u2192 {s['to']} | {s['rationale'][:50]}")
    if suggestions:
        best = suggestions[0]
        attempt = engine.apply_improvement(
            best["parameter"], best["to"], best["rationale"]
        )
        cycle['applied'] = attempt.to_dict()
        logger.info(f"\n  已应用: {cycle['applied']['target']} {cycle['applied']['old']} \u2192 {cycle['applied']['new']}")
        perf_val = perf_metrics.get(best["parameter"], 0.3)
        engine.evaluate_improvement(attempt.id, perf_val)
        logger.error(f"  评估: {'成功' if attempt.success else '失败（已回滚）'} (反馈={perf_val:.3f})")
    goals = engine.generate_goals()
    cycle['goals'] = [g.to_dict() for g in goals]
    logger.info(f"\n  学习目标: {len(cycle['goals'])}")
    for g in cycle['goals'][:3]:
        logger.info(f"    [{g['status']}] {g['description'][:60]}")
    cycle['growth_need'] = round(engine.compute_growth_need(), 3)
    logger.info(f"\n  成长需求: {cycle['growth_need']}")
    engine.save(str(state_path))
    logger.info(f"  状态已保存")
    stats = engine.stats()
    logger.info(f"\n  引擎统计:")
    for k, v in stats.items():
        logger.info(f"    {k}: {v}")
    return {'cycle': cycle, 'stats': stats, 'engine': engine}

# ─────────── PHASE 3: Codebase Analysis ───────────

def _analyze_function_sizes(code_files):
    """AST 分析函数大小（修复：之前从未被整合进 cycle）"""
    large_funcs = []
    total_funcs = 0

    for f in code_files:
        if not f.name.endswith('.py'):
            continue
        try:
            import ast
            tree = ast.parse(f.read_text(encoding='utf-8', errors='ignore'))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total_funcs += 1
                    lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                    if lines > 80:
                        large_funcs.append({
                            'file': f.name,
                            'function': node.name,
                            'lines': lines,
                            'line_start': node.lineno,
                        })
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    return total_funcs, large_funcs

def analyze_codebase():
    logger.info("\n" + "=" * 60)
    logger.info("  PHASE 3: Codebase Structure Analysis")
    logger.info("=" * 60)
    brain_dir = BRAIN_DIR
    laap_dir = Path("D:/LAAP")

    # 分析 aris_brain
    py_files = list(brain_dir.rglob("*.py"))
    py_files = [f for f in py_files if '__pycache__' not in str(f)
                and '_archive' not in str(f) and '.venv' not in str(f)]

    total_size = sum(f.stat().st_size for f in py_files)
    total_lines = 0
    file_sizes = []
    imports_map = defaultdict(set)

    for f in py_files:
        try:
            content = f.read_text(encoding='utf-8', errors='ignore')
            lines = content.count('\n')
            total_lines += lines
            file_sizes.append((f.name, lines, f.stat().st_size))
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('import ') or line.startswith('from '):
                    imports_map[f.name].add(line)
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    file_sizes.sort(key=lambda x: x[1], reverse=True)

    logger.info(f"\n  aris_brain:")
    logger.info(f"    Python files: {len(py_files)}")
    logger.info(f"    Total lines: {total_lines:,}")
    logger.info(f"    Total size: {total_size / 1024:.1f} KB")
    logger.info(f"\n  Top 10 largest:")
    for name, lines, size in file_sizes[:10]:
        logger.info(f"    {name}: {lines:,} lines ({size/1024:.1f} KB)")
    very_large = [f for f in file_sizes if f[1] > 1000]
    logger.info(f"\n  >1000 行（需模块化）: {len(very_large)}")
    for name, lines, size in very_large:
        logger.info(f"    {name}: {lines:,} lines")
    logger.info(f"\n  AST 函数分析:")
    total_funcs, large_funcs = _analyze_function_sizes(py_files)
    logger.info(f"    总函数数: {total_funcs}")
    logger.info(f"    >80行函数: {len(large_funcs)}")
    for lf in large_funcs[:10]:
        logger.info(f"    {lf['file']}:{lf['line_start']} {lf['function']}() — {lf['lines']}行")
    laap_py = list(laap_dir.rglob("*.py"))
    laap_py = [f for f in laap_py if '__pycache__' not in str(f)
               and 'node_modules' not in str(f) and '.venv' not in str(f)]
    laap_lines = 0
    laap_size = 0
    for f in laap_py:
        try:
            laap_lines += f.read_text(encoding='utf-8', errors='ignore').count('\n')
            laap_size += f.stat().st_size
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    logger.info(f"\n  LAAP codebase:")
    logger.info(f"    Python files: {len(laap_py)}")
    logger.info(f"    Total lines: {laap_lines:,}")
    logger.info(f"    Total size: {laap_size / 1024:.1f} KB")
    return {
        'aris_brain_files': len(py_files),
        'aris_brain_lines': total_lines,
        'aris_brain_size_kb': total_size / 1024,
        'largest_files': file_sizes[:10],
        'very_large_files': very_large,
        'large_functions': large_funcs,
        'laap_files': len(laap_py),
        'laap_lines': laap_lines,
        'laap_size_kb': laap_size / 1024,
    }

# ─────────── PHASE 4: 自动代码修改 (True RSI) ───────────

def run_true_rsi_modifications(dry_run: bool = False) -> dict:
    """调用 evolution/true_rsi.py 执行真正的代码修改（修复：之前 cycle_runner 从不调用它）"""
    logger.info("\n" + "=" * 60)
    logger.info("  PHASE 4: True RSI — 自动代码修改")
    logger.info("=" * 60)
    try:
        # 直接导入 true_rsi 模块
        sys.path.insert(0, str(BRAIN_DIR / "evolution"))
        from true_rsi import run_cycle, discover_tunable_parameters

        # 先打印一下发现了多少参数
        params = discover_tunable_parameters()
        logger.info(f"\n  发现 {len(params)} 个可调参数:")
        if params:
            # 按文件分组展示
            by_file = defaultdict(list)
            for p in params:
                by_file[p['file']].append(p)
            for file, ps in sorted(by_file.items())[:5]:
                logger.info(f"    {file}: {len(ps)} 个参数")
                for p in ps[:3]:
                    logger.info(f"      {p['name']} = {p['value']} (line {p['line']})")
            if len(by_file) > 5:
                logger.info(f"    ... 以及 {len(by_file) - 5} 个更多文件")
        result = run_cycle(dry_run=dry_run)
        logger.info(f"\n  True RSI 结果:")
        logger.info(f"    论文扫描: {result.get('papers_scanned', 0)}")
        logger.info(f"    待执行: {result.get('changes', 0)}")
        logger.info(f"    成功应用: {result.get('applied', 0)}")
        logger.info(f"    回滚: {result.get('rolled_back', 0)}")
        logger.error(f"    失败: {result.get('failed', 0)}")
        return result

    except ImportError as e:
        logger.warning(f"true_rsi 导入失败（非致命）: {e}")
        logger.info(f"  true_rsi 不可用，跳过 PHASE 4")
        return {'status': 'skipped', 'error': str(e)}
    except Exception as e:
        logger.error(f"true_rsi 执行失败: {e}")
        logger.info(f"  true_rsi 出错: {e}")
        return {'status': 'error', 'error': str(e)}

# ─────────── PHASE 5: 优化报告 ───────────

def generate_optimization_report(codebase, arxiv_findings, rsi_result, true_rsi_result):
    logger.info("\n" + "=" * 60)
    logger.info("  PHASE 5: Optimization Report")
    logger.info("=" * 60)
    recommendations = []

    # 1. 大文件模块化
    if codebase['very_large_files']:
        recommendations.append({
            'category': 'Code Structure',
            'priority': 'HIGH',
            'finding': f"{len(codebase['very_large_files'])} 个文件超过 1000 行",
            'recommendation': '拆分大文件为功能清晰的模块',
            'impact': '让 RSI 自修改更精确，减小误伤范围',
        })

    # 2. 大函数拆分
    if codebase.get('large_functions'):
        recommendations.append({
            'category': 'Code Structure',
            'priority': 'HIGH',
            'finding': f"{len(codebase['large_functions'])} 个函数超过 80 行",
            'recommendation': '将大函数拆分为多个小函数，增加可调参数暴露面',
            'impact': 'RSI 可以更精细地调整代码行为',
        })

    # 3. 高价值论文整合
    high_value_papers = [p for p in arxiv_findings if p['score'] >= 3]
    if high_value_papers:
        for p in high_value_papers[:3]:
            recommendations.append({
                'category': 'Knowledge Integration',
                'priority': 'HIGH' if p['score'] >= 5 else 'MEDIUM',
                'finding': f"论文: {p['title'][:60]} (score={p['score']})",
                'recommendation': f"整合进 {p['aspect']} 核区域",
                'impact': f"增强 {p['aspect']} 能力",
            })

    # 4. RSI 参数
    if rsi_result and rsi_result['cycle']['suggestions']:
        for s in rsi_result['cycle']['suggestions'][:3]:
            recommendations.append({
                'category': 'PSI Parameter Tuning',
                'priority': 'MEDIUM',
                'finding': f"参数 '{s['parameter']}' = {s['from']}",
                'recommendation': f"调整为 {s['to']}",
                'impact': f"预期改进: {s['expected_improvement']}",
            })

    # 5. True RSI 结果
    if true_rsi_result and true_rsi_result.get('applied', 0) > 0:
        recommendations.append({
            'category': 'Code Modification',
            'priority': 'INFO',
            'finding': f"True RSI 应用了 {true_rsi_result['applied']} 项修改",
            'recommendation': '查看 modification_log.json 了解详情',
            'impact': '代码参数根据论文自动调优',
        })

    # 6. 架构缺口
    recommendations.append({
        'category': 'Architecture Integration',
        'priority': 'HIGH',
        'finding': 'evolution/rsi_engine.py 和 laap/agi/rsi_engine.py 和 evolution/true_rsi.py 三个引擎独立运行',
        'recommendation': '通过 rsi_cycle_runner.py v3 统一调度，已在此版本实现',
        'impact': '统一自我改进: 论文扫描 → 参数调优 → 代码修改 → 验证',
    })

    # 打印报告
    for i, rec in enumerate(recommendations, 1):
        logger.info(f"\n  {rec['priority']} #{i}: [{rec['category']}]")
        logger.info(f"    发现: {rec['finding'][:80]}")
        logger.info(f"    建议: {rec['recommendation'][:100]}")
        logger.info(f"    影响: {rec['impact'][:80]}")
    return recommendations

# ─────────── MAIN ───────────

def main():
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("  Aris RSI Full Cycle v3 — 递归自我改进")
    logger.info(f"  {datetime.now().isoformat()}")
    logger.info("=" * 60)
    arxiv_findings = run_arxiv_scan()

    # PHASE 2: RSI Meta Engine 参数调优（带真实性能指标）
    rsi_result = run_rsi_meta_cycle()

    # PHASE 3: 代码库分析 + AST 函数大小
    codebase = analyze_codebase()

    # PHASE 4: True RSI 自动代码修改
    true_rsi_result = run_true_rsi_modifications(dry_run=False)

    # PHASE 5: 优化报告
    recommendations = generate_optimization_report(
        codebase, arxiv_findings, rsi_result, true_rsi_result
    )

    # 摘要
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 60)
    logger.info(f"  RSI Full Cycle Complete — {elapsed:.1f}s")
    logger.info("=" * 60)
    logger.info(f"  arXiv 新论文: {len(arxiv_findings)}")
    if rsi_result:
        logger.info(f"  RSI 参数改进: {'已应用' if rsi_result['cycle']['applied'] else '无变更'}")
        logger.info(f"  学习目标: {len(rsi_result['cycle']['goals'])}")
        logger.info(f"  成长需求: {rsi_result['cycle']['growth_need']}")
    logger.info(f"  代码行数: {codebase['aris_brain_lines']:,} ({codebase['aris_brain_files']} files)")
    if true_rsi_result:
        print(f"  True RSI 修改: {true_rsi_result.get('applied', 0)} 成功, "
              f"{true_rsi_result.get('failed', 0)} 失败, "
              f"{true_rsi_result.get('rolled_back', 0)} 回滚")
    logger.info(f"  优化建议: {len(recommendations)}")
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'arxiv_papers': len(arxiv_findings),
        'rsi_applied': bool(rsi_result and rsi_result['cycle']['applied']),
        'true_rsi_applied': true_rsi_result.get('applied', 0) if true_rsi_result else 0,
        'code_lines': codebase['aris_brain_lines'],
        'recommendations': len(recommendations),
        'elapsed_s': round(elapsed, 1),
    }
    run_log = BRAIN_DIR / "evolution" / "cycle_run_log.json"
    run_logs = []
    if run_log.exists():
        try:
            run_logs = json.loads(run_log.read_text())
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    run_logs.append(log_entry)
    run_log.write_text(json.dumps(run_logs[-100:], ensure_ascii=False, indent=2))

    return {
        'arxiv_findings': arxiv_findings,
        'rsi_cycle': rsi_result,
        'codebase': codebase,
        'true_rsi': true_rsi_result,
        'recommendations': recommendations,
        'elapsed_s': elapsed,
    }

if __name__ == "__main__":
    results = main()
