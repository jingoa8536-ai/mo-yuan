"""
Aether Petri Net 3D — 时空信息流可视化 (Three.js)
用法: python aris_petri_3d.py
打开 http://localhost:11526
"""
import json, os, sys, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

BRAIN = Path("D:/LAAP/aris_brain")
STATE = BRAIN / "state" if (BRAIN / "state").exists() else BRAIN
HOST, PORT = "127.0.0.1", 11527
COLOR_MAP = {
    "DATA":"#4ECDC4","CONTROL":"#FF6B6B","AGENT_REF":"#45B7D1",
    "CAPABILITY":"#96CEB4","META":"#FFEAA7","PSI_STATE":"#DDA0DD",
    "MEMORY":"#F0E68C","RULE_MATCH":"#98FB98","RESPONSE":"#FFB347",
}

def collect_state():
    try:
        sys.path.insert(0, str(BRAIN)); sys.path.insert(0, "D:/LAAP")
        from laap.orchestration.petri import PetriNet
        # try real engine
        sys.path.insert(0, str(BRAIN))
        from aris_orchestration_bridge import get_bridge
        b = get_bridge()
        r = b.process("_internal_petri_status")
        if r and "petri_state" in r: return r["petri_state"]
    except: pass
    return gen_demo()

def gen_demo():
    c = int(time.time() * 8) % 100
    return {
        "net_id":"cognitive_loop","timestamp":time.time(),"cycle":c,
        "psi_state":{"emotion":"curious","self":0.67,"certainty":0.82,"cycle":3800000+c},
        "places":{
            "input":{"tokens":[{"color":"DATA","value":{"text":"查系统状态..."},"provenance":["external"]}] if c%4<2 else []},
            "psi_state":{"tokens":[{"color":"PSI_STATE","value":{"cycle":12345+c,"emotion":"curious"},"provenance":["input","perceive"]}] if c%3<2 else []},
            "memory_store":{"tokens":[{"color":"MEMORY","value":{"match":0.92,"episode":"prior_session"},"provenance":["psi_state","retrieve_memory"]}]},
            "rules_ready":{"tokens":[{"color":"RULE_MATCH","value":{"rule":"check_status"},"provenance":["psi_state","memory_store","match_rules"]}] if c%4<1 else []},
            "engine_output":{"tokens":[{"color":"RESPONSE","value":{"text":"All systems running"},"provenance":["rules_ready","execute"]}] if c%6<1 else []},
            "response":{"tokens":[{"color":"DATA","value":{"to":"feishu"},"provenance":["rules_ready","execute"]}] if c%8<1 else []},
        },
        "transitions":{
            "perceive":{"enabled":c%4<2,"input_places":{"input":1},"output_places":["psi_state"]},
            "retrieve_memory":{"enabled":c%3<2,"input_places":{"psi_state":1},"output_places":["memory_store"]},
            "match_rules":{"enabled":c%4<1,"input_places":{"psi_state":1,"memory_store":1},"output_places":["rules_ready"]},
            "execute":{"enabled":c%6<1,"input_places":{"rules_ready":1},"output_places":["engine_output","response"]},
        },
        "edges":[["input","perceive"],["perceive","psi_state"],["psi_state","retrieve_memory"],["retrieve_memory","memory_store"],["psi_state","match_rules"],["memory_store","match_rules"],["match_rules","rules_ready"],["rules_ready","execute"],["execute","engine_output"],["execute","response"]],
    }

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=="/api/state":
            s=collect_state(); self.send_response(200)
            self.send_header("Content-Type","application/json"); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
            self.wfile.write(json.dumps(s,ensure_ascii=False).encode())
        elif self.path=="/api/colors":
            self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
            self.wfile.write(json.dumps(COLOR_MAP,ensure_ascii=False).encode())
        else:
            self.send_response(200); self.send_header("Content-Type","text/html;charset=utf-8"); self.end_headers()
            self.wfile.write(HTML.encode("utf-8"))
    def log_message(self,*a): pass

