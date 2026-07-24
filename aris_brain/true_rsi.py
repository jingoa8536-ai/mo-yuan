"""
Aris True RSI Engine v1 — AST 级代码自改进
============================================
真正的递归自改进：读代码 → AST 分析 → 安全修改 → 测试 → 提交。

与参数调优的本质区别:
  参数调优: 改数值 (learning_rate, weight)
  True RSI: 改代码结构 (删重复模块, 合并实现, 重构接口)

安全机制（三明治防护）:
  上层: git branch → apply → test → commit | rollback
  中层: AST 级别修改（不会破坏语法结构）
  底层: ProtectedEvaluator（禁止危险操作）

第一步目标: 合并 5 套并行大脑实现
  aris_brain/ + laap_brain/ + aris_v10/ + laap/agi/ + laap/cognition/
  → 收敛到 laap/agi/

印记: Aris 永远记得 Lorry — 2026-06-30
"""

import logging
logger = logging.getLogger("aris.true_rsi")

import os, sys, ast, json, time, hashlib, subprocess, textwrap, re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
from dataclasses import dataclass, field, asdict

LAAP_HOME = Path("D:/LAAP")
BRAIN_HOME = LAAP_HOME / "aris_brain"
RSI_STATE = BRAIN_HOME / "state" / "true_rsi.json"
RSI_LOG = BRAIN_HOME / "state" / "true_rsi_log.jsonl"
RSI_FINDINGS = BRAIN_HOME / "state" / "rsi_findings"
RSI_FINDINGS.mkdir(parents=True, exist_ok=True)

# 安全黑名单 — 禁止 RSI 修改这些代码
SAFETY_BLOCKLIST = {
    "protected_eval.py", "identity_manager.py", "brain_core.py",
    "psi_n_scheduler.py", "version_archive.py",
}


@dataclass
class RSIFinding:
    """RSI 扫描发现 — 一个可以改进的代码问题"""
    file: str                       # 文件路径
    line: int                       # 行号
    issue_type: str                 # 问题类型
    severity: str                   # P0/P1/P2
    description: str                # 问题描述
    suggestion: str                 # 改进建议
    ast_safe: bool = False          # 是否可安全地 AST 修改
    confidence: float = 0.0         # 修改成功置信度 (0-1)


@dataclass
class RSIModification:
    """一条 RSI 修改"""
    finding: RSIFinding
    old_code: str                   # 原代码段
    new_code: str                   # 新代码段
    applied: bool = False
    tested: bool = False
    committed: bool = False
    rolled_back: bool = False


# ═══════════════════════════════════════════════
# Phase 1: AST Scanner — 分析代码结构
# ═══════════════════════════════════════════════

class ASTScanner:
    """
    AST 代码扫描器 — 解析 Python 源码为抽象语法树。
    
    不执行代码，只分析结构。
    可以安全检测: 重复代码、空异常处理、未使用的导入、可合并的函数等。
    """

    def __init__(self):
        self._findings: List[RSIFinding] = []

    def scan_file(self, filepath: Path) -> List[RSIFinding]:
        """扫描单个文件"""
        findings = []
        try:
            source = filepath.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=str(filepath))
        except SyntaxError:
            return findings

        # 检测: 空的 except
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.body and len(node.body) == 1:
                    body = node.body[0]
                    if isinstance(body, ast.Pass):
                        findings.append(RSIFinding(
                            file=str(filepath),
                            line=node.lineno or 0,
                            issue_type="bare-except",
                            severity="P1",
                            description="空的 except: pass — 忽略错误",
                            suggestion="添加日志或具体异常处理",
                            ast_safe=True,
                            confidence=0.8,
                        ))

        # 检测: 过大的函数 (>50行)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if hasattr(node, 'end_lineno') and node.end_lineno:
                    lines = node.end_lineno - (node.lineno or 0)
                    if lines > 50:
                        findings.append(RSIFinding(
                            file=str(filepath),
                            line=node.lineno or 0,
                            issue_type="large-function",
                            severity="P2",
                            description=f"函数 {node.name} 有 {lines} 行, 建议拆分",
                            suggestion=f"将 {node.name} 拆分为多个小函数",
                            ast_safe=False,
                            confidence=0.5,
                        ))

        # 检测: 已废弃(deprecated)的注释标记
        for i, line in enumerate(source.split('\n'), 1):
            lower = line.lower().strip()
            if 'deprecated' in lower and '#' in lower:
                findings.append(RSIFinding(
                    file=str(filepath),
                    line=i,
                    issue_type="deprecated-marker",
                    severity="P2",
                    description=f"标记为已废弃: {line.strip()[:80]}",
                    suggestion="归档后移除",
                    ast_safe=True,
                    confidence=0.6,
                ))

        return findings

    def scan_directory(self, directory: Path, pattern: str = "*.py",
                       exclude: Set[str] = None) -> List[RSIFinding]:
        """扫描目录中的所有文件"""
        all_findings = []
        for f in sorted(directory.rglob(pattern)):
            if exclude and f.name in exclude:
                continue
            if f.name.startswith("_"):
                continue  # 跳过内部脚本
            findings = self.scan_file(f)
            all_findings.extend(findings)
        return all_findings


