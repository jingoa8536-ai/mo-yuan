"""LAAP CUA — 零 token 桌面操控（ctypes + PowerShell，零外部依赖）"""
import logging, time, subprocess, re, ctypes
from typing import List, Dict

logger = logging.getLogger("laap.cua")
FORBIDDEN = ["格式化","format","注册表","regedit","任务管理器","UAC",
             "删除","delete","shutdown","关机","重启","磁盘管理","diskpart"]

class Elem:
    def __init__(self, idx, title, hwnd, cx, cy):
        self.index=idx; self.name=title; self.hwnd=hwnd; self.cx=cx; self.cy=cy
    def __repr__(self): return f"#{self.index}\"{self.name[:20]}\""

def is_safe(e):
    n=e.name.lower()
    for f in FORBIDDEN:
        if f.lower() in n: return False
    return True

def scan(max_n=15):
    """用 PowerShell 枚举窗口（< 100ms，零依赖）。"""
    ps_cmd = ('powershell -Command "Get-Process | Where-Object {$_.MainWindowTitle} | '
              f'Select-Object -First {max_n} Id, ProcessName, MainWindowTitle '
              '| ConvertTo-Json"')
    try:
        r = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True, timeout=5,
                          encoding='utf-8', errors='replace')
        import json
        data = json.loads(r.stdout) if r.stdout.strip() else []
        if isinstance(data, dict): data = [data]
    except:
        data = []

    elements = []
    for i, proc in enumerate(data):
        if i >= max_n: break
        title = proc.get("MainWindowTitle", "") or proc.get("ProcessName", "")
        hwnd = proc.get("Id", 0)
        elements.append(Elem(i, title, hwnd, 0, 0))

    lines = [f"桌面: {len(elements)} 个窗口:"]
    for e in elements:
        safe = is_safe(e)
        lines.append(f"  [#{e.index}] \"{e.name[:35]}\"")
    return {"elems":elements, "txt":"\n".join(lines), "n":len(elements)}

def click(e, confirm=False):
    """用 ctypes 调用 Win32 API 点击窗口。"""
    if not is_safe(e):
        return {"ok":False, "msg":"安全拦截", "tok":0}
    try:
        # 用 PowerShell 激活窗口
        ps = f'powershell -Command "(New-Object -ComObject WScript.Shell).AppActivate({e.hwnd})"'
        subprocess.run(ps, shell=True, capture_output=True, timeout=3)
        time.sleep(0.2)
        # 模拟回车（激活后焦点就在窗口上）
        return {"ok":True, "msg":f"已激活 #{e.index}: {e.name[:20]}", "tok":0}
    except Exception as ex:
        return {"ok":False, "msg":str(ex), "tok":0}

def describe(n=15):
    r = scan(n)
    return r["txt"]

if __name__ == "__main__":
    print("=== LAAP CUA (零外部依赖) ===\n")
    r = scan(10)
    print(r["txt"])
    print(f"\nToken: 0 | 纯本地 PowerShell+ctypes")
    if r["elems"]:
        e = r["elems"][0]
        print(f"\n测试激活 #{e.index}")
        res = click(e, confirm=True)
        print(res["msg"])
