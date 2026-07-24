/**
 * PlayroomKit 集成演示页面
 *
 * 完整装配：3 个 CLP 组件 + 3 个网络组件
 *
 * 装配序列（参见 assembly-graph.json + demos/README.md）：
 *   1. Mount keyframes-pack (CSS import)
 *   2. Mount PhysicsVehicle + AudioManager + GhostRecorder (CLP v1.0)
 *   3. Mount NetworkManager + MultiplayerSync + RemoteVehicle (本次新增)
 *   4. 用户选择 MULTIPLAYER 模式
 *   5. NetworkManager.createRoom() → 分享 URL
 *   6. 对手加入 → onPlayerJoin 触发 RemoteVehicle 创建
 *   7. 倒计时同步 → 比赛开始
 *   8. 每帧：本地状态广播 + 远程状态插值渲染
 *   9. 圈完成：Ghost 数据可通过 sendGhostChallenge() 发送给对手
 */

"use client";

import { useState, useMemo, useRef, useEffect } from "react";
import dynamic from "next/dynamic";
import { useMultiplayerSync } from "./MultiplayerSync";
import { RemoteVehiclesGroup } from "./RemoteVehicle";
import { GhostRecorder, GhostPlayer, saveGhostToLocal, loadGhostFromLocal } from "../../components/ghost-system/template";
import { getAudioManager } from "../../components/audio-manager/template";

const Scene3D = dynamic(() => import("@/components/three/Scene3D"), { ssr: false });

type GameMode = "single" | "multiplayer";
type RacePhase = "menu" | "lobby" | "countdown" | "racing" | "finished";

const PLAYER_COLORS = ["#3683ff", "#ff6b6b", "#22c55e", "#ffd76a", "#a855f7", "#06b6d4", "#f97316", "#ec4899"];

