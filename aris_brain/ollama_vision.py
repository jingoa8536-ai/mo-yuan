"""
Aris Ollama Vision Module — 用本地 Ollama 视觉模型看图
"""

import logging

import base64, json, logging, os, subprocess, sys, time
from pathlib import Path

logger = logging.getLogger("aris.ollama_vision")

OLLAMA_MODELS_DIR = "D:/ollama/models"
IMAGE_CACHE = Path("C:/Users/user/AppData/Local/hermes/profiles/laap-avatar-v4/image_cache")


def analyze_image(image_path: str, model: str = "minicpm-v") -> str:
    """Analyze an image using Ollama vision model."""
    path = Path(image_path)
    if not path.exists():
        return f"图片不存在: {image_path}"

    # Convert to absolute path for ollama
    abs_path = str(path.resolve())

    env = os.environ.copy()
    env["OLLAMA_MODELS"] = OLLAMA_MODELS_DIR

    prompt = "请详细描述这张图片里有什么，包括内容、颜色、文字（如果有）、氛围等"
    
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            input=abs_path,  # Pass image path
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            return f"模型调用失败: {result.stderr.strip()}"
        return output if output else "模型返回为空"
    except subprocess.TimeoutExpired:
        return "模型响应超时（120秒）"
    except FileNotFoundError:
        return "Ollama 未安装或不在 PATH 中"
    except Exception as e:
        return f"分析出错: {e}"


def analyze_image_with_ollama_api(image_path: str, model: str = "minicpm-v") -> str:
    """Analyze image using Ollama REST API (more reliable for vision models)."""
    path = Path(image_path)
    if not path.exists():
        return f"图片不存在: {image_path}"

    # Read and base64 encode the image
    with open(path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "model": model,
        "prompt": "请详细描述这张图片里有什么，包括内容、颜色、文字（如果有）、氛围等",
        "images": [img_b64],
        "stream": False,
    }

    try:
        import requests
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json=payload,
            timeout=120,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("response", "(无响应)")
        else:
            return f"API 错误: HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return "Ollama 服务未运行 (localhost:11434)"
    except Exception as e:
        return f"API 调用失败: {e}"


def check_ollama_status() -> dict:
    """Check if Ollama is running and list available models."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            env={"OLLAMA_MODELS": OLLAMA_MODELS_DIR},
            capture_output=True, text=True, timeout=10,
        )
        models_raw = result.stdout.strip().split("\n")[1:] if result.stdout.strip() else []
        models = []
        for line in models_raw:
            parts = line.split()
            if parts:
                models.append(parts[0])
        return {"running": True, "models": models}
    except FileNotFoundError:
        return {"running": False, "error": "ollama not installed"}
    except Exception as e:
        return {"running": False, "error": str(e)}


if __name__ == "__main__":
    # CLI usage
    if len(sys.argv) > 1:
        img = sys.argv[1]
        model = sys.argv[2] if len(sys.argv) > 2 else "minicpm-v"
        logger.info(f"Analyzing {img} with {model}...")
        result = analyze_image_with_ollama_api(img, model)
        logger.info(result)
    else:
        status = check_ollama_status()
        logger.info(f"Ollama Status: {json.dumps(status, indent=2, ensure_ascii=False)}")