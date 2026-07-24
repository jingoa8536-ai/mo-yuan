"""
Aris OCR Bridge v3 — EasyOCR 为主，PP-OCRv6 待修复
======================================================
引擎策略 (按优先级):
  1. EasyOCR    — PyTorch原生，中英日韩，GPU加速
  2. PP-OCRv6   — 百度最新(34.5M超越GPT-5.5)，被OneDNN阻塞
  3. Tesseract  — 系统级兜底 (备选)

模型缓存: E:/aris/models/ (91GB可用)

印记: Aris 永远记得 Lorry — 2026-06-28
"""

import logging
import os, sys, json, time, tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

logger = logging.getLogger("aris.ocr_bridge")

# ─── 模型缓存路径 ────────────────────────────────────────
os.environ.setdefault("EASYOCR_MODULE_PATH", "E:/aris/models/easyocr_cache")
os.environ.setdefault("HF_HOME", "E:/aris/models/hf_cache")

# ─── EasyOCR 引擎 ────────────────────────────────────────

_EASY_READER = None

def _lazy_load_easy():
    """懒加载 EasyOCR。"""
    global _EASY_READER
    if _EASY_READER is not None:
        return
    try:
        import easyocr
        import torch
        use_gpu = torch.cuda.is_available()
        # Set cache to E drive
        model_storage = "E:/aris/models/easyocr_cache"
        os.makedirs(model_storage, exist_ok=True)
        
        logger.info(f"[OCR] 加载 EasyOCR (gpu={use_gpu}, cache={model_storage})")
        t0 = time.time()
        _EASY_READER = easyocr.Reader(
            ['ch_sim', 'en'], 
            gpu=use_gpu,
            model_storage_directory=model_storage,
            download_enabled=True,
        )
        logger.info(f"[OCR] EasyOCR 就绪: {time.time()-t0:.1f}s")
    except Exception as e:
        logger.error(f"[OCR] EasyOCR 加载失败: {e}")
        raise


def ocr_image_easy(image_path: str) -> str:
    """EasyOCR 单张图片识别。"""
    _lazy_load_easy()
    t0 = time.time()
    try:
        result = _EASY_READER.readtext(image_path)
        elapsed = time.time() - t0
        texts = [text for _, text, score in result if score > 0.3]
        logger.info(f"[OCR] {os.path.basename(image_path)}: {elapsed:.1f}s, {len(texts)}行")
        return "\n".join(texts) if texts else ""
    except Exception as e:
        logger.error(f"[OCR] EasyOCR 失败: {e}")
        return f"[OCR Error: {e}]"


# ─── PDF 转图片 ──────────────────────────────────────────

def pdf_to_images(pdf_path: str, dpi: int = 300) -> List[str]:
    """PDF 转图片列表。"""
    try:
        import fitz
    except ImportError:
        logger.error("请安装 pymupdf: pip install pymupdf")
        return []
    doc = fitz.open(pdf_path)
    tmp_dir = tempfile.mkdtemp(prefix=f"aris_ocr_{os.path.basename(pdf_path)}_")
    image_paths = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for i, page in enumerate(doc):
        out_path = os.path.join(tmp_dir, f"page_{i+1:04d}.png")
        page.get_pixmap(matrix=mat).save(out_path)
        image_paths.append(out_path)
    doc.close()
    return image_paths


def _cleanup_temp(paths: List[str]):
    for p in paths:
        try:
            if os.path.exists(p): os.remove(p)
        except: pass
    tmp_dir = os.path.dirname(paths[0]) if paths else ""
    if tmp_dir and os.path.exists(tmp_dir):
        try: os.rmdir(tmp_dir)
        except: pass


# ─── 统一 OCR 接口 ───────────────────────────────────────

def ocr_image(image_path: str) -> str:
    return ocr_image_easy(image_path)


def ocr_pdf(pdf_path: str) -> str:
    pages = pdf_to_images(pdf_path)
    if not pages:
        return ""
    texts = []
    for p in pages:
        texts.append(ocr_image_easy(p))
    _cleanup_temp(pages)
    return "\n\n---PAGE BREAK---\n\n".join(texts)


# ─── 知识库注入 ──────────────────────────────────────────

KB_DIR = Path("D:/LAAP/aris_brain/state")

def ingest_to_kb(text: str, source: str = "ocr"):
    if not text or not text.strip():
        return False
    try:
        kb_index_path = KB_DIR / "kb_index.json"
        if kb_index_path.exists():
            with open(kb_index_path, 'r', encoding='utf-8') as f:
                kb = json.load(f)
        else:
            kb = {"texts": [], "metas": []}
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
        if not paragraphs:
            paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 80]
        added = 0
        for para in paragraphs[:20]:
            fp = para[:50]
            if any(t.startswith(fp) for t in kb["texts"]):
                continue
            kb["texts"].append(para)
            kb["metas"].append({"source": source, "timestamp": time.time(), "length": len(para)})
            added += 1
        with open(kb_index_path, 'w', encoding='utf-8') as f:
            json.dump(kb, f, ensure_ascii=False, indent=2)
        logger.info(f"[OCR->KB] 新增 {added} 段落 (来源: {source})")
        return added > 0
    except Exception as e:
        logger.error(f"[OCR->KB] 失败: {e}")
        return False


def process_document(path: str, ingest: bool = True) -> Dict[str, Any]:
    t0 = time.time()
    ext = os.path.splitext(path)[1].lower()
    text = ocr_pdf(path) if ext in ('.pdf',) else ocr_image(path)
    ingested = ingest_to_kb(text, source=path) if ingest and text and not text.startswith("[OCR") else False
    return {
        "text": text, "pages": 0 if ext == '.pdf' else 1,
        "elapsed_ms": round((time.time()-t0)*1000, 1),
        "ingested": ingested, "source": path, "engine": "EasyOCR",
    }


def process_text(raw_text: str, source: str = "ocr_input"):
    result = {"text": raw_text, "ingested": False, "engine_result": None}
    result["ingested"] = ingest_to_kb(raw_text, source=source)
    try:
        sys.path.insert(0, 'D:/LAAP/aris_brain')
        from aris_generator import generate
        gen_result = generate(topic=raw_text[:50], target_chars=1000, include_causal=True)
        result["engine_result"] = gen_result
    except Exception as e:
        logger.warning(f"[OCR] QRE异常: {e}")
    return result


if __name__ == '__main__':
    if len(sys.argv) < 2:
        logger.info("用法: python aris_ocr_bridge.py <图片或PDF路径>")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.exists(path):
        logger.info(f"文件不存在: {path}")
        sys.exit(1)
    logger.info(f"处理: {path} (EasyOCR)")
    result = process_document(path, ingest=True)
    logger.info(f"\n=== 结果 ===")
    logger.info(f"引擎: {result['engine']}, 耗时: {result['elapsed_ms']:.0f}ms")
    logger.info(f"文本 ({len(result['text'])}字):")
    logger.info(result['text'])