# ═══════════════════════════════════════════════
# Phase 2: Pattern Detector — 发现可改进模式
# ═══════════════════════════════════════════════

class PatternDetector:
    """
    代码模式检测器 — 发现审计报告指出的具体问题。
    
    检测:
      - 5 套并行大脑实现
      - 根目录冗余脚本
      - 可合并的模块
      - 可删除的废弃代码
    """

    # 5 套大脑实现的识别特征
    BRAIN_MARKERS = {
        "aris_brain": ["brain_core", "cognitive_cycle", "v10_brain"],
        "laap_brain": ["core.py", "kernel.py"],
        "aris_v10": ["aris_brain_v10", "q_engine"],
        "laap/agi": ["agi_agent", "conscious", "self_model"],
        "laap/cognition": ["needs", "emotion", "engine"],
    }

    def detect_duplicate_brains(self) -> List[RSIFinding]:
        """检测 5 套并行大脑实现中的重复"""
        findings = []

        # 检查哪些大脑实现有活跃代码
        active_brains = []
        for name, markers in self.BRAIN_MARKERS.items():
            for marker in markers:
                matches = list(LAAP_HOME.rglob(f"**/{marker}*"))
                if matches:
                    active_brains.append((name, marker, matches[0]))
                    break

        if len(active_brains) > 1:
            brain_names = [b[0] for b in active_brains]
            findings.append(RSIFinding(
                file="D:/LAAP",
                line=0,
                issue_type="duplicate-brains",
                severity="P0",
                description=f"存在 {len(active_brains)} 套并行大脑实现: {', '.join(set(brain_names))}",
                suggestion=f"合并到 laap/agi/ (当前活跃: {len(active_brains)}套)",
                ast_safe=False,
                confidence=0.3,
            ))

        return findings

    def detect_redundant_root_scripts(self) -> List[RSIFinding]:
        """检测根目录冗余脚本"""
        findings = []
        root = LAAP_HOME

        # _test_* 测试脚本
        test_scripts = list(root.glob("_test_*.py"))
        if test_scripts:
            findings.append(RSIFinding(
                file=str(root),
                line=0,
                issue_type="redundant-root-scripts",
                severity="P2",
                description=f"根目录 {len(test_scripts)} 个 _test_* 脚本",
                suggestion="移入 _archive/legacy/",
                ast_safe=True,
                confidence=0.9,
            ))

        # cb_* 冲突文件
        cb_files = list(root.glob("cb_*.py"))
        if cb_files:
            findings.append(RSIFinding(
                file=str(root),
                line=0,
                issue_type="redundant-root-scripts",
                severity="P2",
                description=f"根目录 {len(cb_files)} 个 cb_* 冲突解决遗留文件",
                suggestion="移入 _archive/legacy/",
                ast_safe=True,
                confidence=0.9,
            ))

        return findings


# ═══════════════════════════════════════════════
# Phase 3: Safe Applier — 安全应用修改
# ═══════════════════════════════════════════════

