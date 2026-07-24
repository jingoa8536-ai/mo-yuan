"""Use Ollama REST API to analyze the image (model should be cached now)."""

import logging
logger = logging.getLogger(__name__)

import base64, json, urllib.request, sys

img_path = r'C:\Users\user\AppData\Local\hermes\profiles\laap-avatar-v4\image_cache\img_1cdd68034bd5.jpg'
with open(img_path, 'rb') as f:
    img_b64 = base64.b64encode(f.read()).decode()

# Try with a more specific prompt
prompts = [
    "Describe this image in detail. What objects do you see? What colors?",
    "仔细看这张图片，描述你看到的一切。这是什么场景？有什么物体？什么颜色？",
]

for i, prompt in enumerate(prompts):
    logger.info(f"\n--- Attempt {i+1}: {prompt[:30]}... ---")
    try:
        payload = json.dumps({
            "model": "minicpm-v",
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
            "options": {"temperature": 0.1, "max_tokens": 200}
        }).encode()
        
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=300)
        result = json.loads(resp.read())
        text = result.get("response", "")
        logger.info(text)
        with open(f"D:/LAAP/aris_brain/_vision_result_{i}.txt", "w", encoding="utf-8") as f:
            f.write(text)
    except Exception as e:
        logger.error(f"Error: {e}")
logger.info("\nDONE")