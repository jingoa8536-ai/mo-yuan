"""
Aris TTS Server — edge-tts HTTP API on :18880
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, tempfile, asyncio, time

# Ensure proper event loop on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from aiohttp import web
import edge_tts

VOICE = 'zh-CN-XiaoxiaoNeural'
PORT = 18880

async def tts_handler(request):
    text = request.query.get('text', '')
    voice = request.query.get('voice', VOICE)
    if not text:
        return web.json_response({'error': 'text required'}, status=400)
    
    # Truncate if too long
    if len(text) > 500:
        text = text[:500]
    
    t0 = time.time()
    tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
    out_path = tmp.name
    tmp.close()
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(out_path)
        
        with open(out_path, 'rb') as f:
            audio_data = f.read()
        os.unlink(out_path)
        
        elapsed = (time.time() - t0) * 1000
        logger.info(f'[TTS] {elapsed:.0f}ms — "{text[:50]}"')
        return web.Response(body=audio_data, content_type='audio/mpeg')
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def health_handler(request):
    return web.json_response({'status': 'ok', 'voice': VOICE})

async def main():
    app = web.Application()
    app.router.add_get('/tts', tts_handler)
    app.router.add_get('/health', health_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', PORT)
    await site.start()
    logger.info(f'[TTS] Server on :{PORT} (voice={VOICE})')
    await asyncio.Event().wait()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('[TTS] Shutdown')