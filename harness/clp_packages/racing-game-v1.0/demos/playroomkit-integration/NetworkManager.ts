/**
 * NetworkManager — PlayroomKit 多人网络管理器
 *
 * 反编译证据：原网站三层网络架构
 *   PlayroomKit (房间/匹配) + Supabase (持久化) + PeerJS (P2P 数据流)
 *
 * 装配图谱节点：harness://game/network/module/playroom-manager@1.0.0#three-layer
 *
 * 职责：
 *   1. 创建/加入房间
 *   2. 广播本地车辆状态
 *   3. 接收远程车辆状态
 *   4. 同步赛事阶段（countdown/racing/finished）
 *   5. 发送/接收 Ghost 挑战
 */

"use client";

import { useState, useEffect, useRef, useCallback } from "react";

// PlayroomKit 类型（如未安装则降级为单机模式）
interface PlayroomKitAPI {
  createRoom: (options: { maxPlayers: number }) => Promise<string>;
  joinRoom: (roomCode: string) => Promise<void>;
  leaveRoom: () => void;
  onPlayerJoin: (cb: (player: RemotePlayer) => void) => void;
  onPlayerLeave: (cb: (player: RemotePlayer) => void) => void;
  broadcastState: (state: VehicleNetworkState) => void;
  onRemoteState: (cb: (playerId: string, state: VehicleNetworkState) => void) => void;
  broadcastEvent: (event: NetworkEvent) => void;
  onEvent: (cb: (event: NetworkEvent) => void) => void;
  getPlayers: () => RemotePlayer[];
  isHost: () => boolean;
}

interface RemotePlayer {
  id: string;
  name: string;
  color: string;
  state?: VehicleNetworkState;
}

interface VehicleNetworkState {
  position: { x: number; y: number; z: number };
  quaternion: { x: number; y: number; z: number; w: number };
  speed: number;
  rpm: number;
  gear: number;
  currentLap: number;
  racePhase: "menu" | "countdown" | "racing" | "finished";
  timestamp: number;
}

type NetworkEvent =
  | { type: "racePhaseChange"; phase: string; timestamp: number }
  | { type: "lapComplete"; playerId: string; lapTime: number }
  | { type: "ghostChallenge"; fromPlayerId: string; ghostFrames: any[]; trackId: string }
  | { type: "raceResults"; standings: Array<{ playerId: string; position: number; totalTime: number }> };

interface NetworkManagerState {
  connected: boolean;
  roomCode: string | null;
  isHost: boolean;
  players: RemotePlayer[];
  remoteStates: Map<string, VehicleNetworkState>;
  localPlayerId: string;
  latency: number;
}

/**
 * useNetworkManager Hook
 *
 * 装配到 test-race/page.tsx 中：
 *   const net = useNetworkManager({ enabled: mode === 'multiplayer' });
 *   <Scene3D networkManager={net} ... />
 */
export function useNetworkManager(options: {
  enabled: boolean;
  playerName?: string;
  maxPlayers?: number;
}) {
  const { enabled, playerName = "Player", maxPlayers = 8 } = options;
  const [state, setState] = useState<NetworkManagerState>({
    connected: false,
    roomCode: null,
    isHost: false,
    players: [],
    remoteStates: new Map(),
    localPlayerId: "",
    latency: 0,
  });

  const apiRef = useRef<PlayroomKitAPI | null>(null);
  const lastBroadcastRef = useRef<number>(0);

  // === 创建房间 ===
  const createRoom = useCallback(async () => {
    if (!apiRef.current) return null;
    const roomCode = await apiRef.current.createRoom({ maxPlayers });
    setState((s) => ({ ...s, connected: true, roomCode, isHost: true }));
    return roomCode;
  }, []);

  // === 加入房间 ===
  const joinRoom = useCallback(async (roomCode: string) => {
    if (!apiRef.current) return;
    await apiRef.current.joinRoom(roomCode);
    setState((s) => ({ ...s, connected: true, roomCode, isHost: false }));
  }, []);

  // === 离开房间 ===
  const leaveRoom = useCallback(() => {
    if (!apiRef.current) return;
    apiRef.current.leaveRoom();
    setState({
      connected: false,
      roomCode: null,
      isHost: false,
      players: [],
      remoteStates: new Map(),
      localPlayerId: "",
      latency: 0,
    });
  }, []);

  // === 广播本地车辆状态（每帧调用） ===
  const broadcastLocalState = useCallback((localState: Omit<VehicleNetworkState, "timestamp">) => {
    if (!apiRef.current || !state.connected) return;
    const now = performance.now();
    // 限频：每 50ms 广播一次（20Hz），降低带宽
    if (now - lastBroadcastRef.current < 50) return;
    lastBroadcastRef.current = now;

    apiRef.current.broadcastState({
      ...localState,
      timestamp: now,
    });
  }, [state.connected]);

  // === 广播赛事事件 ===
  const broadcastEvent = useCallback((event: NetworkEvent) => {
    if (!apiRef.current || !state.connected) return;
    apiRef.current.broadcastEvent(event);
  }, [state.connected]);

  // === 发送 Ghost 挑战 ===
  const sendGhostChallenge = useCallback((ghostFrames: any[], trackId: string) => {
    if (!apiRef.current || !state.connected) return;
    apiRef.current.broadcastEvent({
      type: "ghostChallenge",
      fromPlayerId: state.localPlayerId,
      ghostFrames,
      trackId,
    });
  }, [state.connected, state.localPlayerId]);

  // === 监听远程状态 + 事件 ===
  useEffect(() => {
    if (!enabled) return;

    // 动态导入 PlayroomKit（如未安装则降级）
    import("playroomkit")
      .then((module) => {
        apiRef.current = module.default as unknown as PlayroomKitAPI;
        setState((s) => ({ ...s, localPlayerId: `p_${Date.now()}` }));

        // 远程状态监听
        apiRef.current!.onRemoteState((playerId, remoteState) => {
          setState((s) => {
            const newStates = new Map(s.remoteStates);
            newStates.set(playerId, remoteState);
            // 计算延迟
            const latency = performance.now() - remoteState.timestamp;
            return { ...s, remoteStates: newStates, latency };
          });
        });

        // 玩家加入/离开
        apiRef.current!.onPlayerJoin((player) => {
          setState((s) => ({ ...s, players: [...s.players, player] }));
        });
        apiRef.current!.onPlayerLeave((player) => {
          setState((s) => {
            const newStates = new Map(s.remoteStates);
            newStates.delete(player.id);
            return {
              ...s,
              players: s.players.filter((p) => p.id !== player.id),
              remoteStates: newStates,
            };
          });
        });
      })
      .catch((err) => {
        console.warn("[NetworkManager] PlayroomKit 未安装，降级为单机模式", err);
      });

    return () => {
      if (apiRef.current) {
        apiRef.current.leaveRoom();
      }
    };
  }, [enabled]);

  return {
    ...state,
    createRoom,
    joinRoom,
    leaveRoom,
    broadcastLocalState,
    broadcastEvent,
    sendGhostChallenge,
  };
}

export type {
  NetworkManagerState,
  VehicleNetworkState,
  NetworkEvent,
  RemotePlayer,
  PlayroomKitAPI,
};