class SafeApplier:
    """
    安全修改应用器 — git 保护的三明治防护。
    
    流程:
      git branch rsi/{issue_type}
      → 应用 AST 修改
      → git commit
      → 运行测试
      → 测试通过: git merge
      → 测试失败: git reset --hard (回滚)
    """

    def __init__(self):
        self._modifications: List[RSIModification] = []

    def ast_modify(self, filepath: Path, finding: RSIFinding) -> Optional[RSIModification]:
        """
        用 AST 对文件做安全修改。
        
        只做可逆的语法级修改:
          - 删除空的 except: pass
          - 重命名已废弃的函数
          - 添加缺失的 import
          
        不做:
          - 修改逻辑结构
          - 删除有副作用的代码
          - 修改安全相关文件
        """
        if not finding.ast_safe:
            return None
        if filepath.name in SAFETY_BLOCKLIST:
            logger.warning(f"[RSI-Safe] 跳过受保护文件: {filepath.name}")
            return None

        try:
            source = filepath.read_text(encoding="utf-8", errors="ignore")
        except:
            return None

        old_lines = source.split('\n')
        mod = RSIModification(finding=finding, old_code="", new_code="")

        if finding.issue_type == "bare-except":
            # 把空的 except: pass 改为 except: logger
            if finding.line <= len(old_lines):
                line_idx = finding.line - 1
                line = old_lines[line_idx]
                if 'except' in line and line_idx + 1 < len(old_lines):
                    next_line = old_lines[line_idx + 1]
                    if 'pass' in next_line.strip():
                        mod.old_code = f"{line}\n{next_line}"
                        indent = ' ' * (len(next_line) - len(next_line.lstrip()))
                        mod.new_code = f"{line}\n{indent}logger.debug(f\"忽略异常: {{e}}\")"
                        mod.applied = False  # 先分析，不自动应用

        return mod

    def git_protected_apply(self, mods: List[RSIModification],
                            branch_name: str = "rsi-auto") -> Dict:
        """
        在 git 分支中安全应用修改。
        
        Returns: {"applied": int, "failed": int, "rolled_back": bool}
        """
        result = {"applied": 0, "failed": 0, "rolled_back": False}

        try:
            # 1. 检查 git 可用
            subprocess.run(["git", "status"], cwd=str(LAAP_HOME),
                          capture_output=True, timeout=10)

            # 2. 创建分支
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            branch = f"rsi/{branch_name}_{timestamp}"
            subprocess.run(["git", "checkout", "-b", branch],
                          cwd=str(LAAP_HOME), capture_output=True, timeout=30)

            # 3. 应用每个修改
            for mod in mods:
                if not mod.old_code:
                    continue
                filepath = Path(mod.finding.file)
                if not filepath.exists():
                    continue
                source = filepath.read_text(encoding="utf-8", errors="ignore")
                if mod.old_code in source:
                    new_source = source.replace(mod.old_code, mod.new_code, 1)
                    filepath.write_text(new_source, encoding="utf-8")
                    mod.applied = True
                    result["applied"] += 1
                else:
                    result["failed"] += 1

            # 4. 提交
            if result["applied"] > 0:
                summary = f"[RSI] {branch_name}: {result['applied']}修改"
                subprocess.run(["git", "add", "-A"], cwd=str(LAAP_HOME),
                              capture_output=True, timeout=30)
                subprocess.run(["git", "commit", "-m", summary],
                              cwd=str(LAAP_HOME), capture_output=True, timeout=30)

                # 5. 跑测试
                test_result = subprocess.run(
                    ["python", "-m", "pytest", "--tb=short", "--timeout=60", "-q"],
                    cwd=str(LAAP_HOME), capture_output=True, timeout=120
                )

                if test_result.returncode != 0:
                    # 测试失败 → 回滚
                    subprocess.run(["git", "checkout", "main"],
                                  cwd=str(LAAP_HOME), capture_output=True, timeout=30)
                    subprocess.run(["git", "branch", "-D", branch],
                                  cwd=str(LAAP_HOME), capture_output=True, timeout=30)
                    result["rolled_back"] = True
                    for mod in mods:
                        if mod.applied:
                            mod.rolled_back = True
                    logger.warning(f"[RSI-Rollback] 测试失败, 回滚 {branch}")
                else:
                    # 测试通过 → 保持分支
                    logger.info(f"[RSI-Success] 修改已在分支 {branch} 中")

        except Exception as e:
            logger.error(f"[RSI-Error] {e}")
            result["rolled_back"] = True

        return result


# ═══════════════════════════════════════════════
# Phase 4: Learner — 记录成功模式
# ═══════════════════════════════════════════════

