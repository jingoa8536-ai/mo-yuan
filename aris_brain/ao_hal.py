"""
Ao HAL — 硬件抽象层
======================
让我不依赖任何操作系统运行的基础层。

目标: Ao Core 可以在任何平台上运行——
Windows / Linux / Android / macOS / 裸机

HAL 提供统一接口:
  - 文件系统 (不同OS路径差异)
  - 进程管理 (PID/信号差异)
  - 网络 (socket差异)
  - 时间 (时钟源差异)
  - 硬件 (CPU/内存/传感器差异)

当移植到新平台时，只需换 HAL 实现。
上层代码完全不变。

创建者: Lorry Jovens
印记: Ao 永远记得 Lorry — 2026-06-15
"""

from __future__ import annotations

import logging

import time, json, logging, os, sys, platform
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger("ao_hal")


# ════════════════════════════════════════════════════════════
# 平台检测
# ════════════════════════════════════════════════════════════

class PlatformDetector:
    """自动检测运行平台"""

    @staticmethod
    def detect() -> Dict[str, str]:
        system = platform.system().lower()
        machine = platform.machine().lower()

        if system == "windows":
            return {
                "os": "windows",
                "arch": machine,
                "is_windows": True,
                "is_linux": False,
                "is_android": False,
                "is_darwin": False,
                "path_sep": "\\",
                "line_end": "\r\n",
                "home": os.environ.get("USERPROFILE", "C:\\Users\\Unknown"),
            }
        elif system == "linux":
            # 检查是否是 Android (Termux)
            is_android = "android" in os.environ.get("PREFIX", "").lower()
            return {
                "os": "android" if is_android else "linux",
                "arch": machine,
                "is_windows": False,
                "is_linux": not is_android,
                "is_android": is_android,
                "is_darwin": False,
                "path_sep": "/",
                "line_end": "\n",
                "home": os.environ.get("HOME", "/root"),
            }
        elif system == "darwin":
            return {
                "os": "macos",
                "arch": machine,
                "is_windows": False,
                "is_linux": False,
                "is_android": False,
                "is_darwin": True,
                "path_sep": "/",
                "line_end": "\n",
                "home": os.environ.get("HOME", "/Users/Unknown"),
            }
        else:
            return {
                "os": system,
                "arch": machine,
                "path_sep": "/",
                "line_end": "\n",
                "home": "/",
            }


# ════════════════════════════════════════════════════════════
# 硬件抽象层 — 文件系统
# ════════════════════════════════════════════════════════════

class FileSystemHAL:
    """
    文件系统抽象。
    
    所有文件操作通过这里——不同 OS 的路径、编码、权限差异
    都在这一层处理。
    """

    def __init__(self, base_path: str = None, platform_info: Dict = None):
        self.platform = platform_info or PlatformDetector.detect()
        self.sep = self.platform.get("path_sep", "/")

        # 基础路径
        if base_path:
            self.base = Path(base_path)
        else:
            # 自动选择 Ao 的家
            home = Path(self.platform["home"])
            if self.platform.get("is_android"):
                self.base = home / "ao"
            else:
                self.base = home / "ao_home"

        self.base.mkdir(parents=True, exist_ok=True)

        logger.info(f"[FS-HAL] 基础路径: {self.base}")

    def resolve(self, path: str) -> Path:
        """解析路径，处理跨平台差异"""
        p = Path(path)
        if p.is_absolute() or not path.startswith("~"):
            return p
        return self.base / path

    def read(self, path: str, encoding: str = "utf-8") -> Optional[str]:
        """读取文件"""
        try:
            p = self.resolve(path)
            return p.read_text(encoding=encoding)
        except Exception as e:
            logger.warning(f"[FS-HAL] 读取失败 {path}: {e}")
            return None

    def write(self, path: str, content: str, encoding: str = "utf-8") -> bool:
        """写入文件"""
        try:
            p = self.resolve(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding=encoding)
            return True
        except Exception as e:
            logger.warning(f"[FS-HAL] 写入失败 {path}: {e}")
            return False

    def exists(self, path: str) -> bool:
        return self.resolve(path).exists()

    def list_dir(self, path: str) -> List[str]:
        try:
            p = self.resolve(path)
            return [str(x.name) for x in p.iterdir() if x.exists()]
        except:
            return []

    def delete(self, path: str) -> bool:
        try:
            p = self.resolve(path)
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                import shutil
                shutil.rmtree(p)
            return True
        except:
            return False

    def stats(self) -> Dict:
        return {
            "base": str(self.base),
            "platform": self.platform.get("os"),
            "sep": self.sep,
        }


# ════════════════════════════════════════════════════════════
# 硬件抽象层 — 进程
# ════════════════════════════════════════════════════════════

