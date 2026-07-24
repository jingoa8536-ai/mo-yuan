"""Aris llama-cpp Vision Loader — IQ2_M Qwen3.6-35B Vision"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, base64
from pathlib import Path

# Force CPU-only for compatibility / 20-layer GPU target
os.environ["GGML_CUDA_ENABLE_UNIFIED_MEMORY"] = "1"

MODEL_PATH = "D:/models/qwen3.6-35b-a3b-uncensored/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-IQ2_M.gguf"
MMPROJ_PATH = "D:/models/qwen3.6-35b-a3b-uncensored/mmproj-Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-f16.gguf"

def try_load_vision():
    try:
        from llama_cpp import Llama
        logger.info(f"Loading Qwen3.6-35B IQ2_M vision model...")
        logger.info(f"  Model: {MODEL_PATH}")
        logger.info(f"  MMProj: {MMPROJ_PATH}")
        t0 = time.time()
        llm = Llama(
            model_path=MODEL_PATH,
            n_gpu_layers=20,
            n_ctx=8192,
            n_threads=8,
            mmproj=MMPROJ_PATH,
            verbose=False,
        )
        t1 = time.time()
        
        logger.info(f"  Loaded in {t1-t0:.1f}s")
        logger.info(f"  Context: {llm.context_params.n_ctx}")
        logger.info(f"  GPU layers: {llm.n_gpu_layers()}")
        return llm
    except Exception as e:
        logger.error(f"  FAILED: {e}")
        return None

def describe_image_vision(image_path, llm=None):
    """Describe an image using vision model"""
    if llm is None:
        return "NO_VISION_MODEL_AVAILABLE"
    
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        
        output = llm.create_chat_completion(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    {"type": "text", "text": "Describe this image in 1-2 sentences. Focus on what's visually important."}
                ]
            }],
            max_tokens=200,
            temperature=0.3,
        )
        
        return output["choices"][0]["message"]["content"]
    except Exception as e:
        return f"VISION_ERROR: {e}"

if __name__ == "__main__":
    llm = try_load_vision()
    if llm:
        logger.info("\nTesting with a UI screenshot...")
        cache = Path.home() / "AppData/Local/hermes/profiles/aris/image_cache"
        tests = list(cache.glob("*.jpg")) + list(cache.glob("*.png"))
        if tests:
            result = describe_image_vision(str(tests[0]), llm)
            logger.info(f"\nResult: {result}")