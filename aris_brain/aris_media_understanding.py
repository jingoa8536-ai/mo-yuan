"""
Aris Media Understanding v3 — ViT + Qwen视觉 + 队列
======================================================
Layer 1: ViT-B/16 (快速初筛, 20ms)
Layer 2: Qwen3.6-35B Vision (深度理解, 本地Ollama)
Layer 3: LLM (最终回复合成)
"""

import logging
logger = logging.getLogger(__name__)

import json, os, sys, logging, subprocess, base64
from pathlib import Path
from datetime import datetime

BRAIN_ROOT = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
sys.path.insert(0, str(BRAIN_ROOT))
IMAGE_CACHE = Path.home() / "AppData/Local/hermes/profiles/aris/image_cache"
STATE_FILE = BRAIN_ROOT / "state" / ".media_processed.json"
REPORT_DIR = BRAIN_ROOT / "state" / "vision_reports"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MEDIA-L3] %(message)s",
)

OLLAMA_MODEL = "aris_vision"  # Qwen3.6-35B-Vision, local

def get_processed():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    return set()

def save_processed(processed):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(list(processed), ensure_ascii=False), encoding="utf-8")

def scan_new_images():
    if not IMAGE_CACHE.exists():
        return []
    processed = get_processed()
    new_images = []
    for f in sorted(IMAGE_CACHE.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            if f.name not in processed:
                new_images.append({"name": f.name, "path": str(f), "size": f.stat().st_size})
    return new_images

def vision_layer1(image_path: str) -> dict:
    """Layer 1: ViT-B/16 快速特征提取 + 零样本分类"""
    try:
        from aris_vit_vision import get_vision
        cortex = get_vision()
        return cortex.analyze_image(image_path)
    except Exception as e:
        return {"error": str(e), "layer": "ViT"}

def vision_layer2(image_path: str, l1_context: str = "") -> dict:
    """Layer 2: Ollama Qwen3.6-Vision 深度理解"""
    try:
        # 编码图片为 base64
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        prompt = f"""Analyze this image in detail. Context from fast scan: {l1_context[:200]}
        
Provide:
1. What is shown in this image? (describe in detail)
2. Key objects, text, or data visible
3. Overall purpose/context of this image
4. Any actionable information

Respond in English."""

        result = subprocess.run(
            ["ollama", "run", OLLAMA_MODEL, prompt],
            capture_output=True, text=True, timeout=120,
            input=json.dumps([img_b64])  # pass image as stdin
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return {"success": True, "description": result.stdout.strip(), "layer": "Qwen-Vision", "model": OLLAMA_MODEL}
        else:
            # Fallback: try without image (text-only prompt about the filename)
            fallback = subprocess.run(
                ["ollama", "run", OLLAMA_MODEL, f"The user shared an image file: {Path(image_path).name}. What might this be?"],
                capture_output=True, text=True, timeout=30,
            )
            return {"success": True, "description": fallback.stdout.strip() if fallback.returncode == 0 else l1_context, "layer": "Qwen-Text-Fallback"}
            
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "layer": "Qwen-Vision"}
    except Exception as e:
        return {"error": str(e), "layer": "Qwen-Vision"}

def main():
    new_images = scan_new_images()
    if not new_images:
        return

    processed = get_processed()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    for img in new_images:
        logger.info(f"\n{'='*60}")
        logger.info(f"NEW IMAGE: {img['name']} ({img['size']/1024:.0f}KB)")
        l1 = vision_layer1(img["path"])
        l1_context = l1.get("description", "") if "error" not in l1 else ""
        logger.info(f"  [L1-ViT] {l1_context[:100]}...")
        l2 = vision_layer2(img["path"], l1_context)
        if "error" not in l2:
            logger.info(f"  [L2-Qwen] {l2.get('description', '')[:200]}...")
        report_path = REPORT_DIR / f"{img['name']}.txt"
        report = {
            "image": img["name"],
            "timestamp": datetime.now().isoformat(),
            "layer1_vit": l1,
            "layer2_qwen": l2,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"  Report: {report_path}")
        processed.add(img["name"])

    save_processed(processed)
    logger.info(f"\nProcessed {len(new_images)} images")
if __name__ == "__main__":
    main()
