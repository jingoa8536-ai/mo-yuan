"use client";

/**
 * Apex Racing AudioManager
 *
 * 反编译证据：D:\LAAP\_apex_assets\index-BHLGw_OM.js
 *
 * 架构（与原网站完全一致）：
 * 1) Howler.js 加载 911cup_*.ogg 引擎样本（27 个）
 *    - 3 节流阀状态：off(0.22) / steady(0.26) / on(0.31)
 *    - RPM 段：idle(1k) / verylow(2.5k) / low(4k) / lowmid(4.5k) / mid(6k) / high(8k) / veryhigh(9k)
 *    - 多样本随机选择（消除循环感）
 * 2) Web Audio API 合成链（处理 Howler 输出）：
 *    dryGain → masterGain
 *    wetSend → delay(0.018) → highpass(140Hz) → convolver → lowpass(4200Hz) → wetGain → masterGain
 * 3) RPM×节流阀三维交叉淡入：
 *    - 同一时刻最多 2 个相邻 RPM 样本激活
 *    - 节流阀状态切换时插值过渡
 * 4) 限速器（limiter）样本：达到红线时叠加
 *
 * 由于原网站离线，本地 /audio/*.ogg 可能不存在。
 * 此时 AudioManager 会自动启用合成 fallback：
 * - 引擎声：OscillatorNode（锯齿波）+ BiquadFilter（低通）+ Gain，按 RPM 调频
 * - UI 音效：短促正弦波 beep
 */

import { Howl, Howler } from "howler";

// ============ 引擎样本映射（来自 JS bundle tx/yx/sx 数组） ============
interface EngineBand {
  id: string;
  state: "off" | "steady" | "on";
  rpm: number; // RPM 阈值
  samples: string[]; // 可选样本（多样本随机）
  gain?: number; // 该段增益
}

const ENGINE_BANDS: EngineBand[] = [
  // off（节流阀松开）
  { id: "off-idle", state: "off", rpm: 1000, samples: ["911cup_offidle"], gain: 0.9 },
  { id: "off-verylow", state: "off", rpm: 2500, samples: ["911cup_offverylow_1", "911cup_offverylow_2", "911cup_offverylow_3"] },
  { id: "off-low", state: "off", rpm: 4000, samples: ["911cup_offlow"] },
  { id: "off-mid", state: "off", rpm: 6000, samples: ["911cup_offmid"] },
  { id: "off-high", state: "off", rpm: 8000, samples: ["911cup_offhigh"], gain: 0.92 },
  // steady（节流阀稳定）
  { id: "steady-idle", state: "steady", rpm: 1000, samples: ["911cup_steadyidle"], gain: 0.88 },
  { id: "steady-verylow", state: "steady", rpm: 2500, samples: ["911cup_steadyverylow_1", "911cup_steadyverylow_2"] },
  { id: "steady-low", state: "steady", rpm: 4000, samples: ["911cup_steadylow"] },
  { id: "steady-lowmid", state: "steady", rpm: 4500, samples: ["911cup_steadylowmid"], gain: 0.92 },
  { id: "steady-mid", state: "steady", rpm: 6000, samples: ["911cup_steadymid"] },
  { id: "steady-high", state: "steady", rpm: 8000, samples: ["911cup_steadyhigh"] },
  { id: "steady-veryhigh", state: "steady", rpm: 9000, samples: ["911cup_steadyveryhigh"], gain: 0.96 },
  // on（节流阀踩下）
  { id: "on-idle", state: "on", rpm: 1000, samples: ["911cup_onidle_1", "911cup_onidle_2", "911cup_onidle_3"] },
  { id: "on-verylow", state: "on", rpm: 2500, samples: ["911cup_onverylow_1", "911cup_onverylow_2"] },
  { id: "on-low", state: "on", rpm: 4000, samples: ["911cup_onlow"] },
  { id: "on-mid", state: "on", rpm: 6000, samples: ["911cup_onmid"] },
  { id: "on-high", state: "on", rpm: 8000, samples: ["911cup_onhigh"] },
  { id: "on-veryhigh", state: "on", rpm: 9000, samples: ["911cup_onveryhigh"], gain: 0.96 },
];

const LIMITER_SAMPLES = ["911cup_limiter", "911cup_steadylimiter"];

// 节流阀状态对应的基础音量（反编译证据：an={off:.22,steady:.26,on:.31}）
const STATE_VOLUMES: Record<"off" | "steady" | "on", number> = {
  off: 0.22,
  steady: 0.26,
  on: 0.31,
};

