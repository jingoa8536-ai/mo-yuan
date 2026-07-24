/**
 * Ghost System 示例装配代码
 *
 * 展示如何在 PhysicsVehicle + Scene3D + test-race 中集成 Ghost 系统
 * 实际来源：
 *   - D:/ai-website-cloner-template-master/src/components/three/PhysicsVehicle.tsx
 *   - D:/ai-website-cloner-template-master/src/components/three/GhostVehicle.tsx
 *   - D:/ai-website-cloner-template-master/src/app/test-race/page.tsx
 */

import { useMemo, useEffect, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import {
  GhostRecorder,
  GhostPlayer,
  saveGhostToLocal,
  loadGhostFromLocal,
} from "harness://game/racing/module/ghost-system@1.0.0#localstorage";

// ============ 1. 在 PhysicsVehicle 中接入 GhostRecorder ============

function PhysicsVehicle({ ghostRecorder, racePhase }) {
  const carRef = useRef<THREE.Group>(null);
  const lastLapRef = useRef(0);

  // racing 阶段每帧录制
  useFrame(() => {
    if (!carRef.current || !ghostRecorder) return;

    if (racePhase === "racing") {
      const pos = carRef.current.position;
      const quat = carRef.current.quaternion;
      ghostRecorder.record(
        new THREE.Vector3(pos.x, pos.y, pos.z),
        new THREE.Quaternion(quat.x, quat.y, quat.z, quat.w),
        speed
      );
    }
  });
}

// ============ 2. 在 test-race 中管理 Ghost 生命周期 ============

function TestRacePage() {
  const ghostRecorder = useMemo(() => new GhostRecorder(), []);
  const ghostPlayer = useMemo(() => new GhostPlayer(), []);
  const [hasGhost, setHasGhost] = useState(false);
  const lastLapRef = useRef(0);

  // 加载本地 Ghost 数据
  useEffect(() => {
    const frames = loadGhostFromLocal(trackId);
    if (frames && frames.length > 0) {
      ghostPlayer.load(frames);
      setHasGhost(true);
    }
  }, [trackId]);

  // 监听圈数变化：完成一圈时保存 Ghost
  useEffect(() => {
    if (race.state.currentLap > lastLapRef.current && race.state.currentLap > 0) {
      const frames = ghostRecorder.finishLap();
      if (frames && frames.length > 10) {
        saveGhostToLocal(frames, trackId);
        ghostPlayer.load(frames);
        setHasGhost(true);
      }
    }
    lastLapRef.current = race.state.currentLap;
  }, [race.state.currentLap]);

  // racing 开始时启动回放
  useEffect(() => {
    if (race.phase === "racing" && hasGhost) {
      ghostPlayer.play();
    } else if (race.phase !== "racing") {
      ghostPlayer.stop();
    }
  }, [race.phase, hasGhost]);

  return (
    <Scene3D
      ghostRecorder={ghostRecorder}
      ghostPlayer={ghostPlayer}
      showGhost={hasGhost}
    />
  );
}

// ============ 3. 在 Scene3D 中渲染 Ghost 车辆 ============

function Scene3D({ ghostPlayer, showGhost, carGltf }) {
  return (
    <>
      <PhysicsVehicle ghostRecorder={ghostRecorder} />
      {showGhost && ghostPlayer.hasData() && (
        <GhostVehicle
          ghostPlayer={ghostPlayer}
          carGltf={carGltf}
          opacity={0.4}
        />
      )}
    </>
  );
}

// ============ 4. GhostVehicle 渲染组件 ============

function GhostVehicle({ ghostPlayer, carGltf, opacity = 0.4 }) {
  const groupRef = useRef<THREE.Group>(null);

  // 复用 GLB 模型，替换为半透明蓝色材质
  const carScene = useMemo(() => {
    if (!carGltf?.scene) return null;
    const cloned = carGltf.scene.clone(true);
    cloned.traverse((child) => {
      if (child instanceof THREE.Mesh) {
        child.castShadow = false;
        child.material = new THREE.MeshStandardMaterial({
          color: new THREE.Color("#7dd3fc"),
          transparent: true,
          opacity,
          emissive: new THREE.Color("#3683ff"),
          emissiveIntensity: 0.4,
          depthWrite: false,
        });
      }
    });
    return cloned;
  }, [carGltf, opacity]);

  // 每帧从 GhostPlayer 获取插值后的位置/朝向
  useFrame(() => {
    if (!groupRef.current) return;
    const state = ghostPlayer.update();
    if (state) {
      groupRef.current.position.copy(state.pos);
      groupRef.current.quaternion.copy(state.quat);
      groupRef.current.visible = true;
    } else {
      groupRef.current.visible = false;
    }
  });

  return (
    <group ref={groupRef}>
      {carScene && <primitive object={carScene} />}
    </group>
  );
}