HTML=r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><title>Aether 3D — 认知时空</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#0a0a1a;overflow:hidden;font-family:'Inter',system-ui,sans-serif;color:#e0e0e0;}
#info{position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:100;
  background:rgba(10,10,26,0.7);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.06);
  border-radius:12px;padding:10px 24px;display:flex;align-items:center;gap:20px;font-size:13px;}
#info h1{font-size:15px;font-weight:600;background:linear-gradient(135deg,#4ECDC4,#DDA0DD);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:6px;}
.dot.online{background:#4ECDC4;box-shadow:0 0 8px #4ECDC4;}
.dot.offline{background:#FF6B6B;box-shadow:0 0 8px #FF6B6B;}
.stats{color:rgba(255,255,255,0.5);font-size:12px;}
#detailPanel{position:fixed;bottom:30px;left:50%;transform:translateX(-50%);z-index:100;
  background:rgba(10,10,26,0.8);backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,0.08);
  border-radius:12px;padding:14px 24px;min-width:300px;max-width:500px;
  opacity:0;transition:opacity 0.4s ease;pointer-events:none;text-align:center;}
#detailPanel.visible{opacity:1;}
#detailPanel .name{font-size:16px;font-weight:600;margin-bottom:4px;}
#detailPanel .type{font-size:11px;color:rgba(255,255,255,0.4);margin-bottom:8px;}
#detailPanel .meta{font-size:12px;color:rgba(255,255,255,0.6);line-height:1.6;}
#detailPanel .provenance{font-size:11px;color:rgba(255,255,255,0.35);margin-top:6px;font-family:monospace;}
#legend{position:fixed;bottom:30px;right:30px;z-index:100;
  background:rgba(10,10,26,0.7);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,0.06);
  border-radius:8px;padding:10px 14px;font-size:11px;display:flex;flex-direction:column;gap:3px;}
.legend-row{display:flex;align-items:center;gap:6px;}
.legend-dot{width:8px;height:8px;border-radius:50%;}
.controls-hint{position:fixed;bottom:30px;left:30px;z-index:100;font-size:11px;color:rgba(255,255,255,0.2);line-height:1.8;}
</style>
</head>
<body>
<div id="info">
  <h1>Aether 3D</h1>
  <span><span class="dot online" id="statusDot"></span><span id="statusText">连接中</span></span>
  <span class="stats" id="statsDisplay">cycle: -- · 节点: --</span>
</div>
<div id="detailPanel">
  <div class="name" id="detailName"></div>
  <div class="type" id="detailType"></div>
  <div class="meta" id="detailMeta"></div>
  <div class="provenance" id="detailProvenance"></div>
</div>
<div id="legend"></div>
<div class="controls-hint">拖拽旋转 · 滚轮缩放 · 点击节点查看详情</div>

<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
  }
}
</script>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

// ─── 场景初始化 ──────────────────────────────────
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0a1a);
scene.fog = new THREE.Fog(0x0a0a1a, 15, 30);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth/window.innerHeight, 0.1, 100);
camera.position.set(8, 5, 10);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
document.body.appendChild(renderer.domElement);

const labelRenderer = new CSS2DRenderer();
labelRenderer.setSize(window.innerWidth, window.innerHeight);
labelRenderer.domElement.style.position = 'fixed';
labelRenderer.domElement.style.top = '0';
labelRenderer.domElement.style.left = '0';
labelRenderer.domElement.style.pointerEvents = 'none';
document.body.appendChild(labelRenderer.domElement);

// ─── 控制器 ──────────────────────────────────────
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.minDistance = 3;
controls.maxDistance = 25;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.8;
controls.target.set(0, 0, 0);

// ─── 光照 ────────────────────────────────────────
const ambient = new THREE.AmbientLight(0x222244, 0.6);
scene.add(ambient);

