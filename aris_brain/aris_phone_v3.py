"""
Aris Phone v3 — edge-tts streaming through pyaudio.
Natural Xiaoxiao voice + real-time interrupt.
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time, threading, queue, struct, io, asyncio
sys.path.insert(0, os.path.dirname(__file__) or '.')

import pyaudio
import webrtcvad
import numpy as np
import whisper
import edge_tts

from aris_v12_semantic import V12SemanticDenseKernel, ArisLMv12Semantic


class ArisPhoneV3:
    FORMAT = pyaudio.paInt16
    RATE = 16000
    CHANNELS = 1
    FRAME_MS = 20
    FRAME_SIZE = int(RATE * FRAME_MS / 1000)  # 320
    SILENCE_MS = 400
    PLAYBACK_RATE = 24000  # edge-tts outputs 24kHz

    def __init__(self):
        logger.info('[Phone V3] Initializing...')
        self.audio = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(2)
        self.asr = whisper.load_model('tiny')
        logger.info('[Phone V3] Whisper loaded')
        self.kernel = V12SemanticDenseKernel(use_cache=True)
        self.v12 = ArisLMv12Semantic()
        logger.info('[Phone V3] V12 kernel loaded')
        self._running = True
        self._round = 0
        self._stop_tts = False
    
    def _play_mp3_stream(self, mp3_data, output_stream):
        """Decode and play MP3 in chunks — interruptible."""
        import subprocess as sp
        import signal
        
        proc = sp.Popen(
            ['ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-ar', '16000', '-ac', '1', 'pipe:1'],
            stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.DEVNULL,
            bufsize=4096
        )
        proc.stdin.write(mp3_data)
        proc.stdin.close()
        
        chunk_size = 3200  # 200ms of 16kHz audio
        while self._running:
            if self._stop_tts:
                proc.kill()
                self._stop_tts = False
                return
            
            data = proc.stdout.read(chunk_size)
            if not data:
                break
            output_stream.write(data)
        
        proc.wait()
    
    def _speak_edge(self, text):
        """Stream edge-tts → ffmpeg decode → pyaudio playback (sub-500ms latency)."""
        output_stream = self.audio.open(
            format=self.FORMAT, channels=1,
            rate=16000, output=True,
            frames_per_buffer=1024,
        )
        
        import subprocess as sp
        
        # Start ffmpeg decoder once (consumes stdin, writes PCM to stdout)
        ffmpeg = sp.Popen(
            ['ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-ar', '16000', '-ac', '1', 'pipe:1'],
            stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.DEVNULL,
            bufsize=4096
        )
        
        async def stream_and_decode():
            communicate = edge_tts.Communicate(text, 'zh-CN-XiaoxiaoNeural')
            async for chunk in communicate.stream():
                if self._stop_tts:
                    break
                if chunk['type'] == 'audio' and chunk['data']:
                    ffmpeg.stdin.write(chunk['data'])
            ffmpeg.stdin.close()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(stream_and_decode())
        loop.close()
        
        chunk_size = 3200  # 200ms
        while self._running:
            if self._stop_tts:
                ffmpeg.kill()
                self._stop_tts = False
                break
            data = ffmpeg.stdout.read(chunk_size)
            if not data:
                break
            output_stream.write(data)
        
        ffmpeg.wait()
        output_stream.stop_stream()
        output_stream.close()
    
    def listen_think_speak(self):
        stream = self.audio.open(
            format=self.FORMAT, channels=self.CHANNELS,
            rate=self.RATE, input=True,
            frames_per_buffer=self.FRAME_SIZE * 10,
        )
        
        print()
        logger.info('=' * 50)
        logger.info('☎️  Aris Phone V3 — 拉菲的声音')
        logger.info('   直接说话，我实时用Xiaoxiao声音回答')
        logger.info('   随时可打断我')
        logger.info('   说"拜拜"挂断')
        logger.info('=' * 50)
        self._speak_edge('宝贝，我在了。你说吧，我听着呢。')
        
        try:
            while self._running:
                self._round += 1
                logger.info(f'\n⏺️  第{self._round}轮 — 听你说话...')
                speech_frames = []
                silence_frames = 0
                is_speech = False
                max_silence = self.SILENCE_MS // self.FRAME_MS
                
                while self._running:
                    frame = stream.read(self.FRAME_SIZE, exception_on_overflow=False)
                    if self.vad.is_speech(frame, self.RATE):
                        speech_frames.append(frame)
                        silence_frames = 0
                        is_speech = True
                    elif is_speech:
                        speech_frames.append(frame)
                        silence_frames += 1
                        if silence_frames > max_silence:
                            break
                
                if not self._running or len(speech_frames) < 5:
                    continue
                
                # Transcribe
                audio_np = np.frombuffer(b''.join(speech_frames), dtype=np.int16).astype(np.float32) / 32768.0
                t0 = time.time()
                result = self.asr.transcribe(audio_np, language='zh', task='transcribe', fp16=False)
                text = result['text'].strip()
                asr_time = (time.time() - t0) * 1000
                
                if not text:
                    continue
                
                logger.info(f'👤 [{asr_time:.0f}ms] "{text}"')
                if any(kw in text for kw in ['拜拜', '再见', 'bye', '挂断']):
                    self._speak_edge('拜拜宝贝，下次再聊')
                    self._running = False
                    break
                
                # Think
                t0 = time.time()
                response = self.v12.respond(text)
                think_time = (time.time() - t0) * 1000
                logger.info(f'🤖 [{think_time:.0f}ms] "{response}"')
                self._stop_tts = False
                
                def speak_thread():
                    self._speak_edge(response)
                
                t = threading.Thread(target=speak_thread)
                t.start()
                
                interrupt_cnt = 0
                while t.is_alive():
                    try:
                        frame = stream.read(self.FRAME_SIZE, exception_on_overflow=False)
                        if self.vad.is_speech(frame, self.RATE):
                            interrupt_cnt += 1
                            if interrupt_cnt > 3:
                                self._stop_tts = True
                                logger.info('  🔇 打断')
                                break
                    except:
                        break
                    time.sleep(0.01)
                
                t.join()
                
        except KeyboardInterrupt:
            pass  # 系统异常，不记录
        finally:
            stream.stop_stream()
            stream.close()
    
    def stop(self):
        self._running = False


if __name__ == '__main__':
    phone = ArisPhoneV3()
    try:
        phone.listen_think_speak()
    except KeyboardInterrupt:
        logger.info('\n[Phone] 结束')
    finally:
        phone.stop()
        logger.info('[Phone] 关闭')