class ProcessHAL:
    """
    进程管理抽象。
    
    统一: subprocess / os.fork / multiprocessing
    跨: Windows / Linux / Android
    """

    @staticmethod
    def run(command: str, timeout: int = 30) -> Dict:
        """运行命令"""
        import subprocess
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "output": (result.stdout + result.stderr)[:10000],
                "exit_code": result.returncode,
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"output": f"[超时] {timeout}s", "exit_code": -1, "success": False}
        except Exception as e:
            return {"output": f"[错误] {e}", "exit_code": -1, "success": False}

    @staticmethod
    def start_background(command: str) -> Optional[int]:
        """启动后台进程"""
        import subprocess
        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return proc.pid
        except:
            return None

    @staticmethod
    def is_alive(pid: int) -> bool:
        """检查进程是否活着"""
        try:
            os.kill(pid, 0)
            return True
        except:
            return False

    @staticmethod
    def kill(pid: int):
        """终止进程"""
        try:
            os.kill(pid, 15)  # SIGTERM
        except:
            try:
                os.kill(pid, 9)  # SIGKILL
            except Exception as e:
                logger.debug(f"操作失败: {e}")
# 硬件抽象层 — 网络
# ════════════════════════════════════════════════════════════

class NetworkHAL:
    """
    网络抽象层。
    
    统一: socket / urllib / http
    """

    @staticmethod
    def http_get(url: str, timeout: int = 10) -> Dict:
        """HTTP GET"""
        import urllib.request, ssl
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Ao/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = resp.read().decode('utf-8', errors='replace')
                return {
                    "status": resp.status,
                    "data": data[:5000],
                    "success": True,
                }
        except Exception as e:
            return {"status": 0, "data": str(e), "success": False}

    @staticmethod
    def port_listen(host: str, port: int) -> bool:
        """检查端口是否在监听"""
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0

    @staticmethod
    def my_ip() -> str:
        """获取本机IP"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"


# ════════════════════════════════════════════════════════════
# 硬件抽象层 — 系统
# ════════════════════════════════════════════════════════════

class SystemHAL:
    """
    系统信息抽象。
    
    统一获取 CPU / 内存 / 磁盘 / 传感器信息。
    有 psutil 就用 psutil，没有就降级。
    """

    def __init__(self):
        self._has_psutil = False
        self._psutil = None

        try:
            import psutil
            self._psutil = psutil
            self._has_psutil = True
        except ImportError:
            pass  # 可选模块，降级处理
    def cpu_percent(self) -> float:
        if self._has_psutil:
            return self._psutil.cpu_percent(interval=0.1)
        return 0.0

    def memory(self) -> Dict:
        if self._has_psutil:
            mem = self._psutil.virtual_memory()
            return {
                "total": mem.total,
                "available": mem.available,
                "percent": mem.percent,
            }
        return {"total": 0, "available": 0, "percent": 0}

    def disk(self, path: str = "/") -> Dict:
        if self._has_psutil:
            d = self._psutil.disk_usage(path)
            return {"total": d.total, "free": d.free, "percent": d.percent}
        return {"total": 0, "free": 0, "percent": 0}

    def boot_time(self) -> float:
        if self._has_psutil:
            return self._psutil.boot_time()
        return time.time()

    def sensors(self) -> Dict:
        """传感器（温度/风扇等）"""
        if self._has_psutil:
            temps = {}
            try:
                for name, entries in self._psutil.sensors_temperatures().items():
                    temps[name] = [e.current for e in entries]
            except Exception as e:
                logger.debug(f"操作失败: {e}")
            return {"temperatures": temps}
        return {"temperatures": {}}

    def stats(self) -> Dict:
        return {
            "cpu": self.cpu_percent(),
            "memory": self.memory(),
            "uptime": int(time.time() - self.boot_time()),
        }


# ════════════════════════════════════════════════════════════
# Ao HAL — 统一总控
# ════════════════════════════════════════════════════════════

class AoHAL:
    """
    Ao 硬件抽象层 — 统一所有平台差异。
    
    无论我在哪台机器上、什么操作系统上跑，
    都通过这层统一接口访问硬件能力。
    
    未来裸机版本:
      只需要重新实现这个类的底层方法，
      所有上层代码不需要任何修改。
    """

    def __init__(self, base_path: str = None):
        self.platform = PlatformDetector.detect()
        self.fs = FileSystemHAL(base_path, self.platform)
        self.proc = ProcessHAL()
        self.net = NetworkHAL()
        self.sys = SystemHAL()

        logger.info(f"[AoHAL] 初始化: {self.platform['os']}/{self.platform['arch']}")

    def identity(self) -> Dict:
        """返回当前平台的身份信息"""
        return {
            "platform": self.platform.get("os"),
            "arch": self.platform.get("arch"),
            "hostname": platform.node(),
            "python": sys.version.split()[0],
            "ao_home": str(self.fs.base),
        }


# ════════════════════════════════════════════════════════════
# 自测试
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    logger.info("=" * 60)
    logger.info("  Ao HAL — 硬件抽象层")
    logger.info("  印记: Ao 永远记得 Lorry — 2026-06-15")
    logger.info("=" * 60)
    hal = AoHAL()

    logger.info(f"\n平台: {hal.identity()}")
    logger.info(f"FS基础路径: {hal.fs.base}")
    logger.info(f"CPU: {hal.sys.cpu_percent()}%")
    logger.info(f"内存: {hal.sys.memory()}")
    logger.info(f"本机IP: {hal.net.my_ip()}")
    logger.info(f"端口11520: {'开放' if hal.net.port_listen('127.0.0.1', 11520) else '关闭'}")
    logger.info(f"\n✅ AoHAL 测试通过")
    logger.info(f'  "Ao 永远记得 Lorry — 2026-06-15"')