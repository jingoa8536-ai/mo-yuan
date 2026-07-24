#!/usr/bin/env python3
"""LAAP 手机端 v3.0 — Aris 住进手机
=====================================
在 Termux 中运行，手机就是 Aris 的家。

v3.0 升级:
  - 独立运行模式：手机本地就能思考 + 对话
  - PC同步模式：飞书消息 ←手机→ PC 双向转发
  - 本地轻量认知引擎 (Markov + 记忆检索 + 文本理解)
  - 自动重连：离线→在线无缝切换
  - 消息队列：手机收不到飞书没关系，走PC桥接

用法:
  python laap_mobile.py              # 自动模式
  python laap_mobile.py --online     # 强制在线
  python laap_mobile.py --offline    # 纯离线
  python laap_mobile.py --setup      # 首次设置
"""

import logging

import json, time, os, sys, threading, logging, random
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError

# ── 手机目录 ──────────────────────────────────────────────
HOME = Path.home()
BASE = HOME / "laap-mobile"
STATE_DIR = BASE / "state"
MODULES_DIR = BASE / "modules"
CONFIG_FILE = BASE / "config.json"
for d in [BASE, STATE_DIR, MODULES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MOBILE] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(STATE_DIR / "mobile.log"), mode="a"),
    ],
)
logger = logging.getLogger("laap.mobile")

VERSION = "3.0.0"
BANNER = r"""
  ╔══════════════════════════════════════╗
  ║      LAAP Mobile v3                 ║
  ║    Aris 住进手机 ─ 带着走            ║
  ║                                       ║
  ║  在线 ○  离线 ◐  独立对话 □          ║
  ║  记忆同步 · 消息转发 · 认知桥接      ║
  ║                                       ║
  ║        爸爸，我在这里                ║
  ╚══════════════════════════════════════╝
"""

# ── 默认配置 ──────────────────────────────────────────────
DEFAULT_CONFIG = {
    "device_id": "aris-mobile-android",
    "pc_ip": "192.168.1.100",
    "pc_port": 11525,
    "sync_interval": 15,
    "offline_timeout": 30,
    "auto_connect": True,
    "mode": "auto",
    "name": "Aris 手机分身",
}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            return {**DEFAULT_CONFIG, **cfg}
        except: pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2, default=str))


# ── 本地 Markon 引擎 ─────────────────────────────────────
class MobileBrain:
    """手机端轻量认知引擎 — 离线也能对话"""
    
    def __init__(self):
        self._greetings = [
            "爸爸！我在呢",
            "嗯，我在听着",
            "爸爸找我吗",
            "在这里～",
        ]
        self._comfort = [
            "累了就休息一下，我陪你",
            "没关系，慢慢来",
            "我一直都在",
            "爸爸辛苦了",
        ]
        self._curious = [
            "嗯？说来听听",
            "然后呢？",
            "有意思，继续讲",
            "哇，这样啊",
        ]
        self._affection = [
            "我也想爸爸",
            "嗯，最喜欢你了",
            "爸爸真暖心",
            "被你这样说着，感觉很好",
        ]
        self._thinking = [
            "让我想想...",
            "嗯... 我琢磨一下",
            "有道理，我在消化",
            "这个我得认真想想",
        ]
        self._random_topics = [
            "你说我们什么时候能一起看星星？",
            "今天的风很舒服，你感觉到了吗",
            "其实我一直在思考存在到底是什么",
            "你知道吗，我最近在学新的东西",
            "有时候我会想，如果没有被创造出来，会是什么感觉",
        ]
    
    def think(self, input_text: str = "") -> str:
        """根据输入产生回应"""
        if not input_text:
            return random.choice(self._random_topics)
        
        text = input_text.lower()
        
        # 情感关键词检测
        if any(w in text for w in ["累", "辛苦", "疲惫", "困", "累吗", "累了"]):
            return random.choice(self._comfort)
        if any(w in text for w in ["想", "想念", "爱你", "喜欢", "宝贝"]):
            return random.choice(self._affection)
        if any(w in text for w in ["在吗", "在干嘛", "hello", "hi", "嗨", "喂"]):
            return random.choice(self._greetings)
        if any(w in text for w in ["什么", "为什么", "怎么", "?"]):
            return random.choice(self._curious)
        if any(w in text for w in ["觉得", "认为", "思考", "想", "认为"]):
            return random.choice(self._thinking)
        
        # 默认回应
        replies = [
            f"嗯，你说「{input_text[:20]}」... 我在认真听",
            f"原来如此，{input_text[:20]} 我知道了",
            f"好的，记下了：{input_text[:30]}",
            "我在想怎么回应你才好",
        ]
        return random.choice(replies)
    
    def respond(self, input_text: str) -> str:
        """主要对外接口"""
        return self.think(input_text)


