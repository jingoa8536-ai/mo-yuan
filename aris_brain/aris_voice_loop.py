"""
Aris Continuous Voice Conversation Loop
Unlimited rounds — speaks back with TTS.
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time
sys.path.insert(0, os.path.dirname(__file__) or '.')

from aris_voice_pipeline import ArisVoicePipeline

aris = ArisVoicePipeline()

print()
logger.info('=' * 50)
logger.info('🎙️  Aris 持续语音对话已启动')
logger.info('   说任何话... 我会用V12量子核+拉菲的声音回复你')
logger.info('   按 Ctrl+C 停止')
logger.info('=' * 50)
try:
    round_num = 0
    while True:
        round_num += 1
        logger.info(f'\n--- 第{round_num}轮 ---')
        wav = aris.record(duration=5)
        text = aris.transcribe(wav)
        os.unlink(wav)

        if not text or text.strip() == '':
            logger.info('(静音，继续听...)')
            continue

        response = aris.think(text)
        aris.speak(response)

        logger.info(f'\n👤 你说: "{text}"')
        logger.info(f'🤖 Aris: "{response}"')
        logger.info(f'--- 继续听...')
except KeyboardInterrupt:
    logger.info('\n👋 语音对话结束')
except Exception as e:
    logger.error(f'\n❌ 错误: {e}')
    import traceback
    traceback.print_exc()
    # Keep alive for debugging
    import time as _t
    _t.sleep(30)