export default function PlayroomKitDemoPage() {
  const [mode, setMode] = useState<GameMode>("single");
  const [racePhase, setRacePhase] = useState<RacePhase>("menu");
  const [currentLap, setCurrentLap] = useState(0);
  const [roomCode, setRoomCode] = useState<string | null>(null);
  const [joinCode, setJoinCode] = useState("");
  const [players, setPlayers] = useState<Array<{ id: string; name: string; color: string }>>([]);
  const [ghostFrames, setGhostFrames] = useState<any[] | null>(null);
  const [remoteGhost, setRemoteGhost] = useState<any[] | null>(null);

  const localVehicleRef = useRef(null);
  const ghostRecorder = useMemo(() => new GhostRecorder(), []);
  const ghostPlayer = useMemo(() => new GhostPlayer(), []);
  const audioManager = useMemo(() => getAudioManager(), []);

  // === 多人同步 ===
  const net = useMultiplayerSync({
    enabled: mode === "multiplayer",
    trackId: "lagunaSeca",
    localVehicleRef,
    localRacePhase: racePhase,
    localCurrentLap: currentLap,
    onRemoteRacePhaseChange: (phase) => setRacePhase(phase as RacePhase),
    onGhostChallengeReceived: (frames, trackId, fromPlayer) => {
      console.log(`[Ghost Challenge] 收到来自 ${fromPlayer} 的 Ghost 挑战`, { trackId, frames: frames.length });
      setRemoteGhost(frames);
      ghostPlayer.load(frames);
    },
    onLapComplete: (playerId, lapTime) => {
      console.log(`[Lap Complete] ${playerId} 完成一圈: ${lapTime}s`);
    },
  });

  // === 创建房间 ===
  const handleCreateRoom = async () => {
    const code = await net.createRoom();
    if (code) {
      setRoomCode(code);
      setRacePhase("lobby");
      setPlayers([{ id: net.localPlayerId, name: "Host", color: PLAYER_COLORS[0] }]);
    }
  };

  // === 加入房间 ===
  const handleJoinRoom = async () => {
    if (!joinCode.trim()) return;
    await net.joinRoom(joinCode.trim().toUpperCase());
    setRoomCode(joinCode.trim().toUpperCase());
    setRacePhase("lobby");
    setPlayers([{ id: net.localPlayerId, name: "Guest", color: PLAYER_COLORS[1] }]);
  };

  // === 开始比赛（仅 host） ===
  const handleStartRace = async () => {
    await audioManager.init();
    audioManager.startEngine();
    setRacePhase("countdown");
    // host 广播阶段变化
    if (net.isHost) {
      net.broadcastEvent({ type: "racePhaseChange", phase: "countdown", timestamp: Date.now() });
    }
    setTimeout(() => {
      setRacePhase("racing");
      ghostRecorder.startLap();
      if (remoteGhost) ghostPlayer.play();
    }, 3000);
  };

  // === 发送 Ghost 挑战 ===
  const handleSendGhostChallenge = () => {
    if (!ghostFrames) return;
    net.sendGhostChallenge(ghostFrames, "lagunaSeca");
    console.log("[Ghost Challenge] 已发送 Ghost 挑战给房间内所有玩家");
  };

  // === 退出 ===
  const handleExit = () => {
    audioManager.stopEngine();
    ghostPlayer.stop();
    if (mode === "multiplayer") {
      net.leaveRoom();
    }
    setRacePhase("menu");
    setRoomCode(null);
    setMode("single");
  };

  return (
    <div className="relative w-full h-screen bg-[#0c1219] overflow-hidden">
      {/* === 3D 场景（装配所有 CLP 组件） === */}
      <div className="absolute inset-0">
        <Scene3D
          physicsEnabled={racePhase === "racing" || racePhase === "countdown"}
          racePhase={racePhase}
          audioEnabled={true}
          ghostRecorder={ghostRecorder}
          ghostPlayer={ghostPlayer}
          showGhost={!!(remoteGhost || ghostFrames)}
          // 多人网络层
          // 注：实际集成时需在 Scene3D 内部接入 RemoteVehiclesGroup
        />
      </div>

      {/* === 菜单：选择模式 === */}
      {racePhase === "menu" && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#0c1219]/95 backdrop-blur-md">
          <div className="text-center animate-settings-panel-rise">
            <h1 className="font-display text-6xl text-[#3683ff] mb-2 text-glow">APEX RACE</h1>
            <p className="font-ui text-sm text-gray-400 mb-12 tracking-widest">CLP v1.0 + PLAYROOMKIT DEMO</p>

            <div className="grid grid-cols-2 gap-6 max-w-2xl">
              {/* 单机模式 */}
              <button
                onClick={() => { setMode("single"); setRacePhase("countdown"); audioManager.init(); }}
                className="group relative p-6 rounded-xl border border-gray-700/30 bg-[#111a24] hover:border-[#3683ff]/60 transition-all hover:scale-105"
              >
                <div className="font-racing text-2xl text-white mb-2">SINGLE PLAYER</div>
                <div className="font-ui text-xs text-gray-500">单机计时赛 + Ghost 挑战</div>
              </button>

              {/* 多人模式 */}
              <button
                onClick={() => setMode("multiplayer")}
                className="group relative p-6 rounded-xl border border-gray-700/30 bg-[#111a24] hover:border-[#3683ff]/60 transition-all hover:scale-105"
              >
                <div className="font-racing text-2xl text-white mb-2">MULTIPLAYER</div>
                <div className="font-ui text-xs text-gray-500">PlayroomKit 多人对战</div>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* === 多人大厅 === */}
      {mode === "multiplayer" && racePhase === "lobby" && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#0c1219]/95 backdrop-blur-md">
          <div className="text-center animate-lobby-window-in">
            <h2 className="font-racing text-3xl text-[#3683ff] mb-6">LOBBY</h2>

            {!roomCode ? (
              <div className="space-y-4">
                <button onClick={handleCreateRoom} className="px-8 py-3 bg-[#3683ff] text-white rounded-lg font-racing text-lg hover:scale-105 transition-all">
                  创建房间
                </button>
                <div className="flex gap-2">
                  <input
                    value={joinCode}
                    onChange={(e) => setJoinCode(e.target.value)}
                    placeholder="输入房间号"
                    className="px-4 py-2 bg-[#111a24] border border-gray-700/30 rounded-lg text-white font-time uppercase"
                    maxLength={6}
                  />
                  <button onClick={handleJoinRoom} className="px-6 py-2 border border-[#3683ff] text-[#3683ff] rounded-lg font-racing hover:bg-[#3683ff]/10">
                    加入
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                <div>
                  <div className="font-ui text-xs text-gray-500 mb-1">房间号（分享给好友）</div>
                  <div className="font-time text-4xl text-[#ffd76a] tracking-[0.3em]">{roomCode}</div>
                </div>

                <div>
                  <div className="font-ui text-xs text-gray-500 mb-2">玩家列表（{players.length}/{8}）</div>
                  <div className="space-y-2">
                    {players.map((p, i) => (
                      <div key={p.id} className="flex items-center gap-3 px-4 py-2 bg-[#111a24] rounded-lg animate-home-lb-row-in" style={{ animationDelay: `${i * 50}ms` }}>
                        <span className="w-3 h-3 rounded-full" style={{ background: p.color }} />
                        <span className="font-racing text-sm text-white">{p.name}</span>
                        {i === 0 && <span className="font-ui text-xs text-[#ffd76a] ml-auto">HOST</span>}
                      </div>
                    ))}
                  </div>
                </div>

                {net.isHost && (
                  <button
                    onClick={handleStartRace}
                    disabled={players.length < 1}
                    className="px-12 py-4 bg-[#3683ff] text-white rounded-xl font-racing text-xl hover:scale-105 transition-all animate-home-live-pulse"
                  >
                    START RACE
                  </button>
                )}
                {!net.isHost && (
                  <div className="font-ui text-sm text-gray-400">等待 host 开始比赛...</div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* === 倒计时 === */}
      {racePhase === "countdown" && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="font-display text-9xl text-[#3683ff] text-glow animate-notif-pop">3</div>
        </div>
      )}

      {/* === 比赛中的多人 HUD === */}
      {racePhase === "racing" && (
        <>
          {/* 左上：房间信息 */}
          <div className="absolute top-20 left-6 z-10 animate-racing-hud-rise">
            <div className="bg-[#0a1018]/90 backdrop-blur-xl rounded-lg border border-gray-700/30 p-4 shadow-xl">
              <div className="font-ui text-xs text-gray-400">ROOM</div>
              <div className="font-time text-xl text-[#ffd76a]">{roomCode || "SINGLE"}</div>
              <div className="font-ui text-xs text-gray-500 mt-2">LATENCY: {net.latency.toFixed(0)}ms</div>
              <div className="font-ui text-xs text-gray-500">PLAYERS: {players.length}</div>
            </div>
          </div>

          {/* 右上：在线玩家列表 */}
          {mode === "multiplayer" && (
            <div className="absolute top-20 right-6 z-10 animate-racing-hud-rise">
              <div className="bg-[#0a1018]/90 backdrop-blur-xl rounded-lg border border-gray-700/30 p-3 shadow-xl min-w-[200px]">
                <div className="font-ui text-xs text-gray-400 mb-2">ONLINE</div>
                {players.map((p, i) => (
                  <div key={p.id} className="flex items-center gap-2 py-1">
                    <span className="w-2 h-2 rounded-full animate-home-live-pulse" style={{ background: p.color }} />
                    <span className="font-racing text-xs text-white">{p.name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 底部：Ghost 挑战按钮 */}
          {ghostFrames && mode === "multiplayer" && (
            <button
              onClick={handleSendGhostChallenge}
              className="absolute bottom-32 right-6 z-10 px-4 py-2 bg-[#7dd3fc]/20 border border-[#7dd3fc]/40 text-[#7dd3fc] rounded-lg font-racing text-sm hover:scale-105 transition-all animate-thumb-frame-breathe"
            >
              发送 GHOST 挑战
            </button>
          )}

          {/* 退出按钮 */}
          <button
            onClick={handleExit}
            className="absolute top-6 right-6 z-10 px-3 py-1 text-xs text-red-400 border border-red-500/30 rounded hover:bg-red-500/10"
          >
            ESC 退出
          </button>
        </>
      )}
    </div>
  );
}
