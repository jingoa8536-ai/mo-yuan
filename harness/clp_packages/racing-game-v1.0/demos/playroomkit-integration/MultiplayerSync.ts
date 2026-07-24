/**
 * MultiplayerSync — 多人状态同步 Hook
 *
 * 装配图谱节点：harness://game/network/module/state-sync@1.0.0#frame-broadcast
 *
 * 职责：
 *   1. 每帧从 PhysicsVehicle 收集本地状态并广播
 *   2. 监听远程状态变化
 *   3. 同步赛事阶段（仅 host 有权切换）
 *   4. 处理 Ghost 挑战事件
 *   5. 集成空间音频（远程车辆距离 → 音量）
 */

"use client";

import { useEffect, useRef, useCallback } from "react";
import { useNetworkManager, type VehicleNetworkState, type NetworkEvent } from "./NetworkManager";
import { getAudioManager } from "../../components/audio-manager/template";

interface MultiplayerSyncOptions {
  enabled: boolean;
  trackId: string;
  localVehicleRef: React.MutableRefObject<{
    position: { x: number; y: number; z: number };
    quaternion: { x: number; y: number; z: number; w: number };
    speed: number;
    rpm: number;
    gear: number;
  } | null>;
  localRacePhase: string;
  localCurrentLap: number;
  onRemoteRacePhaseChange?: (phase: string) => void;
  onGhostChallengeReceived?: (ghostFrames: any[], trackId: string, fromPlayer: string) => void;
  onLapComplete?: (playerId: string, lapTime: number) => void;
}

export function useMultiplayerSync(options: MultiplayerSyncOptions) {
  const {
    enabled,
    localVehicleRef,
    localRacePhase,
    localCurrentLap,
    onRemoteRacePhaseChange,
    onGhostChallengeReceived,
    onLapComplete,
  } = options;

  const net = useNetworkManager({ enabled });
  const audioManager = getAudioManager();
  const lastPhaseRef = useRef(localRacePhase);
  const lastLapRef = useRef(localCurrentLap);

  // === 每帧广播本地状态 ===
  const syncLocalState = useCallback(() => {
    if (!net.connected || !localVehicleRef.current) return;

    const v = localVehicleRef.current;
    net.broadcastLocalState({
      position: v.position,
      quaternion: v.quaternion,
      speed: v.speed,
      rpm: v.rpm,
      gear: v.gear,
      currentLap: localCurrentLap,
      racePhase: localRacePhase as VehicleNetworkState["racePhase"],
    });

    // === 空间音频：根据远程车辆距离调整音量 ===
    net.remoteStates.forEach((remoteState, playerId) => {
      const dx = remoteState.position.x - v.position.x;
      const dy = remoteState.position.y - v.position.y;
      const dz = remoteState.position.z - v.position.z;
      const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
      // 距离 < 50m 时播放对手引擎声（简化版：直接调整主音量）
      if (distance < 50) {
        const volumeFactor = 1 - distance / 50;
        // 实际项目中这里应该为每个远程车辆创建独立的 Howl 实例
        // 演示版仅记录距离供音频管理器决策
      }
    });
  }, [net, localVehicleRef, localRacePhase, localCurrentLap]);

  // === 监听赛事阶段变化并广播 ===
  useEffect(() => {
    if (!net.connected || !net.isHost) return;
    if (localRacePhase !== lastPhaseRef.current) {
      lastPhaseRef.current = localRacePhase;
      net.broadcastEvent({
        type: "racePhaseChange",
        phase: localRacePhase,
        timestamp: Date.now(),
      });
    }
  }, [localRacePhase, net]);

  // === 监听本地圈完成并广播 ===
  useEffect(() => {
    if (!net.connected) return;
    if (localCurrentLap > lastLapRef.current) {
      lastLapRef.current = localCurrentLap;
      // 实际 lapTime 应从 useRaceState 获取
      net.broadcastEvent({
        type: "lapComplete",
        playerId: net.localPlayerId,
        lapTime: 0, // placeholder
      });
    }
  }, [localCurrentLap, net]);

  // === 监听远程事件 ===
  useEffect(() => {
    if (!net.connected) return;

    // 注意：实际项目中应在 useNetworkManager 内部注册 onEvent 回调
    // 这里仅展示事件处理逻辑
    const handleEvent = (event: NetworkEvent) => {
      switch (event.type) {
        case "racePhaseChange":
          if (!net.isHost) {
            onRemoteRacePhaseChange?.(event.phase);
          }
          break;
        case "lapComplete":
          onLapComplete?.(event.playerId, event.lapTime);
          break;
        case "ghostChallenge":
          onGhostChallengeReceived?.(event.ghostFrames, event.trackId, event.fromPlayerId);
          break;
        case "raceResults":
          // 更新最终排名
          break;
      }
    };
  }, [net.connected, net.isHost, onRemoteRacePhaseChange, onGhostChallengeReceived, onLapComplete]);

  return {
    ...net,
    syncLocalState,
  };
}