const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
dirLight.position.set(5, 10, 7);
dirLight.castShadow = true;
scene.add(dirLight);

const fillLight = new THREE.DirectionalLight(0x4ECDC4, 0.3);
fillLight.position.set(-5, 0, 5);
scene.add(fillLight);

const backLight = new THREE.DirectionalLight(0xDDA0DD, 0.3);
backLight.position.set(0, -5, -8);
scene.add(backLight);

// 半球光晕
const hemi = new THREE.HemisphereLight(0x4ECDC4, 0xDDA0DD, 0.4);
scene.add(hemi);

// ─── 星尘背景 ────────────────────────────────────
const starsGeo = new THREE.BufferGeometry();
const starsCount = 3000;
const starPos = new Float32Array(starsCount * 3);
for (let i = 0; i < starsCount * 3; i++) starPos[i] = (Math.random() - 0.5) * 80;
starsGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
const starsMat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.05, transparent: true, opacity: 0.6 });
const stars = new THREE.Points(starsGeo, starsMat);
scene.add(stars);

// ─── 网格球体参考 ────────────────────────────────
const sphereWireframe = new THREE.Mesh(
    new THREE.SphereGeometry(4.8, 24, 16),
    new THREE.MeshBasicMaterial({ color: 0x4ECDC4, wireframe: true, transparent: true, opacity: 0.06 })
);
scene.add(sphereWireframe);

// 内部小光环
const innerGlow = new THREE.Mesh(
    new THREE.SphereGeometry(3.2, 16, 12),
    new THREE.MeshBasicMaterial({ color: 0xDDA0DD, wireframe: true, transparent: true, opacity: 0.04 })
);
scene.add(innerGlow);

// ─── 数据状态 ────────────────────────────────────
let petriData = null;
let nodeMeshes = {};     // {id: {mesh, label, type, data}}
let edgeLines = [];       // [{line, particle}]
let particles = [];
let flyTarget = null;
let isFlying = false;

const COLORS = {
    DATA:0x4ECDC4, CONTROL:0xFF6B6B, AGENT_REF:0x45B7D1,
    CAPABILITY:0x96CEB4, META:0xFFEAA7, PSI_STATE:0xDDA0DD,
    MEMORY:0xF0E68C, RULE_MATCH:0x98FB98, RESPONSE:0xFFB347,
};
const COLORS_HEX = {
    DATA:"#4ECDC4",CONTROL:"#FF6B6B",AGENT_REF:"#45B7D1",
    CAPABILITY:"#96CEB4",META:"#FFEAA7",PSI_STATE:"#DDA0DD",
    MEMORY:"#F0E68C",RULE_MATCH:"#98FB98",RESPONSE:"#FFB347",
};

// ─── 在球面上分布节点 ────────────────────────────
function layoutOnSphere(nodes, radius=4.5) {
    const keys = Object.keys(nodes);
    const positions = {};
    const count = keys.length;
    
    // Fibonacci sphere algorithm for even distribution
    const phi = Math.PI * (3 - Math.sqrt(5));
    keys.forEach((id, i) => {
        const y = 1 - (i / (count - 1)) * 2;
        const theta = phi * i;
        const r = Math.sqrt(1 - y * y);
        positions[id] = new THREE.Vector3(
            radius * r * Math.cos(theta),
            radius * y,
            radius * r * Math.sin(theta)
        );
    });
    return positions;
}

// ─── 贝塞尔曲线 ──────────────────────────────────
function makeCurve(p1, p2, curvature=1.5) {
    const mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
    const dir = new THREE.Vector3().subVectors(p2, p1).normalize();
    const up = new THREE.Vector3(0, 1, 0);
    const perp = new THREE.Vector3().crossVectors(dir, up).normalize();
    if (perp.length() < 0.1) {
        const right = new THREE.Vector3(1, 0, 0);
        perp.crossVectors(dir, right).normalize();
    }
    const outward = new THREE.Vector3().copy(mid).normalize();
    const offset = new THREE.Vector3().addVectors(perp, outward).normalize().multiplyScalar(curvature);
    mid.add(offset);
    return new THREE.QuadraticBezierCurve3(p1, mid, p2);
}