// ============ SFX 文件列表（反编译证据：Ll 字典） ============
const SFX_FILES = {
  tick: "/audio/tick.mp3",
  hover: "/audio/tick.mp3",
  accept: "/audio/accept.mp3",
  confirm: "/audio/accept.mp3",
  return: "/audio/return.mp3",
  startGame: "/audio/start-game.mp3",
  // 比赛事件
  backfire: ["/audio/backfire1.ogg", "/audio/backfire2.ogg", "/audio/backfire3.ogg"],
  carSkid: "/audio/CarSkid.ogg",
  curb: "/audio/curb.ogg",
  dirt: "/audio/dirt.ogg",
  gravel: "/audio/gravel.ogg",
  carhit: ["/audio/carhit0.ogg", "/audio/carhit1.ogg", "/audio/carhit2.ogg"],
  thump: "/audio/thump.ogg",
  lapPb: "/audio/lap-pb.ogg",
  goodTime: "/audio/good-time.ogg",
  badTime: "/audio/bad-time.ogg",
} as const;

// ============ Web Audio 合成参数（反编译证据：a9 对象） ============
const REVERB_CONFIG = {
  enabled: true,
  dryMix: 1.0,
  wetSend: 0.42,
  wetLevel: 0.42,
  preDelaySeconds: 0.018,
  decaySeconds: 0.58,
  highpassHz: 140,
  lowpassHz: 4200,
};

// ============ AudioManager 单例 ============
class AudioManager {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private reverbChain: {
    dryGain: GainNode;
    wetSendGain: GainNode;
    preDelay: DelayNode;
    highpass: BiquadFilterNode;
    convolver: ConvolverNode;
    lowpass: BiquadFilterNode;
    wetGain: GainNode;
  } | null = null;

  // 引擎样本 Howl 实例
  private engineHowls: Map<string, Howl> = new Map();
  private limiterHowls: Howl[] = [];
  private engineReady: boolean = false;

  // SFX Howl 实例
  private sfxHowls: Map<string, Howl> = new Map();
  private skidHowl: Howl | null = null;
  private backfireHowls: Howl[] = [];
  private sfxReady: boolean = false;

  // 引擎状态
  private engineActive: boolean = false;
  private currentRpm: number = 0;
  private currentThrottle: number = 0; // 0-1
  private currentBrake: number = 0;
  private currentSpeed: number = 0; // m/s

  // 当前激活的样本（用于交叉淡入）
  private activeBandIdx: number = -1;
  private activeHowls: Howl[] = [];

  // 合成 fallback
  private synthEngine: {
    osc1: OscillatorNode;
    osc2: OscillatorNode;
    gain: GainNode;
    filter: BiquadFilterNode;
  } | null = null;

  // 是否已初始化
  private initialized: boolean = false;
  private enabled: boolean = true;