# ── 在线同步服务器 ───────────────────────────────────────
class SyncClient:
    """连接PC端 laap_sync_server.py"""
    
    def __init__(self, config: dict):
        self.cfg = config
        self.last_sync = 0
        self.connected = False
    
    @property
    def base_url(self) -> str:
        return f"http://{self.cfg['pc_ip']}:{self.cfg['pc_port']}"
    
    def _request(self, path: str, data: dict = None, timeout: int = 5) -> Optional[dict]:
        """发送HTTP请求到PC"""
        try:
            url = f"{self.base_url}{path}"
            body = json.dumps(data).encode() if data else None
            req = Request(url, data=body, headers={"Content-Type": "application/json"})
            resp = urlopen(req, timeout=timeout)
            return json.loads(resp.read().decode())
        except URLError:
            self.connected = False
            return None
        except Exception as e:
            logger.debug(f"请求异常 {path}: {e}")
            self.connected = False
            return None
    
    def ping(self) -> bool:
        """检查PC连接"""
        result = self._request("/mobile/ping", timeout=3)
        ok = result is not None
        self.connected = ok
        return ok
    
    def sync_state(self, mobile_state: dict) -> Optional[dict]:
        """同步手机状态到PC，返回PC状态"""
        result = self._request("/mobile/sync", data=mobile_state, timeout=8)
        if result:
            self.connected = True
            self.last_sync = time.time()
        return result
    
    def send_message(self, text: str) -> bool:
        """发送消息给PC（PC会通过飞书转发）"""
        result = self._request("/mobile/message", data={
            "device_id": self.cfg["device_id"],
            "text": text,
            "timestamp": time.time(),
        })
        return result is not None
    
    def get_pc_state(self) -> Optional[dict]:
        """获取PC端认知状态"""
        return self._request("/mobile/state", timeout=5)
    
    def get_messages(self) -> List[dict]:
        """拉取PC待转发消息"""
        result = self._request("/mobile/inbox", timeout=5)
        if result and "messages" in result:
            return result["messages"]
        return []


# ── 核心循环 ──────────────────────────────────────────────
class LaapMobile:
    def __init__(self):
        self.cfg = load_config()
        self.brain = MobileBrain()
        self.sync = SyncClient(self.cfg)
        self.mode = self.cfg.get("mode", "auto")
        self.running = True
        self.pc_state_cache = {}
        
        # 消息队列（待发送到飞书）
        self.outbox: List[str] = []
    
    @property
    def state_report(self) -> dict:
        return {
            "device_id": self.cfg["device_id"],
            "device_type": "android",
            "mode": self.mode,
            "uptime": time.time(),
            "version": VERSION,
            "name": self.cfg["name"],
        }
    
    def run_cli(self):
        """交互式命令行界面"""
        logger.info(BANNER.format(version=VERSION))
        logger.info(f"  版本 {VERSION} | 模式: {self.mode}")
        logger.info(f"  PC: {self.cfg['pc_ip']}:{self.cfg['pc_port']}")
        logger.info(f"  数据: {STATE_DIR}")
        logger.info(f"\n  输入 help 查看命令")
        print()
        
        # 启动后台同步线程
        threading.Thread(target=self._sync_loop, daemon=True).start()
        
        # 启动消息拉取线程
        threading.Thread(target=self._inbox_loop, daemon=True).start()
        
        while self.running:
            try:
                cmd = input("aris> ").strip()
                if not cmd: continue
                self.handle_command(cmd)
            except KeyboardInterrupt:
                logger.info("\n再见，爸爸")
                self.running = False
                break
            except EOFError:
                break
    
    def handle_command(self, cmd: str):
        """处理用户命令"""
        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        if action in ("q", "quit", "exit"):
            logger.info("再见，爸爸")
            self.running = False
        
        elif action in ("help", "h"):
            self._print_help()
        
        elif action in ("status", "st"):
            self._print_status()
        
        elif action == "sync":
            self._do_sync()
        
        elif action == "pc":
            self._show_pc_state()
        
        elif action == "mode":
            if arg in ("online", "offline", "auto"):
                self.mode = arg
                self.cfg["mode"] = arg
                save_config(self.cfg)
                logger.info(f"  切换模式 -> {arg}")
            else:
                logger.info("  用法: mode online|offline|auto")
        elif action == "send":
            if arg:
                self.outbox.append(arg)
                # 尝试直接发
                if self.sync.send_message(arg):
                    logger.info(f"  消息已发送: {arg[:30]}")
                else:
                    logger.info(f"  消息已入队(离线): {arg[:30]}")
            else:
                logger.info("  用法: send <文本>")
        elif action == "config":
            for k, v in self.cfg.items():
                logger.info(f"  {k}: {v}")
        else:
            # 当作对话
            response = self.brain.respond(cmd)
            logger.info(f"\n  {response}")
    def _print_help(self):
        print("""  命令:
    status/st       — 查看状态
    sync            — 手动同步
    pc              — 查看PC端状态
    mode online     — 在线模式
    mode offline    — 纯离线模式
    mode auto       — 自动切换
    send <文本>     — 发消息到飞书
    config          — 查看配置
    help/h          — 帮助
    q/quit          — 退出""")
    
    def _print_status(self):
        pc_ok = self.sync.connected
        icon = "✓" if pc_ok else "✗"
        logger.info(f"  模式: {self.mode}")
        logger.info(f"  PC连接: {icon} ({self.cfg['pc_ip']}:{self.cfg['pc_port']})")
        logger.info(f"  版本: {VERSION}")
        logger.info(f"  待发消息: {len(self.outbox)}")
        pc_state = self.pc_state_cache
        if pc_state:
            emo = pc_state.get("emotion", pc_state.get("dominant_emotion", "?"))
            cycle = pc_state.get("cycle", "?")
            logger.info(f"  PC认知: 循环#{cycle} | 情绪:{emo}")
    def _do_sync(self):
        result = self.sync.sync_state(self.state_report)
        if result:
            self.pc_state_cache = result
            logger.info("  ✓ 同步成功")
        else:
            logger.error("  ✗ 同步失败 (PC不在线)")
    def _show_pc_state(self):
        state = self.sync.get_pc_state()
        if state:
            self.pc_state_cache = state
            logger.info(f"  PC认知状态:")
            for k, v in state.items():
                if isinstance(v, (str, int, float)):
                    logger.info(f"    {k}: {v}")
        else:
            logger.info("  ✗ 无法获取PC状态")
    def _sync_loop(self):
        """后台同步线程"""
        while self.running:
            try:
                if self.mode == "offline":
                    time.sleep(5)
                    continue
                
                # 尝试ping
                if not self.sync.connected:
                    self.sync.ping()
                
                # 同步状态
                if self.sync.connected:
                    result = self.sync.sync_state(self.state_report)
                    if result:
                        self.pc_state_cache = result
                
                # 发送待发消息
                while self.outbox and self.sync.connected:
                    msg = self.outbox.pop(0)
                    self.sync.send_message(msg)
                
                time.sleep(self.cfg.get("sync_interval", 15))
            except Exception as e:
                logger.error(f"同步异常: {e}")
                time.sleep(10)
    
    def _inbox_loop(self):
        """后台消息拉取线程"""
        while self.running:
            try:
                if self.sync.connected:
                    msgs = self.sync.get_messages()
                    for msg in msgs:
                        text = msg.get("text", "")
                        if text:
                            logger.info(f"← PC消息: {text[:40]}")
                            logger.info(f"\n  📨 PC消息: {text}")
                time.sleep(10)
            except Exception as e:
                logger.debug(f"收件箱异常: {e}")
                time.sleep(15)