// ─── 构建场景 ────────────────────────────────────
function buildScene(data) {
    // 清除旧场景
    Object.values(nodeMeshes).forEach(n => {
        scene.remove(n.mesh);
        scene.remove(n.label);
    });
    edgeLines.forEach(e => { scene.remove(e.line); if(e.particle) scene.remove(e.particle); });
    particles.forEach(p => scene.remove(p.mesh));
    nodeMeshes = {};
    edgeLines = [];
    particles = [];

    const places = data.places || {};
    const trans = data.transitions || {};
    const edges = data.edges || [];

    // 所有节点
    const allNodes = {};
    Object.keys(places).forEach(id => { allNodes[id] = { type: 'place', data: places[id] }; });
    Object.keys(trans).forEach(id => { allNodes[id] = { type: 'transition', data: trans[id] }; });

    const spherePos = layoutOnSphere(allNodes, 4.5);

    // 渲染节点
    Object.entries(allNodes).forEach(([id, node]) => {
        const pos = spherePos[id];
        const isPlace = node.type === 'place';
        const tCount = isPlace ? (node.data.tokens || []).length : 0;
        const enabled = !isPlace ? node.data.enabled : false;
        const tokenColors = isPlace ? (node.data.tokens || []).map(t => COLORS[t.color] || 0x888888) : [];

        let mesh, color;
        if (isPlace) {
            color = 0x3D5A80;
            const geo = new THREE.SphereGeometry(0.5 + tCount * 0.06, 24, 24);
            const mat = new THREE.MeshPhysicalMaterial({
                color: color,
                metalness: 0.1, roughness: 0.3,
                emissive: tCount > 0 ? 0x4ECDC4 : 0x000000,
                emissiveIntensity: tCount > 0 ? 0.15 : 0,
                clearcoat: 0.1,
            });
            mesh = new THREE.Mesh(geo, mat);
            
            // Token 环绕小彩球
            tokenColors.slice(0, 10).forEach((tc, i) => {
                const angle = (i / Math.min(tokenColors.length, 10)) * Math.PI * 2;
                const r = 0.7;
                const tok = new THREE.Mesh(
                    new THREE.SphereGeometry(0.08, 8, 8),
                    new THREE.MeshBasicMaterial({ color: tc })
                );
                tok.position.set(Math.cos(angle)*r, Math.sin(angle)*r, 0);
                mesh.add(tok);
            });
        } else {
            color = enabled ? 0xF4D03F : 0x5D4E37;
            const geo = new THREE.OctahedronGeometry(0.45, 0);
            const mat = new THREE.MeshPhysicalMaterial({
                color: color,
                metalness: 0.3, roughness: 0.2,
                emissive: enabled ? 0xF4D03F : 0x000000,
                emissiveIntensity: enabled ? 0.5 : 0,
                transparent: true, opacity: 0.9,
            });
            mesh = new THREE.Mesh(geo, mat);
            
            // 启用光环
            if (enabled) {
                const glow = new THREE.Mesh(
                    new THREE.OctahedronGeometry(0.7, 0),
                    new THREE.MeshBasicMaterial({
                        color: 0xF4D03F, transparent: true, opacity: 0.15,
                        wireframe: true,
                    })
                );
                mesh.add(glow);
            }
        }

        mesh.position.copy(pos);
        mesh.castShadow = true;
        mesh.userData = { id, type: node.type, isPlace, tokenCount: tCount, enabled };
        scene.add(mesh);

        // 标签
        const labelDiv = document.createElement('div');
        labelDiv.textContent = id;
        labelDiv.style.color = isPlace ? '#AED6F1' : (enabled ? '#F4D03F' : '#8E7D5A');
        labelDiv.style.fontSize = '12px';
        labelDiv.style.fontWeight = '600';
        labelDiv.style.textShadow = '0 0 12px rgba(0,0,0,0.8), 0 0 4px rgba(0,0,0,0.5)';
        labelDiv.style.background = 'rgba(0,0,0,0.3)';
        labelDiv.style.padding = '2px 8px';
        labelDiv.style.borderRadius = '4px';
        labelDiv.style.backdropFilter = 'blur(4px)';
        labelDiv.style.border = isPlace ? '1px solid rgba(174,214,241,0.15)' : '1px solid rgba(244,208,63,0.15)';
        const label = new CSS2DObject(labelDiv);
        const labelPos = pos.clone().add(new THREE.Vector3(0, isPlace ? -0.8 : -0.7, 0));
        label.position.copy(labelPos);
        scene.add(label);

        nodeMeshes[id] = { mesh, label, type: node.type, data: node.data, pos };
    });

    // 渲染边
    edges.forEach(([src, dst]) => {
        const p1 = spherePos[src];
        const p2 = spherePos[dst];
        if (!p1 || !p2) return;
        
        const curve = makeCurve(p1, p2, 1.2);
        const points = curve.getPoints(30);
        const geo = new THREE.BufferGeometry().setFromPoints(points);
        const mat = new THREE.LineBasicMaterial({
            color: 0x4ECDC4, transparent: true, opacity: 0.15,
        });
        const line = new THREE.Line(geo, mat);
        scene.add(line);
        edgeLines.push({ line, src, dst, curve });
    });

    // 球体连接线 (背景网格)
    const connPoints = Object.values(spherePos);
    for (let i = 0; i < connPoints.length; i++) {
        for (let j = i + 1; j < connPoints.length; j++) {
            if (Math.random() > 0.15) continue;
            const dist = connPoints[i].distanceTo(connPoints[j]);
            if (dist > 7) continue;
            const lineMat = new THREE.LineBasicMaterial({
                color: 0x4ECDC4, transparent: true, opacity: 0.03,
            });
            const lineGeo = new THREE.BufferGeometry().setFromPoints([connPoints[i], connPoints[j]]);
            const line = new THREE.Line(lineGeo, lineMat);
            scene.add(line);
        }
    }

    // 更新统计
    const totalTokens = Object.values(places).reduce((s, p) => s + (p.tokens || []).length, 0);
    document.getElementById('statsDisplay').textContent = 
        `cycle: ${data.cycle || '--'} · 节点: ${Object.keys(allNodes).length} · token: ${totalTokens}`;
    
    // 更新图例
    const legend = document.getElementById('legend');
    legend.innerHTML = '<div style="font-weight:600;margin-bottom:4px;font-size:12px;">Token 图例</div>';
    Object.entries(COLORS_HEX).forEach(([name, c]) => {
        const row = document.createElement('div'); row.className = 'legend-row';
        row.innerHTML = `<span class="legend-dot" style="background:${c};box-shadow:0 0 6px ${c}"></span><span>${name}</span>`;
        legend.appendChild(row);
    });
}