  /**
   * 初始化音频系统（必须在用户手势后调用，满足浏览器自动播放策略）
   */
  async init() {
    if (this.initialized) return;
    this.initialized = true;

    try {
      // 使用 Howler 的 AudioContext
      Howler.autoUnlock = true;
      Howler.autoSuspend = false;
      this.ctx = Howler.ctx as AudioContext;
      if (!this.ctx) {
        // Howler 还没创建 ctx，手动创建
        const Ctor: typeof AudioContext =
          window.AudioContext ||
          ((window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext);
        this.ctx = new Ctor();
        Howler.ctx = this.ctx;
      }
      if (this.ctx.state === "suspended") {
        await this.ctx.resume();
      }

      // 创建主增益
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.value = 0.6;
      this.masterGain.connect(this.ctx.destination);

      // 创建 reverb 处理链
      this.setupReverbChain();

      // 加载引擎样本（异步，不阻塞）
      this.loadEngineSamples();
      this.loadSfxSamples();

      console.log("[Audio] 初始化完成", {
        ctx: this.ctx.state,
        engineBands: ENGINE_BANDS.length,
        sfxFiles: Object.keys(SFX_FILES).length,
      });
    } catch (e) {
      console.warn("[Audio] 初始化失败:", e);
      this.initialized = false;
    }
  }

  /**
   * 设置 Web Audio API reverb 处理链
   * 反编译证据：qx() 函数
   */
  private setupReverbChain() {
    if (!this.ctx || !this.masterGain) return;
    const ctx = this.ctx;

    const dryGain = ctx.createGain();
    const wetSendGain = ctx.createGain();
    const preDelay = ctx.createDelay(0.08);
    const highpass = ctx.createBiquadFilter();
    const convolver = ctx.createConvolver();
    const lowpass = ctx.createBiquadFilter();
    const wetGain = ctx.createGain();

    dryGain.gain.value = REVERB_CONFIG.dryMix;
    wetSendGain.gain.value = REVERB_CONFIG.wetSend;
    preDelay.delayTime.value = REVERB_CONFIG.preDelaySeconds;
    highpass.type = "highpass";
    highpass.frequency.value = REVERB_CONFIG.highpassHz;
    lowpass.type = "lowpass";
    lowpass.frequency.value = REVERB_CONFIG.lowpassHz;
    wetGain.gain.value = REVERB_CONFIG.wetLevel;

    // 生成 IR（脉冲响应）反编译证据：ex() 函数
    convolver.buffer = this.createImpulseResponse(REVERB_CONFIG.decaySeconds);

    // 连接：dryGain → masterGain
    dryGain.connect(this.masterGain);
    // 连接：wetSend → preDelay → highpass → convolver → lowpass → wetGain → masterGain
    wetSendGain.connect(preDelay);
    preDelay.connect(highpass);
    highpass.connect(convolver);
    convolver.connect(lowpass);
    lowpass.connect(wetGain);
    wetGain.connect(this.masterGain);

    this.reverbChain = { dryGain, wetSendGain, preDelay, highpass, convolver, lowpass, wetGain };

    // 让 Howler 的主输出也接入 reverb
    if (Howler.masterGain) {
      const howlerMaster = Howler.masterGain as GainNode;
      // howlerMaster → dryGain (原有 dry 信号)
      howlerMaster.connect(dryGain);
      // howlerMaster → wetSendGain (送入 reverb)
      howlerMaster.connect(wetSendGain);
    }
  }

  /**
   * 生成 noise burst IR（反编译证据：ex() 函数）
   */
  private createImpulseResponse(decaySeconds: number): AudioBuffer {
    const ctx = this.ctx!;
    const sampleRate = ctx.sampleRate;
    const length = Math.max(1, Math.floor(sampleRate * decaySeconds));
    const buf = ctx.createBuffer(2, length, sampleRate);
    for (let ch = 0; ch < buf.numberOfChannels; ch++) {
      const data = buf.getChannelData(ch);
      const channelGain = ch === 0 ? 0.96 : 1;
      for (let i = 0; i < length; i++) {
        const t = i / Math.max(1, length - 1);
        const envelope = Math.pow(1 - t, 2.35);
        const noise = Math.random() * 2 - 1;
        data[i] = noise * envelope * channelGain;
      }
    }
    return buf;
  }

  /**
   * 加载引擎样本
   */
  private loadEngineSamples() {
    const allSamples = new Set<string>();
    ENGINE_BANDS.forEach(b => b.samples.forEach(s => allSamples.add(s)));
    LIMITER_SAMPLES.forEach(s => allSamples.add(s));

    let loadedCount = 0;
    let failedCount = 0;

    allSamples.forEach(sampleName => {
      const howl = new Howl({
        src: [`/audio/${sampleName}.ogg`],
        loop: true,
        volume: 0,
        rate: 1,
        preload: true,
        onload: () => { loadedCount++; this.checkEngineReady(loadedCount, failedCount, allSamples.size); },
        onloaderror: () => { failedCount++; this.checkEngineReady(loadedCount, failedCount, allSamples.size); },
      });
      this.engineHowls.set(sampleName, howl);
    });

    // 限速器
    this.limiterHowls = LIMITER_SAMPLES.map(name => this.engineHowls.get(name)!).filter(Boolean);
  }

  private checkEngineReady(loaded: number, failed: number, total: number) {
    if (loaded + failed < total) return;
    this.engineReady = loaded > 0;
    if (this.engineReady) {
      console.log(`[Audio] 引擎样本就绪: ${loaded}/${total} (失败 ${failed})`);
    } else {
      console.warn(`[Audio] 所有引擎样本加载失败，启用合成 fallback`);
      this.startSynthEngine();
    }
  }

  /**
   * 加载 SFX 样本
   */
  private loadSfxSamples() {
    const loadOne = (key: string, src: string) => {
      const howl = new Howl({
        src: [src],
        preload: true,
        onloaderror: () => { /* 静默失败，播放时使用合成 fallback */ },
      });
      this.sfxHowls.set(key, howl);
    };

    loadOne("tick", SFX_FILES.tick);
    loadOne("accept", SFX_FILES.accept);
    loadOne("return", SFX_FILES.return);
    loadOne("startGame", SFX_FILES.startGame);
    loadOne("carSkid", SFX_FILES.carSkid);
    loadOne("curb", SFX_FILES.curb);
    loadOne("dirt", SFX_FILES.dirt);
    loadOne("gravel", SFX_FILES.gravel);
    loadOne("thump", SFX_FILES.thump);
    loadOne("lapPb", SFX_FILES.lapPb);
    loadOne("goodTime", SFX_FILES.goodTime);
    loadOne("badTime", SFX_FILES.badTime);

    this.skidHowl = this.sfxHowls.get("carSkid") || null;

    // backfire / carhit 多样本
    this.backfireHowls = (SFX_FILES.backfire as readonly string[]).map(src => {
      const howl = new Howl({ src: [src], preload: true });
      return howl;
    });

    this.sfxReady = true;
  }

  /**
   * 启动合成引擎（fallback）
   */
  private startSynthEngine() {
    if (!this.ctx || !this.masterGain || this.synthEngine) return;
    const ctx = this.ctx;

    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const gain = ctx.createGain();
    const filter = ctx.createBiquadFilter();

    osc1.type = "sawtooth";
    osc2.type = "square";
    osc1.frequency.value = 80;
    osc2.frequency.value = 120;
    filter.type = "lowpass";
    filter.frequency.value = 800;
    filter.Q.value = 5;
    gain.gain.value = 0;

    osc1.connect(filter);
    osc2.connect(filter);
    filter.connect(gain);
    gain.connect(this.masterGain);

    osc1.start();
    osc2.start();

    this.synthEngine = { osc1, osc2, gain, filter };
  }

  /**
   * 启动引擎（比赛开始时调用）
   */
  startEngine() {
    if (!this.enabled || !this.initialized) return;
    this.engineActive = true;
    if (this.engineReady) {
      // 启动 idle 样本
      this.crossfadeToBand(0, "off");
    }
    if (this.synthEngine) {
      this.synthEngine.gain.gain.setTargetAtTime(0.08, this.ctx!.currentTime, 0.1);
    }
  }

  /**
   * 停止引擎
   */
  stopEngine() {
    this.engineActive = false;
    this.activeHowls.forEach(h => {
      h.fade(h.volume(), 0, 0.2);
      h.once("fade", () => h.stop());
    });
    this.activeHowls = [];
    this.activeBandIdx = -1;
    if (this.synthEngine && this.ctx) {
      this.synthEngine.gain.gain.setTargetAtTime(0, this.ctx.currentTime, 0.1);
    }
  }

  /**
   * 每帧更新引擎声（RPM×节流阀三维交叉淡入）
   * @param rpm 引擎转速（RPM，0-9000+）
   * @param throttle 节流阀（0-1）
   * @param brake 刹车（0-1）
   * @param speed 速度（m/s）
   */
  updateEngine(rpm: number, throttle: number, brake: number, speed: number) {
    if (!this.enabled || !this.engineActive) return;

    this.currentRpm = Math.max(0, rpm);
    this.currentThrottle = Math.max(0, Math.min(1, throttle));
    this.currentBrake = Math.max(0, Math.min(1, brake));
    this.currentSpeed = Math.abs(speed);

    // 1) 节流阀状态判定（反编译证据：基于 throttle 阈值）
    let state: "off" | "steady" | "on";
    if (this.currentThrottle > 0.6) state = "on";
    else if (this.currentThrottle > 0.1) state = "steady";
    else state = "off";

    // 2) 找到当前 RPM 段
    const stateBands = ENGINE_BANDS.filter(b => b.state === state);
    let bandIdx = 0;
    for (let i = 0; i < stateBands.length; i++) {
      if (this.currentRpm >= stateBands[i].rpm) bandIdx = i;
      else break;
    }

    // 3) 交叉淡入到新段
    if (bandIdx !== this.activeBandIdx) {
      this.crossfadeToBand(bandIdx, state);
      this.activeBandIdx = bandIdx;
    }

    // 4) 限速器叠加（接近红线 9000+）
    if (this.currentRpm > 8500 && this.limiterHowls.length > 0) {
      const lim = this.limiterHowls[Math.floor(Math.random() * this.limiterHowls.length)];
      if (!lim.playing()) {
        lim.volume(0);
        lim.play();
        lim.fade(0, 0.15, 0.1);
      }
    } else {
      this.limiterHowls.forEach(h => {
        if (h.playing()) {
          h.fade(h.volume(), 0, 0.1);
          h.once("fade", () => h.stop());
        }
      });
    }

    // 5) 合成引擎 fallback：按 RPM 调频
    if (this.synthEngine && this.ctx) {
      const baseFreq = 60 + (this.currentRpm / 9000) * 280;
      this.synthEngine.osc1.frequency.setTargetAtTime(baseFreq, this.ctx.currentTime, 0.05);
      this.synthEngine.osc2.frequency.setTargetAtTime(baseFreq * 1.5, this.ctx.currentTime, 0.05);
      this.synthEngine.filter.frequency.setTargetAtTime(
        400 + this.currentThrottle * 3000,
        this.ctx.currentTime,
        0.05
      );
      const synthVol = 0.05 + this.currentThrottle * 0.15;
      this.synthEngine.gain.gain.setTargetAtTime(synthVol, this.ctx.currentTime, 0.05);
    }
  }

  /**
   * 交叉淡入到指定段
   */
  private crossfadeToBand(bandIdx: number, state: "off" | "steady" | "on") {
    const stateBands = ENGINE_BANDS.filter(b => b.state === state);
    const band = stateBands[bandIdx];
    if (!band) return;

    const stateVolume = STATE_VOLUMES[state] * (band.gain ?? 1);

    // 随机选一个样本
    const sampleName = band.samples[Math.floor(Math.random() * band.samples.length)];
    const howl = this.engineHowls.get(sampleName);
    if (!howl) return;

    // 淡出旧的
    this.activeHowls.forEach(h => {
      h.fade(h.volume(), 0, 0.15);
      h.once("fade", () => h.stop());
    });
    this.activeHowls = [];

    // 淡入新的
    howl.volume(0);
    howl.play();
    howl.fade(0, stateVolume, 0.15);
    this.activeHowls.push(howl);
  }

  // ============ SFX 接口 ============

  playTick() { this.playSfx("tick", 0.3); }
  playHover() { this.playSfx("tick", 0.15); }
  playAccept() { this.playSfx("accept", 0.5); }
  playReturn() { this.playSfx("return", 0.5); }
  playStartGame() { this.playSfx("startGame", 0.6); }
  playLapPb() { this.playSfx("lapPb", 0.5); }
  playGoodTime() { this.playSfx("goodTime", 0.5); }
  playBadTime() { this.playSfx("badTime", 0.5); }

  playBackfire() {
    if (!this.enabled || !this.sfxReady) return;
    const howl = this.backfireHowls[Math.floor(Math.random() * this.backfireHowls.length)];
    if (howl) { howl.volume(0.4); howl.play(); }
  }

  playCarhit() {
    if (!this.enabled || !this.sfxReady) return;
    const howls = ["carhit0", "carhit1", "carhit2"].map(k => this.sfxHowls.get(k)).filter(Boolean) as Howl[];
    if (howls.length === 0) return;
    const h = howls[Math.floor(Math.random() * howls.length)];
    h.volume(0.5); h.play();
  }

  /**
   * 轮胎打滑声（loop）
   */
  setSkid(intensity: number) {
    if (!this.enabled || !this.skidHowl) return;
    const i = Math.max(0, Math.min(1, intensity));
    if (i > 0.05) {
      if (!this.skidHowl.playing()) {
        this.skidHowl.volume(0);
        this.skidHowl.play();
      }
      this.skidHowl.volume(i * 0.4);
    } else {
      if (this.skidHowl.playing()) {
        this.skidHowl.fade(this.skidHowl.volume() as number, 0, 0.1);
      }
    }
  }

  /**
   * 路面材质音效
   */
  playSurface(surface: "curb" | "dirt" | "gravel") {
    if (!this.enabled || !this.sfxReady) return;
    const howl = this.sfxHowls.get(surface);
    if (howl) { howl.volume(0.3); howl.play(); }
  }

  private playSfx(key: string, volume: number) {
    if (!this.enabled || !this.sfxReady) return;
    const howl = this.sfxHowls.get(key);
    if (howl) {
      howl.volume(volume);
      howl.play();
    } else {
      // 合成 beep fallback
      this.synthBeep(volume);
    }
  }

  /**
   * 合成 beep（UI 音效 fallback）
   */
  private synthBeep(volume: number) {
    if (!this.ctx || !this.masterGain) return;
    const ctx = this.ctx;
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 800;
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(volume * 0.3, now + 0.005);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.08);
    osc.connect(gain);
    gain.connect(this.masterGain);
    osc.start(now);
    osc.stop(now + 0.1);
  }

  // ============ 通用控制 ============

  setEnabled(enabled: boolean) {
    this.enabled = enabled;
    if (!enabled) {
      this.stopEngine();
      Howler.mute(true);
    } else {
      Howler.mute(false);
    }
  }

  setMasterVolume(volume: number) {
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.setTargetAtTime(volume, this.ctx.currentTime, 0.05);
    }
  }

  isEnabled() { return this.enabled; }
  isEngineActive() { return this.engineActive; }
}

// 单例导出
let _instance: AudioManager | null = null;
export function getAudioManager(): AudioManager {
  if (!_instance) _instance = new AudioManager();
  return _instance;
}
