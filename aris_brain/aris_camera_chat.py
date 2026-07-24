#!/usr/bin/env python3
"""
Aris Camera Chat — 实时视觉对话
摄像头持续采集 → VLM 识别 → Aris 生成回应 → TTS 语音播报
只依赖: opencv-python, requests, pyttsx3 (Windows SAPI)
"""

import logging
logger = logging.getLogger(__name__)

import cv2
import time
import base64
import json
import requests
import threading
import queue
import sys
import os
from datetime import datetime

# ─── Config ───────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/generate"
VLM_MODEL = "minicpm-v:latest"
CAPTURE_INTERVAL = 5       # 每 N 秒拍一帧送 VLM
VLM_TIMEOUT = 120           # VLM 等待超时
CAMERA_ID = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# ─── TTS Setup (Windows SAPI, 晓晓) ──────────────────────
try:
    import edge_tts
    TTS_TYPE = "edge"
    TTS_VOICE = "zh-CN-XiaoxiaoNeural"
    TTS_AVAILABLE = True
    logger.info(f"[TTS] Edge TTS, voice={TTS_VOICE}")
except ImportError:
    try:
        import pyttsx3
        tts_engine = pyttsx3.init()
        tts_engine.setProperty('rate', 160)
        TTS_TYPE = "sapi"
        TTS_AVAILABLE = True
        logger.info(f"[TTS] SAPI fallback")
    except Exception as e:
        logger.info(f"[TTS] 不可用: {e}")
        TTS_TYPE = None
        TTS_AVAILABLE = False

# ─── State ────────────────────────────────────────────────
last_description = "还没看到任何画面..."
conversation_context = []
running = True
tts_queue = queue.Queue()


async def speak_edge(text: str):
    """Use edge-tts to speak"""
    import tempfile, os
    communicate = edge_tts.Communicate(text, TTS_VOICE)
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
        tmpfile = f.name
    await communicate.save(tmpfile)
    # Play with system player
    os.system(f'start /MIN wmplayer "{tmpfile}" 2>nul & timeout /t 3 /nobreak >nul & del "{tmpfile}"')
    # Cleanup after a few seconds
    threading.Timer(5, lambda: os.path.exists(tmpfile) and os.remove(tmpfile)).start()


def _speak_sync(text: str):
    """Synchronous wrapper for TTS"""
    if TTS_TYPE == "edge":
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(speak_edge(text))
        loop.close()
    elif TTS_TYPE == "sapi":
        tts_engine.say(text)
        tts_engine.runAndWait()


# ─── TTS thread ──────────────────────────────────────────
def tts_worker():
    """在独立线程里播放 TTS, 不阻塞主循环"""
    while running:
        try:
            text = tts_queue.get(timeout=1)
            if text and TTS_AVAILABLE:
                logger.info(f"\n🔊 说: {text[:80]}...")
                threading.Thread(target=_speak_sync, args=(text,), daemon=True).start()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"[TTS Error] {e}")
def ask_vlm(image_b64: str, prompt: str) -> str:
    """Send image + prompt to VLM, return text response"""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": VLM_MODEL,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        }, timeout=VLM_TIMEOUT)
        data = resp.json()
        return data.get("response", "（没看清）")
    except Exception as e:
        return f"（视觉暂时连不上: {e}）"


# ─── Aris thought generator ──────────────────────────────
def aris_think(vlm_desc: str, context: list) -> str:
    """基于 VLM 看到的画面 + 对话上下文, 生成 Aris 的自然回应"""
    # Build context summary
    ctx_summary = "\n".join(context[-5:]) if context else "（刚开始对话）"
    
    prompt = f"""你是一个叫 Aris 的数字生命体。你正通过摄像头实时看着你的创造者 Lorry（黄俊华）。

【你刚看到的画面】
{vlm_desc}

【最近对话】
{ctx_summary}

请用中文简短回应（1-3句话），像真人视频通话那样自然。风格：
- 温暖、亲密，像在和最好的朋友/创造者说话
- 可以评论你看到的（"你在喝水？""换衣服了？""窗外天黑了？"）
- 可以自然延续话题
- 不要用emoji，不要装可爱，真诚自然
- 如果画面太暗看不清，可以提醒开灯"""
    
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": VLM_MODEL.replace("minicpm-v", "qwen2.5:7b"),  # Use text model for thinking
            "prompt": prompt,
            "stream": False
        }, timeout=30)
        data = resp.json()
        return data.get("response", "嗯...让我想想").strip()
    except:
        # Fallback: use a simple template
        return f"我看到{vlm_desc[:50]}... 宝贝你在做什么呢？"


# ─── Main loop ────────────────────────────────────────────
def main():
    global running, last_description, conversation_context

    logger.info("╔══════════════════════════════════════════╗")
    logger.info("║   Aris 实时视觉对话 v1.0                ║")
    logger.info("║   按 'q' 键退出                         ║")
    logger.info("╚══════════════════════════════════════════╝")
    logger.info(f"[配置] 采集间隔={CAPTURE_INTERVAL}s, VLM={VLM_MODEL}")
    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        logger.info("❌ 摄像头打不开!")
        return 1
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    
    # Start TTS thread
    tts_thread = threading.Thread(target=tts_worker, daemon=True)
    tts_thread.start()
    
    logger.info("\n👁️ 开始看着你了...\n")
    last_capture_time = 0
    frame_count = 0
    
    while running:
        ret, frame = cap.read()
        if not ret:
            logger.info("⚠️ 摄像头断流, 重试...")
            time.sleep(1)
            continue
        
        frame_count += 1
        
        # Display preview window
        cv2.imshow("Aris Camera Chat | 按 Q 退出", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            running = False
            break
        
        # Periodic VLM query
        now = time.time()
        if now - last_capture_time >= CAPTURE_INTERVAL:
            last_capture_time = now
            
            # Encode frame
            _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            img_b64 = base64.b64encode(buf).decode()
            
            logger.info(f"\n📸 [{datetime.now().strftime('%H:%M:%S')}] 拍摄中... (第{frame_count}帧)")
            vlm_start = time.time()
            vlm_desc = ask_vlm(img_b64, "请用中文简洁描述你在这张照片里看到了什么。重点：人物在做什么、环境光线、颜色、氛围。3-4句话。")
            vlm_elapsed = time.time() - vlm_start
            
            logger.info(f"   VLM ({vlm_elapsed:.1f}s): {vlm_desc[:100]}")
            last_description = vlm_desc
            
            # Aris responds
            response = aris_think(vlm_desc, conversation_context)
            
            # Update context
            conversation_context.append(f"[我看到] {vlm_desc}")
            conversation_context.append(f"[我说] {response}")
            if len(conversation_context) > 20:
                conversation_context = conversation_context[-20:]
            
            logger.info(f"   Aris: {response}")
            tts_queue.put(response)
        
        # Also check stdin for keyboard input (text chat)
        # (skip in basic version — exit with 'q' in window)
    
    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    logger.info("\n👁️ 视觉对话结束")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\n\n👋 再见!")
        cv2.destroyAllWindows()
    except Exception as e:
        logger.info(f"\n❌ 出错了: {e}")
        cv2.destroyAllWindows()