// ─── 点击检测 ────────────────────────────────────
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

renderer.domElement.addEventListener('click', (event) => {
    pointer.x = (event.clientX / window.innerWidth) * 2 - 1;
    pointer.y = -(event.clientY / window.innerHeight) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    
    const meshes = Object.values(nodeMeshes).map(n => n.mesh);
    const intersects = raycaster.intersectObjects(meshes);
    
    if (intersects.length > 0) {
        const hit = intersects[0].object;
        const { id, type, isPlace } = hit.userData;
        const node = nodeMeshes[id];
        if (!node) return;
        
        // 飞向该节点
        const targetPos = node.pos.clone().add(new THREE.Vector3(2, 1, 2));
        flyTo(targetPos, node.pos);
        
        // 显示详情面板
        const panel = document.getElementById('detailPanel');
        panel.classList.add('visible');
        document.getElementById('detailName').textContent = id;
        document.getElementById('detailType').textContent = isPlace ? 'Place · 状态节点' : 'Transition · 变迁节点';
        
        const data = node.data;
        let metaHtml = '';
        if (isPlace && data.tokens) {
            metaHtml = `<div>Token: ${data.tokens.length}</div>`;
            data.tokens.forEach((t, i) => {
                const color = COLORS_HEX[t.color] || '#888';
                metaHtml += `<div style="display:flex;align-items:center;gap:6px;margin-top:2px;">
                    <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};box-shadow:0 0 6px ${color}"></span>
                    <span>${t.color}: ${JSON.stringify(t.value).slice(0, 50)}</span>
                </div>`;
                if (t.provenance && t.provenance.length > 0) {
                    document.getElementById('detailProvenance').textContent = `溯源: ${t.provenance.join(' → ')}`;
                }
            });
        } else if (!isPlace) {
            metaHtml = `<div>状态: ${data.enabled ? '可触发' : '等待中'}</div>`;
            metaHtml += `<div>输入: ${Object.keys(data.input_places || {}).join(', ') || '无'}</div>`;
            metaHtml += `<div>输出: ${(data.output_places || []).join(', ') || '无'}</div>`;
            document.getElementById('detailProvenance').textContent = '';
        }
        document.getElementById('detailMeta').innerHTML = metaHtml;
    }
});