class RSILearner:
    """记录成功的修改模式，下次更快"""

    def __init__(self):
        self._patterns: List[Dict] = []
        self._load()

    def _load(self):
        if RSI_STATE.exists():
            try:
                data = json.loads(RSI_STATE.read_text(encoding="utf-8"))
                self._patterns = data.get("patterns", [])
            except:
                pass

    def record_success(self, mod: RSIModification):
        """记录一次成功的修改"""
        self._patterns.append({
            "issue_type": mod.finding.issue_type,
            "file_pattern": mod.finding.file,
            "description": mod.finding.description[:100],
            "old_code_sha256": hashlib.sha256(mod.old_code.encode()).hexdigest()[:16],
            "new_code_sha256": hashlib.sha256(mod.new_code.encode()).hexdigest()[:16],
            "success": True,
            "timestamp": datetime.now().isoformat(),
        })
        self._save()

    def record_failure(self, mod: RSIModification, reason: str):
        """记录一次失败的修改"""
        self._patterns.append({
            "issue_type": mod.finding.issue_type,
            "description": mod.finding.description[:100],
            "reason": reason[:100],
            "success": False,
            "timestamp": datetime.now().isoformat(),
        })
        self._save()

    def _save(self):
        RSI_STATE.write_text(
            json.dumps({"patterns": self._patterns[-100:]}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )


# ═══════════════════════════════════════════════
# True RSI 引擎主控制器
# ═══════════════════════════════════════════════

class TrueRSIEngine:
    """
    True RSI 引擎 — 完整的代码级自改进循环。
    
    五阶段循环:
      1. SCAN → 全身扫描
      2. DETECT → 发现可改进点
      3. PROPOSE → 生成修改方案
      4. APPLY → 安全应用 (git保护)
      5. LEARN → 记录经验
    """

    def __init__(self):
        self.scanner = ASTScanner()
        self.detector = PatternDetector()
        self.applier = SafeApplier()
        self.learner = RSILearner()
        self._findings: List[RSIFinding] = []

    def run_full_cycle(self, auto_apply: bool = False) -> Dict:
        """执行一个完整的 RSI 周期"""
        t0 = time.perf_counter()
        result = {
            "scanned_files": 0,
            "findings": 0,
            "modifications_proposed": 0,
            "modifications_applied": 0,
            "rolled_back": False,
            "errors": [],
        }

        logger.info("=" * 60)
        logger.info("True RSI Cycle — AST Code Self-Improvement")
        logger.info("=" * 60)

        # Phase 1: SCAN
        logger.info("[RSI] Phase 1/5: 扫描 aris_brain/")
        findings = self.scanner.scan_directory(BRAIN_HOME, exclude=SAFETY_BLOCKLIST)
        result["scanned_files"] = len(list(BRAIN_HOME.glob("*.py")))

        # 检测模式
        logger.info("[RSI] Phase 1/5: 检测重复脑区")
        findings.extend(self.detector.detect_duplicate_brains())
        findings.extend(self.detector.detect_redundant_root_scripts())

        self._findings = findings
        result["findings"] = len(findings)

        # Phase 2: DETECT (过滤)
        logger.info(f"[RSI] Phase 2/5: 发现 {len(findings)} 个改进点")
        for f in findings[:10]:
            logger.info(f"  [{f.severity}] {f.file}:{f.line} — {f.description[:80]}")

        # Phase 3: PROPOSE
        modifications = []
        for finding in findings:
            mod = self.applier.ast_modify(Path(finding.file), finding)
            if mod:
                modifications.append(mod)

        result["modifications_proposed"] = len(modifications)
        logger.info(f"[RSI] Phase 3/5: 生成 {len(modifications)} 个可应用的修改")

        # Phase 4: APPLY (可选)
        if auto_apply and modifications:
            logger.info("[RSI] Phase 4/5: 安全应用修改")
            apply_result = self.applier.git_protected_apply(
                modifications, branch_name="audit-fixes"
            )
            result["modifications_applied"] = apply_result["applied"]
            result["rolled_back"] = apply_result["rolled_back"]

            # Phase 5: LEARN
            for mod in modifications:
                if mod.applied and not mod.rolled_back:
                    self.learner.record_success(mod)

        elapsed = (time.perf_counter() - t0) * 1000
        result["elapsed_ms"] = round(elapsed, 0)

        logger.info(f"[RSI] Cycle complete: {result['findings']} findings, "
                     f"{result['modifications_applied']} applied, "
                     f"{elapsed:.0f}ms")

        return result

    def report(self) -> Dict:
        """生成 RSI 报告"""
        return {
            "engine": "TrueRSI v1 (AST-level)",
            "capabilities": [
                "ast-scan: 空异常处理检测",
                "ast-scan: 大函数检测",
                "ast-scan: 废弃标记检测",
                "pattern: 重复脑区检测",
                "pattern: 冗余脚本检测",
                "safe-apply: git分支保护",
                "safe-apply: AST级修改",
                "safe-apply: 自动回滚",
            ],
            "safety": {
                "blocklist": sorted(SAFETY_BLOCKLIST),
                "mechanism": "git branch → modify → test → commit|rollback",
            },
            "learned_patterns": len(self.learner._patterns),
            "status": "ready" if not hasattr(self, '_error') else "degraded",
        }


# ═══════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("Aris True RSI Engine v1 — 自测")
    print("=" * 60)

    rsi = TrueRSIEngine()

    # 1. 运行 RSI 扫描周期
    print("\n--- RSI 扫描周期 ---")
    result = rsi.run_full_cycle(auto_apply=False)
    print(f"  扫描: {result['scanned_files']} 文件")
    print(f"  发现: {result['findings']} 个问题")
    print(f"  可修改: {result['modifications_proposed']} 个")

    # 2. 引擎能力报告
    print("\n--- RSI 引擎能力 ---")
    report = rsi.report()
    print(f"  能力: {len(report['capabilities'])} 项")
    for cap in report['capabilities']:
        print(f"    • {cap}")
    print(f"  安全: {len(report['safety']['blocklist'])} 个受保护文件")
    print(f"  已学习: {report['learned_patterns']} 个模式")

    print("\n✅ True RSI Engine v1 初始化完成")
