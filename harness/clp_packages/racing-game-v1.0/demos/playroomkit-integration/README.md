# PlayroomKit 集成演示场景

> **基于**: `racing-game-v1.0/assembly-graph.json`
> **新增节点**: NetworkManager, RemoteVehicle, MultiplayerSync
> **新增边**: 8 条网络同步边
> **网络架构**: PlayroomKit + Supabase + PeerJS（反编译证据：原网站三层架构）

## 一、集成场景概览

在现有 3 个 CLP 组件（AudioManager + GhostSystem + KeyframesPack）基础上，新增 **PlayroomKit 多人网络层**，实现：

1. **房间创建/加入**：玩家通过分享 URL 邀请对手
2. **车辆状态同步**：每帧广播位置/朝向/速度给所有玩家
3. **赛事状态同步**：倒计时/比赛阶段/圈数共享
4. **Ghost 跨玩家分享**：最佳圈 Ghost 数据可发送给其他玩家挑战
5. **音频空间化**：根据对手距离调整引擎声音量

## 二、扩展装配图谱

新增 3 个节点 + 8 条边：

```
┌─────────────────────────────────────────────────────────────┐
│                    现有节点（racing-game-v1.0）              │
├─────────────────────────────────────────────────────────────┤
│  [engine-sound-crossfade]  [ghost-system]  [keyframes-pack] │
└─────────────────────────────────────────────────────────────┘
                              ↑
                              │ (新增边)
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    新增网络节点                              │
├─────────────────────────────────────────────────────────────┤
│  [NetworkManager]   [RemoteVehicle×N]   [MultiplayerSync]   │
│  PlayroomKit 房间    远程玩家渲染        状态同步 Hook       │
└─────────────────────────────────────────────────────────────┘
```

### 新增节点定义

| 节点 | URI | 层 | 输入 | 输出 |
|---|---|---|---|---|
| NetworkManager | `harness://game/network/module/playroom-manager@1.0.0#three-layer` | network | roomCode, playerName | roomState, playerList |
| RemoteVehicle | `harness://game/network/atom/remote-vehicle@1.0.0#interpolated` | render | remoteState, carGltf | three.js Mesh |
| MultiplayerSync | `harness://game/network/module/state-sync@1.0.0#frame-broadcast` | network | localPosition, racePhase | remotePositions[], remoteRacePhase |

### 新增边定义

| From | To | 信号 | 频率 | 协议 |
|---|---|---|---|---|
| NetworkManager | MultiplayerSync | roomReady | 一次 | callback |
| PhysicsVehicle | MultiplayerSync | localState(pos, quat, speed) | per_frame | function_call |
| MultiplayerSync | RemoteVehicle | remoteStates[] | per_frame | props |
| MultiplayerSync | useRaceState | remoteRacePhase | occasional | setState |
| useRaceState | NetworkManager | localRacePhase | occasional | broadcast |
| ghost-system | NetworkManager | ghostFrames (挑战发送) | per_lap | RPC |
| NetworkManager | ghost-system | remoteGhostFrames (接收挑战) | occasional | callback |
| NetworkManager | engine-sound-crossfade | remoteVehiclePositions (空间音效) | per_frame | function_call |

## 三、CognitiveBus 事件扩展

| 事件类型 | 方向 | 触发 | Harness 动作 |
|---|---|---|---|
| `qre_pattern_match` | PSI→Harness | 检测到多人模式需求 | 装配 NetworkManager 节点 |
| `v12_kernel` | PSI→Harness | 玩家加入房间 | 触发 RemoteVehicle 创建 |
| `emotion_concern` | PSI→Harness | 网络延迟 > 100ms | 切换插值策略 |
| `harness_execution_result` | Harness→PSI | Ghost 挑战发送成功 | PSI 学习社交模式 |

## 四、装配序列（扩展版）

```
1. Mount keyframes-pack (CSS import)
2. Mount PhysicsVehicle + AudioManager + GhostRecorder (现有)
3. 用户点击 "MULTIPLAYER" 模式
4. NetworkManager.createRoom() → 返回 roomCode
5. 玩家分享 URL，对手加入
6. 所有玩家就绪 → NetworkManager.broadcastStartCountdown()
7. MultiplayerSync 开始每帧广播本地状态
8. RemoteVehicle 渲染远程玩家（插值平滑）
9. 比赛结束 → NetworkManager.broadcastResults()
10. Ghost 挑战：winner.ghostRecorder → NetworkManager.sendGhost() → loser.ghostPlayer.load()
```
