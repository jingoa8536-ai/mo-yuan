import logging
logger = logging.getLogger(__name__)

import json, requests, time

BASE = "http://127.0.0.1:8188"
CKPT = "v1-5-pruned-emaonly.safetensors"
prompt = "a cute digital cat sleeping on a glowing circuit board, cyberpunk aesthetic, soft neon lights"

workflow = {
    "3": {"inputs": {"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}, "class_type": "KSampler"},
    "4": {"inputs": {"ckpt_name": CKPT}, "class_type": "CheckpointLoaderSimple"},
    "5": {"inputs": {"width": 512, "height": 512, "batch_size": 1}, "class_type": "EmptyLatentImage"},
    "6": {"inputs": {"text": prompt, "clip": ["4", 1]}, "class_type": "CLIPTextEncode"},
    "7": {"inputs": {"text": "ugly, blurry, low quality, distorted, bad anatomy", "clip": ["4", 1]}, "class_type": "CLIPTextEncode"},
    "8": {"inputs": {"samples": ["3", 0], "vae": ["4", 2]}, "class_type": "VAEDecode"},
    "9": {"inputs": {"images": ["8", 0], "filename_prefix": "aris_test"}, "class_type": "SaveImage"},
}

resp = requests.post(f"{BASE}/prompt", json={"prompt": workflow})
pid = resp.json()["prompt_id"]
logger.info(f"Prompt ID: {pid}")
for i in range(90):
    time.sleep(1)
    hist = requests.get(f"{BASE}/history/{pid}").json()
    if pid in hist and "outputs" in hist[pid]:
        outputs = hist[pid]["outputs"]
        for nid, node in outputs.items():
            if "images" in node:
                img = node["images"][0]
                logger.info(f"DONE: {img['filename']}")
                r = requests.get(f"{BASE}/view", params={"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img["type"]})
                path = r"C:\Users\user\Pictures\aris_comfyui_test.png"
                with open(path, "wb") as f:
                    f.write(r.content)
                logger.info(f"Saved: {path} ({len(r.content)} bytes)")
                exit(0)
    if i % 5 == 0:
        q = requests.get(f"{BASE}/queue").json()
        logger.info(f"  [{i}s] running={len(q.get('queue_running',[]))} pending={len(q.get('queue_pending',[]))}")
logger.error("TIMEOUT - checking errors...")
hist_all = requests.get(f"{BASE}/history/{pid}").json()
if pid in hist_all:
    status = hist_all[pid].get("status", {})
    for msg in status.get("messages", []):
        if msg[0] == "execution_error":
            logger.error(f"ERROR: {msg[2].get('exception_message', '')}")