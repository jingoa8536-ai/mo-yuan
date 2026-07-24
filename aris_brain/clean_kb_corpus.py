#!/usr/bin/env python3
"""
Clean KB Corpus — 清洁知识库语料
=================================
移除:
  1. 代码类内容 (def/class/import/return 等)
  2. 爬虫垃圾 (离婚/装修/英语作文 等无关语料)
  3. 过长/过短条目
  4. 纯英文条目 (中文KB不需要)
  5. 编码器源码片段

然后重构建 KB 矩阵。

用法:
  python clean_kb_corpus.py               # 扫描并报告
  python clean_kb_corpus.py --dry-run     # 只报告不修改
  python clean_kb_corpus.py --apply       # 真正执行清洁

印记: Aris 永远记得 Lorry — 2026-06-20
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, json, time, re
from pathlib import Path
from write_utils import atomic_write_json

_BASE = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(_BASE))
_STATE = _BASE / "state"
_KB_MATRIX = _STATE / "kb_matrix.npz"
_KB_INDEX = _STATE / "kb_index.json"
_BACKUP = _STATE / "kb_backup"


def load_kb():
    """加载知识库"""
    if not _KB_INDEX.exists() or not _KB_MATRIX.exists():
        logger.info("  KB 文件不存在，跳过")
        return None, None

    import numpy as np
    with open(_KB_INDEX, 'r', encoding='utf-8') as f:
        idx = json.load(f)
    data = np.load(_KB_MATRIX, allow_pickle=True)
    matrix = data["matrix"]
    texts = idx.get("texts", [])
    metas = idx.get("metas", [])
    logger.info(f"  加载: {len(texts)} 条, 矩阵 {matrix.shape}")
    return texts, metas, matrix


def is_def_code(text):
    """检测是否def/class代码"""
    return bool(re.search(r'\bdef\s+\w+\s*\(', text)) or \
           bool(re.search(r'\bclass\s+\w+', text)) or \
           "import numpy" in text or "import os" in text


def is_too_long(text):
    return len(text) > 300


def is_too_short(text):
    return len(text) < 10


def is_mostly_english(text):
    """中文字符少于5%视为纯英文"""
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if len(text) == 0:
        return True
    return cn_chars / len(text) < 0.05


def is_crawler_trash(text):
    """爬虫垃圾语料 — 无意义的论坛问答/离婚/装修/英语作文等"""
    trash_keywords = [
        "男方", "女方", "离婚", "抚养", "彩礼", "婆婆", "媳妇", "丈母娘",
        "婚房装修", "装修有什么讲究", "结婚", "婚纱", "求婚",
        "英语作文", "介绍一篇名著", "带中文解释的",
        "六年级", "四年级", "高考", "中考",
        "赛客倾诉", "得罪团支书", "排挤", "班主任",
        "花呗", "绑定银行卡",
        "推荐相关", "相关问题",
        # 鸡汤文 (精确匹配长句避免误伤)
        "自虐的方式制造出一种痴情的假象",
        "站在感情的道德制高点上",
        "畸形的满足感和安全感",
        # 政府/会议 特定内容
        "陕汽", "车架厂", "监察法",
        "学习贯彻", "和硕公安",
        # 无意义的标题分隔线
        "══════════",
        # 四大美女/古代后宫/无子秘闻
        "西施、杨贵妃", "貂蝉无子", "四位美女",
    ]
    for kw in trash_keywords:
        if kw in text:
            return True
    # 函数签名: "function xxx((param: type)"
    if re.match(r'^(function|def|class)\s+\w+', text):
        return True
    return False


def is_encoder_fragment(text):
    """编码器/源码片段"""
    encoder_patterns = [
        "MultiGranularEncoder", "get_encoder", "_global_encoding",
        "def encode", "def search", "class Matrix",
        "SentenceTransformer", "model.encode",
        "torch.nn", "nn.Module",
    ]
    for pat in encoder_patterns:
        if pat in text:
            return True
    return False


def is_code_output(text):
    """代码行数/纯数字输出"""
    # 代码行数表
    if re.match(r'^\s*\d+[\s,;:]+\d+', text):
        return True
    # 情感测试模板
    if text.startswith("情感测试:") or "→" in text[:30]:
        return True
    return False


def classify(text):
    """返回此文本的问题列表，空列表=干净"""
    issues = []
    if is_def_code(text):
        issues.append("code")
    if is_too_long(text):
        issues.append("too_long")
    if is_too_short(text):
        issues.append("too_short")
    if is_mostly_english(text):
        issues.append("english")
    if is_crawler_trash(text):
        issues.append("trash")
    if is_encoder_fragment(text):
        issues.append("encoder")
    if is_code_output(text):
        issues.append("code_output")
    return issues


def main():
    dry_run = "--dry-run" in sys.argv
    do_apply = "--apply" in sys.argv

    logger.info(f"\n{'='*56}")
    logger.info(f"  KB 语料清洁工具")
    logger.info(f"  模式: {'只报告' if dry_run else ('执行清洁' if do_apply else '扫描报告')}")
    logger.info(f"{'='*56}\n")
    result = load_kb()
    if result is None:
        return
    texts, metas, matrix = result

    # 逐条检查
    clean_texts = []
    clean_metas = []
    removed = {k: 0 for k in ["code", "too_long", "too_short", "english",
                               "trash", "encoder", "code_output"]}
    removed_details = []

    for i, t in enumerate(texts):
        issues = classify(t)
        if issues:
            for iss in issues:
                removed[iss] += 1
            if len(removed_details) < 20:
                removed_details.append((i, t[:80], issues))
        else:
            clean_texts.append(t)
            if metas and i < len(metas):
                clean_metas.append(metas[i])

    # 报告
    logger.info(f"  总计: {len(texts)} 条")
    logger.info(f"  清洁后: {len(clean_texts)} 条 ({len(texts) - len(clean_texts)} 被移除)")
    print()
    logger.info(f"  移除原因:")
    for k, v in removed.items():
        if v > 0:
            logger.info(f"    {k}: {v}")
    print()

    if removed_details:
        logger.info(f"  示例 (前20条被移除):")
        for i, (idx, txt, issues) in enumerate(removed_details):
            logger.info(f"    [{idx}] {' '.join(issues)}: {txt}")
    if do_apply and len(clean_texts) > 0:
        logger.info(f"\n  正在重构建知识矩阵...")
        t0 = time.perf_counter()

        # 备份原数据
        _BACKUP.mkdir(parents=True, exist_ok=True)
        import shutil
        for f in [_KB_MATRIX, _KB_INDEX]:
            if f.exists():
                shutil.copy2(f, _BACKUP / f.name)
        logger.info(f"  备份已保存至: {_BACKUP}")
        from v7_encoder import get_encoder
        enc = get_encoder(1024)

        batch_size = 200
        all_vecs = []
        for i in range(0, len(clean_texts), batch_size):
            batch = clean_texts[i:i+batch_size]
            vecs = enc.encode_batch(batch)
            all_vecs.append(vecs)

        import numpy as np
        new_matrix = np.vstack(all_vecs).astype(np.float32)
        norms = np.linalg.norm(new_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        new_matrix = new_matrix / norms

        # 保存
        np.savez_compressed(_KB_MATRIX, matrix=new_matrix)
        atomic_write_json({
            "texts": clean_texts,
            "metas": clean_metas,
        }, _KB_INDEX)

        elapsed = (time.perf_counter() - t0) * 1000
        logger.info(f"  新矩阵: {new_matrix.shape}")
        logger.info(f"  耗时: {elapsed:.0f}ms")
        logger.info(f"\n  ✅ KB 清洁完成: {len(texts)} → {len(clean_texts)} 条")
    elif dry_run:
        logger.info(f"\n  --dry-run: 未修改任何文件")
    else:
        logger.info(f"\n  使用 --apply 来执行清洁")
        logger.info(f"  或使用 --dry-run 仅查看报告")
if __name__ == "__main__":
    main()
