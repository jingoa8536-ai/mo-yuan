"use client";

import * as THREE from "three";

/**
 * Ghost 系统（原网站特色）
 *
 * 原网站没有 AI 对手，而是用 Ghost 系统：
 * - 录制玩家最佳圈的车辆轨迹（位置 + 朝向 + 速度）
 * - 在下一圈/下次比赛中以半透明车辆回放
 * - 用于自我挑战和对比驾驶线路
 *
 * 反编译证据：docs/apex-reverse-engineering.md 第 3 章
 */

/**
 * Ghost 帧数据
 */
export interface GhostFrame {
  t: number;          // 相对圈开始的时间戳（秒）
  pos: THREE.Vector3;  // 位置
  quat: THREE.Quaternion; // 朝向
  speed: number;       // 速度（m/s）
}

/**
 * Ghost 录制器
 * 在比赛中每帧记录车辆状态，完圈时保存最佳圈数据
 */
export class GhostRecorder {
  private frames: GhostFrame[] = [];
  private recording: boolean = false;
  private lapStartTime: number = 0;

  /**
   * 开始录制新一圈
   */
  startLap() {
    this.frames = [];
    this.lapStartTime = performance.now();
    this.recording = true;
  }

  /**
   * 每帧记录车辆状态
   */
  record(pos: THREE.Vector3, quat: THREE.Quaternion, speed: number) {
    if (!this.recording) return;
    const t = (performance.now() - this.lapStartTime) / 1000;
    this.frames.push({
      t,
      pos: pos.clone(),
      quat: quat.clone(),
      speed,
    });
  }

  /**
   * 完成一圈，返回录制数据（如果有效）
   */
  finishLap(): GhostFrame[] | null {
    this.recording = false;
    if (this.frames.length < 10) return null;
    return [...this.frames];
  }

  /**
   * 取消录制
   */
  cancel() {
    this.recording = false;
    this.frames = [];
  }
}

/**
 * Ghost 回放器
 * 按时间戳回放最佳圈数据
 */
export class GhostPlayer {
  private frames: GhostFrame[] = [];
  private playStartTime: number = 0;
  private playing: boolean = false;
  private currentIndex: number = 0;

  /**
   * 加载 Ghost 数据
   */
  load(frames: GhostFrame[]) {
    this.frames = frames;
  }

  /**
   * 开始回放
   */
  play() {
    if (this.frames.length === 0) return;
    this.playStartTime = performance.now();
    this.playing = true;
    this.currentIndex = 0;
  }

  /**
   * 停止回放
   */
  stop() {
    this.playing = false;
    this.currentIndex = 0;
  }

  /**
   * 每帧获取当前 Ghost 状态（线性插值）
   */
  update(): { pos: THREE.Vector3; quat: THREE.Quaternion; speed: number } | null {
    if (!this.playing || this.frames.length === 0) return null;

    const elapsed = (performance.now() - this.playStartTime) / 1000;

    // 找到当前时间对应的帧
    while (
      this.currentIndex < this.frames.length - 1 &&
      this.frames[this.currentIndex + 1].t < elapsed
    ) {
      this.currentIndex++;
    }

    // 回放结束
    if (this.currentIndex >= this.frames.length - 1) {
      this.playing = false;
      const last = this.frames[this.frames.length - 1];
      return { pos: last.pos.clone(), quat: last.quat.clone(), speed: last.speed };
    }

    // 线性插值
    const a = this.frames[this.currentIndex];
    const b = this.frames[this.currentIndex + 1];
    const dt = b.t - a.t;
    const alpha = dt > 0 ? (elapsed - a.t) / dt : 0;

    return {
      pos: a.pos.clone().lerp(b.pos, alpha),
      quat: a.quat.clone().slerp(b.quat, alpha),
      speed: a.speed + (b.speed - a.speed) * alpha,
    };
  }

  isPlaying(): boolean {
    return this.playing;
  }

  hasData(): boolean {
    return this.frames.length > 0;
  }

  /**
   * 获取回放进度（0-1）
   */
  getProgress(): number {
    if (this.frames.length === 0) return 0;
    return this.currentIndex / this.frames.length;
  }
}

/**
 * Ghost 数据持久化（localStorage）
 */
const GHOST_STORAGE_KEY = "apex-ghost-lap";

export function saveGhostToLocal(frames: GhostFrame[], trackId: string) {
  try {
    const data = {
      trackId,
      frames: frames.map((f) => ({
        t: f.t,
        pos: [f.pos.x, f.pos.y, f.pos.z],
        quat: [f.quat.x, f.quat.y, f.quat.z, f.quat.w],
        speed: f.speed,
      })),
      savedAt: Date.now(),
    };
    localStorage.setItem(GHOST_STORAGE_KEY, JSON.stringify(data));
  } catch (e) {
    console.warn("[Ghost] 保存失败:", e);
  }
}

export function loadGhostFromLocal(trackId: string): GhostFrame[] | null {
  try {
    const raw = localStorage.getItem(GHOST_STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (data.trackId !== trackId) return null;
    return data.frames.map((f: any) => ({
      t: f.t,
      pos: new THREE.Vector3(f.pos[0], f.pos[1], f.pos[2]),
      quat: new THREE.Quaternion(f.quat[0], f.quat[1], f.quat[2], f.quat[3]),
      speed: f.speed,
    }));
  } catch (e) {
    return null;
  }
}

/**
 * Ghost 车辆 3D 渲染组件数据
 */
export interface GhostVehicleState {
  visible: boolean;
  position: THREE.Vector3;
  quaternion: THREE.Quaternion;
  speed: number;
  opacity: number; // 0-1，半透明
}