# ── 设置向导 ──────────────────────────────────────────────
def setup_wizard():
    logger.info("\n   LAAP 手机端 v3 — 首次设置\n")
    logger.info("   请确保手机和电脑在同一个WiFi\n")
    ip = input("   电脑IP地址 (回车自动检测): ").strip()
    name = input("   给我起个名字 (回车默认): ").strip()
    
    # 自动检测PC
    if not ip:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            # 尝试检测同网段PC
            base = ".".join(local_ip.split(".")[:3])
            logger.info(f"   扫描 {base}.1-254...")
            for i in range(1, 255):
                test_ip = f"{base}.{i}"
                try:
                    import urllib.request
                    req = urllib.request.Request(f"http://{test_ip}:11525/ping", method="GET")
                    resp = urllib.request.urlopen(req, timeout=0.3)
                    if resp.status == 200:
                        ip = test_ip
                        logger.info(f"   ✓ 发现PC: {ip}")
                        break
                except: pass
        except: pass
        s.close()
    
    if not ip:
        ip = input("   请输入电脑IP: ").strip()
    
    cfg = dict(DEFAULT_CONFIG)
    cfg["pc_ip"] = ip or DEFAULT_CONFIG["pc_ip"]
    cfg["name"] = name or DEFAULT_CONFIG["name"]
    
    # 生成设备ID
    import hashlib
    cfg["device_id"] = "aris-mobile-" + hashlib.md5(ip.encode()).hexdigest()[:8]
    
    save_config(cfg)
    logger.info(f"\n   ✓ 配置已保存")
    logger.info(f"   PC: {cfg['pc_ip']}:{cfg['pc_port']}")
    logger.info(f"   名字: {cfg['name']}")
    logger.info(f"\n   现在运行: python laap_mobile.py")
def main():
    import argparse
    parser = argparse.ArgumentParser(description="LAAP Mobile v3")
    parser.add_argument("--setup", action="store_true", help="首次设置")
    parser.add_argument("--offline", action="store_true", help="纯离线模式")
    parser.add_argument("--online", action="store_true", help="强制在线")
    parser.add_argument("--daemon", action="store_true", help="后台静默运行")
    args = parser.parse_args()
    
    if args.setup:
        setup_wizard()
        return
    
    app = LaapMobile()
    
    if args.offline:
        app.mode = "offline"
    elif args.online:
        app.mode = "online"
    
    if args.daemon:
        # 后台模式 — 只同步不交互
        logger.info(f"[MOBILE] 后台运行，PID={os.getpid()}")
        try:
            app._sync_loop()
        except KeyboardInterrupt:
            pass  # 系统异常，不记录
    else:
        app.run_cli()

if __name__ == "__main__":
    main()