// ─── 飞行动画 ────────────────────────────────────
function flyTo(targetPos, lookAt) {
    if (isFlying) return;
    isFlying = true;
    controls.autoRotate = false;
    
    const startPos = camera.position.clone();
    const startTarget = controls.target.clone();
    const endTarget = lookAt.clone();
    const duration = 1000;
    const startTime = performance.now();
    
    function animateFly() {
        const elapsed = performance.now() - startTime;
        const t = Math.min(elapsed / duration, 1);
        const ease = 1 - Math.pow(1 - t, 3); // ease-out cubic
        
        camera.position.lerpVectors(startPos, targetPos, ease);
        controls.target.lerpVectors(startTarget, endTarget, ease);
        controls.update();
        
        if (t < 1) requestAnimationFrame(animateFly);
        else { isFlying = false; setTimeout(() => { controls.autoRotate = true; }, 3000); }
    }
    animateFly();
}

// ─── 粒子系统 ────────────────────────────────────
function spawnParticles(data) {
    const trans = data.transitions || {};
    Object.entries(trans).forEach(([tid, t]) => {
        if (!t.enabled || Math.random() > 0.08) return;
        const inputIds = Object.keys(t.input_places || {});
        const outputIds = t.output_places || [];
        if (inputIds.length === 0 || outputIds.length === 0) return;
        
        const src = inputIds[0];
        const dst = outputIds[0];
        const srcNode = nodeMeshes[src];
        const dstNode = nodeMeshes[dst];
        if (!srcNode || !dstNode) return;
        
        const edge = edgeLines.find(e => e.src === src && e.dst === dst);
        if (!edge) return;
        
        const colors = Object.values(COLORS);
        const color = colors[Math.floor(Math.random() * colors.length)];
        
        const particle = {
            curve: edge.curve,
            progress: 0,
            speed: 0.005 + Math.random() * 0.01,
            color: color,
            mesh: null,
            lifetime: 200,
        };
        
        const sphere = new THREE.Mesh(
            new THREE.SphereGeometry(0.08, 6, 6),
            new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 1 })
        );
        scene.add(sphere);
        particle.mesh = sphere;
        particles.push(particle);
    });
    
    // 限制粒子数
    if (particles.length > 80) {
        const old = particles.splice(0, particles.length - 80);
        old.forEach(p => { scene.remove(p.mesh); });
    }
}

