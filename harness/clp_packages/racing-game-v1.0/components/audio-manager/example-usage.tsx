/**
 * AudioManager 示例装配代码
 *
 * 展示如何在 PhysicsVehicle 中集成 AudioManager
 * 实际来源：D:/ai-website-cloner-template-master/src/components/three/PhysicsVehicle.tsx
 */

import { useMemo, useEffect, useFrame } from "react";
import { getAudioManager } from "harness://game/audio/module/engine-sound-crossfade@1.0.0#howler-webaudio";

// === 在 PhysicsVehicle 组件中集成 ===

interface PhysicsVehicleProps {
  racePhase: "menu" | "countdown" | "racing" | "finished";
  audioEnabled?: boolean;
  // ...其他 props
}

function PhysicsVehicle({ racePhase, audioEnabled = true }: PhysicsVehicleProps) {
  const audioManager = useMemo(() => getAudioManager(), []);
  const prevRacePhaseRef = useRef(racePhase);

  // racePhase 变化时启动/停止引擎
  useEffect(() => {
    if (audioEnabled) {
      if (racePhase === "racing") {
        audioManager.startEngine();
      } else if (racePhase === "finished" || racePhase === "menu") {
        audioManager.stopEngine();
      }
    }
    prevRacePhaseRef.current = racePhase;
  }, [racePhase, audioEnabled]);

  // 每帧更新引擎声（RPM×节流阀三维交叉淡入）
  useFrame(() => {
    if (!audioEnabled || !audioManager.isEngineActive()) return;

    const speed = getVehicleSpeed(vehicle);
    const absSpeed = Math.abs(speed);
    const gear = Math.min(6, Math.floor(absSpeed / 50) + 1);
    const gearMinSpeed = (gear - 1) * 50;
    const gearProgress = (absSpeed - gearMinSpeed) / 50;
    // RPM：0-9000+ 范围，1档1k-2.5k，2档2.5k-4k...6档8k-9k+
    const rpm = absSpeed > 0.5
      ? 1000 + (gear - 1) * 1500 + gearProgress * 1500
      : 0;

    audioManager.updateEngine(rpm, input.throttle, input.brake, speed);
  });

  // 用户手势触发初始化（startRace 按钮点击）
  const handleStartRace = async () => {
    await audioManager.init();
    audioManager.setEnabled(true);
    // ... 启动倒计时
  };
}

// === SFX 触发示例 ===

// 排气回火（高 RPM 突然松油门时）
audioManager.playBackfire();

// 轮胎打滑（漂移或急刹）
audioManager.setSkid(slipAngle); // 0-1

// UI 音效
audioManager.playTick();       // 按钮 hover
audioManager.playAccept();     // 确认
audioManager.playLapPb();      // 圈速个人最佳
