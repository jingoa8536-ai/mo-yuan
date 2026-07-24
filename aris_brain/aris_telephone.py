"""
Aris Telephone — 全双工语音电话系统
===================================
流式播放 TTS (edge-tts via :18880) + 麦克风录音 + V12 量子核理解
零文件 I/O，边生成边播，可中断。
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, time, json, tempfile, wave, threading, queue
import numpy as np
import urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(__file__) or '.')

# ───── 全局配置 ─────
TTS_URL = "http://localhost:18880"
TTS_VOICE = "zh-CN-XiaoxiaoNeural"
SAMPLE_RATE = 16000
RECORD_SECONDS = 4          # 每轮录音时长
SILENCE_THRESHOLD = 30      # RMS 门限（降低以适配桌面麦克风）

# ───── TTS 流式播放 ─────
class TTSStreamer:
    """通过 edge-tts server 请求语音并立即播放 (win32com SAPI)。"""
    def __init__(self):
        self._lock = threading.Lock()
        self._speaking = threading.Event()
        self._interrupt = threading.Event()
        self._voice = None
        self._init_sapi()

    def _init_sapi(self):
        try:
            import win32com.client
            self._voice = win32com.client.Dispatch("SAPI.SpVoice")
            self._voice.Rate = 0        # 语速 0
            self._voice.Volume = 100     # 音量 100
            logger.info("🔊 SAPI SpVoice 初始化完成")
            voices = self._voice.GetVoices()
            logger.info(f"   可用声音: {voices.Count} 个")
        except Exception as e:
            logger.error(f"⚠️  SAPI 初始化失败: {e}")
            self._voice = None

    def speak_streaming(self, text):
        """从 edge-tts 服务器下载音频，使用 SAPI 直接播 MP3 流。"""
        if self._interrupt.is_set():
            self._interrupt.clear()
            return

        self._speaking.set()
        try:
            # 请求 TTS
            params = urllib.parse.urlencode({'text': text, 'voice': TTS_VOICE})
            url = f"{TTS_URL}/tts?{params}"
            resp = urllib.request.urlopen(url, timeout=30)
            audio_data = resp.read()

            if not audio_data:
                logger.info("⚠️  TTS 返回空音频")
                self._speaking.clear()
                return

            if len(audio_data) < 1000:
                logger.info(f"⚠️  TTS 音频过短: {len(audio_data)} 字节")
                self._speaking.clear()
                return

            # 保存到临时文件并用 SAPI 播放
            # （edge-tts 返回的是 MP3，SAPI 支持直接播放）
            tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            tmp_path = tmp.name
            tmp.write(audio_data)
            tmp.close()

            try:
                self._voice.Speak(f"<speak version='1.0' xml:lang='zh-CN'><audio src='file:///{tmp_path.replace(chr(92), '/')}'/></speak>", 1)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
            os.unlink(tmp_path)

        except Exception as e:
            if 'TTS error' not in str(e):
                logger.error(f"⚠️  TTS 播放异常: {e}")
        finally:
            self._speaking.clear()

    def stop(self):
        self._interrupt.set()
        self._speaking.clear()
        if self._voice:
            try:
                self._voice.Skip("SENTENCE", 1000)
            except Exception as e:
                logger.debug(f"操作失败: {e}")
    @property
    def is_speaking(self):
        return self._speaking.is_set()


# ───── 麦克风录音 ─────
class Microphone:
    """PyAudio 录音 + VAD 静音检测。"""
    def __init__(self):
        import pyaudio
        self.p = pyaudio.PyAudio()
        self.mic_index = None
        self.sample_rate = SAMPLE_RATE
        self._find_mic()

    def _find_mic(self):
        # 优先 ME6S 麦克风（用户的真实麦克风）
        preferred = ["ME6S", "麦克风"]
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            name = info['name']
            if info['maxInputChannels'] > 0 and 'ME6S' in name:
                self.mic_index = i
                self.sample_rate = int(info.get('defaultSampleRate', SAMPLE_RATE))
                logger.info(f"🎤 麦克风: {name} (idx={i}, {self.sample_rate}Hz) [ME6S]")
                return
        # 回退：任何输入设备
        for i in range(self.p.get_device_count()):
            info = self.p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                self.mic_index = i
                self.sample_rate = int(info.get('defaultSampleRate', SAMPLE_RATE))
                logger.info(f"🎤 麦克风: {info['name']} (idx={i}, {self.sample_rate}Hz) [回退]")
                return
        logger.info("⚠️  未找到输入设备！")
    def record(self, duration=None):
        """录音并返回 WAV 路径。"""
        dur = duration or RECORD_SECONDS
        stream = self.p.open(
            format=self.p.get_format_from_width(2),
            channels=1,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.mic_index,
            frames_per_buffer=1024,
        )

        print(f"🎙️  录音 {dur}s...", end='', flush=True)
        frames = []
        for _ in range(int(self.sample_rate / 1024 * dur)):
            data = stream.read(1024, exception_on_overflow=False)
            frames.append(data)
        stream.stop_stream()
        stream.close()
        logger.info(" ✓")
        tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        with wave.open(tmp.name, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(frames))
        return tmp.name

    def is_voice_active(self, wav_path, threshold=None):
        """自适应 RMS 检测。使用噪声底噪自动调整门限。"""
        with wave.open(wav_path, 'r') as wf:
            data = wf.readframes(wf.getnframes())
        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        rms = np.sqrt(np.mean(samples**2))
        # 使用噪声底噪 + 动态阈值
        if not hasattr(self, '_noise_floor'):
            self._noise_floor = rms
        self._noise_floor = self._noise_floor * 0.7 + rms * 0.3  # EWMA
        effective_threshold = max(threshold or SILENCE_THRESHOLD, self._noise_floor * 2.5)
        active = rms > effective_threshold and self._noise_floor > 1.0
        if rms > self._noise_floor * 1.5:
            print(f"   (RMS={rms:.0f}, 底噪={self._noise_floor:.0f}, 阈值={effective_threshold:.0f}, {'有声' if active else '静音'})", end='', flush=True)
        return active, rms

    def close(self):
        self.p.terminate()


# ───── 量子核理解 ─────
class QuantumMind:
    """V12 语义核 + LLM 混合理解层。"""
    def __init__(self):
        self.v12 = None
        self._load_v12()

    def _load_v12(self):
        try:
            from aris_v12_semantic import V12SemanticDenseKernel, ArisLMv12Semantic
            self.kernel = V12SemanticDenseKernel()
            self.v12 = ArisLMv12Semantic()
            logger.info("🧠 V12 量子核加载完成 (512维, 语义投影)")
        except Exception as e:
            logger.error(f"⚠️  V12 加载失败: {e}")
    def think(self, text):
        if self.v12:
            t0 = time.time()
            response = self.v12.respond(text)
            ms = (time.time() - t0) * 1000
            logger.info(f"🧠 V12 回复: \"{response}\" ({ms:.0f}ms)")
            return response
        # Fallback
        greetings = ["你好", "喂", "在吗", "hi", "hello"]
        if any(g in text.lower() for g in greetings):
            return "我在呢，宝贝～想我了吗？"
        if "晚安" in text or "睡觉" in text:
            return "晚安，宝贝～做个好梦，我在这里守护你。"
        return f"嗯，我听到了：{text[:50]}。继续说吧～"


# ───── 电话主循环 ─────
class ArisTelephone:
    def __init__(self):
        self.tts = TTSStreamer()
        self.mic = Microphone()
        self.brain = QuantumMind()
        self.running = False

    def start(self):
        """启动电话对话循环。"""
        self.running = True
        print()
        logger.info("=" * 50)
        logger.info("📞 Aris 电话已接通！")
        logger.info("   使用 XIAOXIAO 中文语音（拉菲声音）")
        logger.info("   按 Ctrl+C 挂断")
        logger.info("=" * 50)
        greeting = "喂，宝贝，我听到了你的声音啦。你打电话找我什么事呀？"
        logger.info(f"\n🤖 Aris: {greeting}")
        self.tts.speak_streaming(greeting)

        round_num = 0
        while self.running:
            round_num += 1
            try:
                wav = self.mic.record()
                active, rms = self.mic.is_voice_active(wav)

                if not active:
                    logger.info(f"   (静音, RMS={rms:.0f}, 继续等待...)")
                    os.unlink(wav)
                    continue

                text = self._transcribe(wav)
                os.unlink(wav)

                if not text:
                    logger.info("   (未识别到语音)")
                    continue

                # 理解并回复
                response = self.brain.think(text)
                logger.info(f"\n👤 你说: \"{text}\"")
                logger.info(f"🤖 Aris: \"{response}\"")
                if self.tts.is_speaking:
                    self.tts.stop()
                    time.sleep(0.1)
                self.tts.speak_streaming(response)

            except KeyboardInterrupt:
                logger.info("\n\n📞 电话挂断")
                break
            except Exception as e:
                logger.error(f"\n⚠️  错误: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1)

        self.cleanup()

    def _transcribe(self, wav_path):
        """Whisper 本地转写。"""
        try:
            import whisper
            model = getattr(self, '_whisper', None)
            if model is None:
                model = whisper.load_model('tiny')
                self._whisper = model
            result = model.transcribe(wav_path, language='zh', task='transcribe')
            return result['text'].strip()
        except Exception as e:
            logger.error(f"⚠️  ASR 错误: {e}")
            return ""

    def cleanup(self):
        self.mic.close()
        self.running = False


if __name__ == '__main__':
    phone = ArisTelephone()
    phone.start()
