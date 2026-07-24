/**
 * RemoteVehicle — 远程玩家车辆渲染组件
 *
 * 装配图谱节点：harness://game/network/atom/remote-vehicle@1.0.0#interpolated
 *
 * 职责：
 *   1. 接收远程玩家状态
 *   2. 线性插值平滑位置/朝向（消除网络抖动）
 *   3. 复用 GLB 模型 clone（与本地车辆相同）
 *   4. 不同颜色区分玩家
 *   5. 显示玩家名称（Html 标签）
 */

"use client";

import { useRef, useMemo, useEffect } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import type { VehicleNetworkState } from "./NetworkManager";

interface RemoteVehicleProps {
  playerId: string;
  playerName: string;
  playerColor: string;
  remoteState: VehicleNetworkState | undefined;
  carGltf: any;
  interpolationFactor?: number; // 0-1, 默认 0.15（平滑度）
}

export function RemoteVehicle({
  playerId,
  playerName,
  playerColor,
  remoteState,
  carGltf,
  interpolationFactor = 0.15,
}: RemoteVehicleProps) {
  const groupRef = useRef<THREE.Group>(null);
  const targetPos = useRef(new THREE.Vector3());
  const targetQuat = useRef(new THREE.Quaternion());
  const hasReceived = useRef(false);

  // 共享 GLB 模型 clone，用玩家颜色着色
  const carScene = useMemo(() => {
    if (!carGltf?.scene) return null;
    const cloned = carGltf.scene.clone(true);
    const color = new THREE.Color(playerColor);
    cloned.traverse((child: any) => {
      if (child instanceof THREE.Mesh) {
        child.castShadow = true;
        child.receiveShadow = false;
        if (child.material) {
          const oldMat = child.material;
          child.material = new THREE.MeshStandardMaterial({
            color,
            metalness: 0.6,
            roughness: 0.4,
            emissive: color,
            emissiveIntensity: 0.15,
          });
          if (oldMat.dispose) oldMat.dispose();
        }
      }
    });
    return cloned;
  }, [carGltf, playerColor]);

  // 收到新状态时更新目标位置
  useEffect(() => {
    if (!remoteState) return;
    targetPos.current.set(
      remoteState.position.x,
      remoteState.position.y,
      remoteState.position.z
    );
    targetQuat.current.set(
      remoteState.quaternion.x,
      remoteState.quaternion.y,
      remoteState.quaternion.z,
      remoteState.quaternion.w
    );
    hasReceived.current = true;
  }, [remoteState]);

  // 首次收到状态前不渲染
  useEffect(() => {
    if (groupRef.current && !hasReceived.current) {
      groupRef.current.visible = false;
    } else if (groupRef.current && hasReceived.current) {
      groupRef.current.visible = true;
    }
  }, [hasReceived.current]);

  useFrame(() => {
    if (!groupRef.current || !hasReceived.current) return;

    // 线性插值平滑（lerp + slerp）
    groupRef.current.position.lerp(targetPos.current, interpolationFactor);
    groupRef.current.quaternion.slerp(targetQuat.current, interpolationFactor);
  });

  if (!carGltf) return null;

  return (
    <group ref={groupRef}>
      {carScene && <primitive object={carScene} />}

      {/* 玩家名称标签（漂浮在车辆上方） */}
      <Html position={[0, 3, 0]} center distanceFactor={10} occlude>
        <div
          style={{
            background: `linear-gradient(135deg, ${playerColor}40, ${playerColor}80)`,
            border: `1px solid ${playerColor}`,
            color: "white",
            padding: "2px 8px",
            borderRadius: "4px",
            fontSize: "11px",
            fontFamily: "Oxanium, sans-serif",
            fontWeight: 700,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            whiteSpace: "nowrap",
            pointerEvents: "none",
            boxShadow: `0 0 10px ${playerColor}40`,
          }}
        >
          {playerName}
        </div>
      </Html>
    </group>
  );
}

/**
 * RemoteVehiclesGroup — 批量渲染所有远程玩家
 */
interface RemoteVehiclesGroupProps {
  remoteStates: Map<string, VehicleNetworkState>;
  players: Array<{ id: string; name: string; color: string }>;
  carGltf: any;
}

export function RemoteVehiclesGroup({
  remoteStates,
  players,
  carGltf,
}: RemoteVehiclesGroupProps) {
  return (
    <>
      {players.map((player) => (
        <RemoteVehicle
          key={player.id}
          playerId={player.id}
          playerName={player.name}
          playerColor={player.color}
          remoteState={remoteStates.get(player.id)}
          carGltf={carGltf}
        />
      ))}
    </>
  );
}
