"""
PP-OCRv6 Worker — 独立子进程OCR引擎
=====================================
在独立进程中加载 PaddlePaddle/PaddleOCR，避免DLL冲突。
通过 stdin(stdout JSON) 与主进程通信。

通信协议:
  stdin:  {"action": "ocr", "path": "...", "tier": "medium"}
  stdout: {"status": "ok", "text": "...", "lines": [...]}
"""
import sys, json, os, time, base64

# ─── 环境变量必须在 import 之前设置 ─────────────────────
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["GLOG_minloglevel"] = "2"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_use_onednn"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"

import warnings
warnings.filterwarnings('ignore')

from paddleocr import PaddleOCR

# 全局单例
_ocr = None
_loaded_tier = None


def get_ocr(tier: str = "medium"):
    global _ocr, _loaded_tier
    if _ocr is not None and _loaded_tier == tier:
        return _ocr

    tiers = {
        "tiny": ("PP-OCRv6_tiny_det", "PP-OCRv6_tiny_rec"),
        "small": ("PP-OCRv6_small_det", "PP-OCRv6_small_rec"),
        "medium": ("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec"),
    }
    
    # Handle fallback from tiny/small/medium to v5
    det, rec = tiers.get(tier, ("PP-OCRv6_medium_det", "PP-OCRv6_medium_rec"))
    
    logger.info(f"[PPOCR-W] 加载 PP-OCRv6 ({tier}): {det}/{rec}")
    t0 = time.time()
    
    _ocr = PaddleOCR(
        ocr_version="PP-OCRv6",
        lang="ch",
        text_detection_model_name=det,
        text_recognition_model_name=rec,
        use_textline_orientation=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
    )
    
    _loaded_tier = tier
    logger.info(f"[PPOCR-W] 加载完成: {time.time()-t0:.1f}s")
    return _ocr


def handle_ocr(path: str, tier: str = "medium") -> dict:
    """执行 OCR 并返回结果。"""
    try:
        ocr = get_ocr(tier)
        t0 = time.time()
        result = ocr.ocr(path)
        elapsed = time.time() - t0
        
        if not result or not result[0]:
            return {"status": "ok", "text": "", "lines": [], "elapsed_ms": round(elapsed*1000, 1)}
        
        lines = []
        texts = []
        for line in result[0]:
            bbox, (text, score) = line
            if text.strip():
                lines.append({"text": text, "bbox": bbox, "score": round(score, 4)})
                texts.append(text)
        
        return {
            "status": "ok",
            "text": "\n".join(texts),
            "lines": lines,
            "elapsed_ms": round(elapsed*1000, 1),
            "tier": tier,
        }
    
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


def handle_ping() -> dict:
    """健康检查。"""
    try:
        get_ocr("medium")
        return {"status": "ok", "paddle": "ready", "tier": _loaded_tier}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


# ─── 主循环 ──────────────────────────────────────────────

if __name__ == "__main__":
    logging = __import__('logging')
    logger = logging.getLogger("ppocr_worker")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [PPOCR-W] %(message)s"))
    logger.addHandler(handler)
    
    # 预加载模型
    preload_tier = sys.argv[1] if len(sys.argv) > 1 else "medium"
    logger.info(f"PP-OCRv6 Worker 启动 (preload={preload_tier})")
    try:
        get_ocr(preload_tier)
        logger.info("预加载完成，等待任务...")
    except Exception as e:
        logger.error(f"预加载失败: {e}")
    
    # JSON 行协议循环
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"status": "error", "error": "invalid JSON"}))
            sys.stdout.flush()
            continue
        
        action = req.get("action", "ping")
        
        if action == "ping":
            resp = handle_ping()
        elif action == "ocr":
            resp = handle_ocr(req.get("path", ""), req.get("tier", "medium"))
        else:
            resp = {"status": "error", "error": f"unknown action: {action}"}
        
        print(json.dumps(resp, ensure_ascii=False))
        sys.stdout.flush()