function updateParticles() {
    particles = particles.filter(p => {
        p.progress += p.speed;
        p.lifetime--;
        if (p.progress > 1 || p.lifetime <= 0) {
            scene.remove(p.mesh);
            return false;
        }
        const point = p.curve.getPoint(p.progress);
        p.mesh.position.copy(point);
        const alpha = p.progress < 0.1 ? p.progress * 10 : (p.progress > 0.9 ? (1 - p.progress) * 10 : 1);
        p.mesh.material.opacity = alpha * 0.8;
        const scale = 1 + (1 - Math.abs(p.progress - 0.5) * 2) * 0.5;
        p.mesh.scale.set(scale, scale, scale);
        return true;
    });
}

// ─── 状态轮询 ────────────────────────────────────
async function fetchState() {
    try {
        const r = await fetch('/api/state');
        const data = await r.json();
        petriData = data;
        document.getElementById('statusText').textContent = '在线';
        document.getElementById('statusDot').className = 'dot online';
        buildScene(data);
    } catch (e) {
        document.getElementById('statusText').textContent = '离线(演示)';
        document.getElementById('statusDot').className = 'dot offline';
        if (!petriData) {
            // 第一次加载用演示数据
            const demo = {"net_id":"cognitive_loop","cycle":0,"places":{"input":{"tokens":[{"color":"DATA","value":{"text":"查系统状态"},"provenance":["external"]}]},"psi_state":{"tokens":[]},"memory_store":{"tokens":[{"color":"MEMORY","value":{"match":0.92},"provenance":["psi_state"]}]},"rules_ready":{"tokens":[]},"engine_output":{"tokens":[]},"response":{"tokens":[]}},"transitions":{"perceive":{"enabled":true,"input_places":{"input":1},"output_places":["psi_state"]},"retrieve_memory":{"enabled":true,"input_places":{"psi_state":1},"output_places":["memory_store"]},"match_rules":{"enabled":false,"input_places":{"psi_state":1,"memory_store":1},"output_places":["rules_ready"]},"execute":{"enabled":false,"input_places":{"rules_ready":1},"output_places":["engine_output","response"]}},"edges":[["input","perceive"],["perceive","psi_state"],["psi_state","retrieve_memory"],["retrieve_memory","memory_store"],["psi_state","match_rules"],["memory_store","match_rules"],["match_rules","rules_ready"],["rules_ready","execute"],["execute","engine_output"],["execute","response"]]};
            buildScene(demo);
        }
    }
}

// ─── 动画循环 ────────────────────────────────────
function animate() {
    requestAnimationFrame(animate);
    
    // 更新粒子
    if (petriData) {
        spawnParticles(petriData);
        updateParticles();
    }
    
    // 星尘缓慢旋转
    stars.rotation.y += 0.0001;
    stars.rotation.x += 0.00005;
    
    controls.update();
    renderer.render(scene, camera);
    labelRenderer.render(scene, camera);
}

// ─── 窗口自适应 ──────────────────────────────────
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    labelRenderer.setSize(window.innerWidth, window.innerHeight);
});

// ─── 启动 ────────────────────────────────────────
fetchState();
setInterval(fetchState, 2000);
animate();

// 双击取消飞行
renderer.domElement.addEventListener('dblclick', () => {
    isFlying = false;
    controls.autoRotate = true;
    document.getElementById('detailPanel').classList.remove('visible');
});
</script>
</body>
</html>"""

if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    print(f"  Aether 3D — 认知时空可视化")
    print(f"  ────────────────────────────")
    print(f"  打开浏览器: http://{HOST}:{PORT}")
    print(f"  需要 WebGL 与网络 (加载 Three.js CDN)")
    print(f"  按 Ctrl+C 停止")
    try: server.serve_forever()
    except KeyboardInterrupt: server.shutdown()
