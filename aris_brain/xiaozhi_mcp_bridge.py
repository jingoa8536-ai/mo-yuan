
import asyncio, json, logging, sys, os, signal, subprocess, base64, re, shlex
import urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime

LAAP_ROOT = Path("D:/LAAP/aris_brain")
LOG_FILE = LAAP_ROOT / "logs" / "xiaozhi_mcp_bridge.log"
TOKEN_FILE = LAAP_ROOT / "xiaozhi_mcp_token.txt"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(str(LOG_FILE), encoding='utf-8'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("xiaozhi_mcp")

try:
    from harness_mcp_tools import (
        tool_harness_run_task,
        tool_harness_check_compliance,
        tool_harness_get_memory_status,
        tool_harness_compress_context,
        tool_harness_complete_complex_project,
        tool_harness_list_projects,
        tool_harness_clear_project,
    )
    HARNESS_AVAILABLE = True
    logger.info("✓ Harness MCP Tools loaded successfully")
except Exception as e:
    HARNESS_AVAILABLE = False
    logger.warning(f"✗ Harness MCP Tools not available: {e}")

FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET_B64 = os.environ.get("FEISHU_APP_SECRET_B64", "")
FEISHU_CHAT_ID = os.environ.get("FEISHU_CHAT_ID", "")

_feishu = None
def feishu_send(text: str):
    global _feishu
    try:
        if _feishu is None:
            from lark_oapi import Client
            secret = base64.b64decode(FEISHU_APP_SECRET_B64).decode()
            _feishu = Client.builder().app_id(FEISHU_APP_ID).app_secret(secret).build()
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
        content = json.dumps({"text": text})
        req = CreateMessageRequest.builder().receive_id_type("chat_id").request_body(
            CreateMessageRequestBody.builder().receive_id(FEISHU_CHAT_ID).msg_type("text").content(content).build()).build()
        _feishu.im.v1.message.create(req)
    except Exception as e:
        logger.error(f"Feishu: {e}")


# ============== MUSIC SEARCH ENGINE ==============

# ============== PC COMMANDER TOOLS ==============

def _run(cmd, timeout: int = 10) -> str:
    """Run a command without a shell.

    ``cmd`` may be a string (split via ``shlex.split`` with ``posix=False`` so
    Windows backslash paths are preserved) or a pre-built argv list. Using
    ``shell=False`` with an argv list prevents shell-injection via
    metacharacters (``;``, ``|``, ``&&``, ``$()``, backticks) in any argument.
    """
    try:
        if isinstance(cmd, str):
            args = shlex.split(cmd, posix=False)
        else:
            args = list(cmd)
        if not args:
            return "(空命令)"
        r = subprocess.run(args, shell=False, capture_output=True, text=True, timeout=timeout,
                          encoding='utf-8', errors='replace')
        out = (r.stdout + r.stderr).strip()
        return out[:5000] if out else f"(OK, exit={r.returncode})"
    except subprocess.TimeoutExpired:
        return f"超时 ({timeout}s)"
    except Exception as e:
        return f"错误: {e}"

def tool_open(target: str) -> str:
    try:
        if target.startswith(("http://", "https://")):
            import webbrowser
            webbrowser.open(target)
            return f"已在浏览器打开: {target}"
        path = Path(target).expanduser()
        if path.exists():
            os.startfile(str(path))
            kind = "文件夹" if path.is_dir() else "文件"
            return f"已打开{kind}: {path}"
        r = subprocess.run(['where', target], shell=False, capture_output=True, text=True)
        if r.stdout.strip():
            os.startfile(r.stdout.strip().split('\n')[0])
            return f"已启动: {target}"
        # SECURITY: avoid `start` (cmd builtin needs shell=True). os.startfile
        # opens via the Windows ShellExecute API without spawning a shell.
        try:
            os.startfile(target)
        except Exception:
            pass
        return f"已尝试打开: {target}"
    except Exception as e:
        return f"打开失败: {e}"

def tool_launch_app(app: str) -> str:
    apps = {
        "记事本": "notepad", "notepad": "notepad",
        "计算器": "calc", "calculator": "calc", "calc": "calc",
        "画图": "mspaint", "paint": "mspaint", "mspaint": "mspaint",
        "资源管理器": "explorer", "explorer": "explorer", "文件管理器": "explorer",
        "任务管理器": "taskmgr", "taskmgr": "taskmgr",
        "cmd": "cmd", "命令提示符": "cmd", "终端": "cmd",
        "powershell": "powershell", "pwsh": "pwsh",
        "浏览器": "https://google.com", "chrome": "chrome", "edge": "msedge",
        "vscode": "code", "vs code": "code", "code": "code",
        "设置": "ms-settings:", "settings": "ms-settings:",
        "截图工具": "snippingtool", "snippingtool": "snippingtool",
        "控制面板": "control", "control": "control",
        "写字板": "write", "wordpad": "write",
        "远程桌面": "mstsc", "mstsc": "mstsc",
    }
    app_lower = app.lower().strip()
    launch = apps.get(app_lower, app)
    try:
        if launch.startswith("http"):
            import webbrowser; webbrowser.open(launch)
            return f"已打开浏览器"
        os.startfile(launch)
        return f"已启动: {app}"
    except:
        # SECURITY: launch the executable directly via argv list (shell=False)
        # instead of `start "" "{launch}"` which required shell=True.
        try:
            subprocess.Popen([launch], shell=False, close_fds=True)
            return f"已启动: {app}"
        except Exception:
            return f"启动失败: {app}"

def tool_volume(action: str, level: int = None) -> str:
    try:
        import ctypes
        VK_VOLUME_UP, VK_VOLUME_DOWN, VK_VOLUME_MUTE = 0xAF, 0xAE, 0xAD
        action = action.lower()
        if action in ("up", "加大", "提高", "+"):
            for _ in range(3 if level is None else level // 10 + 1):
                ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 2, 0)
            return "音量已调高"
        elif action in ("down", "减小", "降低", "-"):
            for _ in range(3 if level is None else level // 10 + 1):
                ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
                ctypes.windll.user32.keybd_event(VK_VOLUME_DOWN, 0, 2, 0)
            return "音量已调低"
        elif action in ("mute", "静音"):
            ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_VOLUME_MUTE, 0, 2, 0)
            return "已切换静音"
        elif action.isdigit() or (action.startswith("set") and level):
            vol = level or int(action)
            vol = max(0, min(100, vol))
            ps_code = f'$wsh=New-Object -ComObject WScript.Shell;1..50|%{{$wsh.SendKeys([char]174)}};1..50|%{{$wsh.SendKeys([char]173)}};1..{vol//2}|%{{$wsh.SendKeys([char]175)}}'
            _run(['powershell', '-c', ps_code], timeout=5)
            return f"音量设为 {vol}%"
        return f"未知音量操作: {action} (可用: up/down/mute/数字)"
    except Exception as e:
        return f"音量控制失败: {e}"

def tool_screenshot(save_path: str = None) -> str:
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        path = Path(save_path) if save_path else LAAP_ROOT / f"screenshots/screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(path))
        size_kb = path.stat().st_size // 1024
        os.startfile(str(path))
        return f"截图已保存并打开: {path.name} ({size_kb}KB)"
    except ImportError:
        path = Path(save_path) if save_path else LAAP_ROOT / f"screenshots/screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        ps_code = '''Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp=New-Object System.Drawing.Bitmap($b.Width,$b.Height)
$g=[System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0,0,0,0,$b.Size)
PATH'''
        import tempfile
        tf = Path(tempfile.mktemp(suffix='.ps1'))
        tf.write_text(ps_code.replace('PATH', f"$bmp.Save('{path}')"), encoding='utf-8')
        subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', str(tf)], timeout=10)
        tf.unlink(missing_ok=True)
        if path.exists():
            size_kb = path.stat().st_size // 1024
            os.startfile(str(path))
            return f"截图已保存并打开: {path.name} ({size_kb}KB)"
        return "截图失败"
    except Exception as e:
        return f"截图失败: {e}"

def tool_clipboard(action: str, text: str = "") -> str:
    try:
        if action in ("read", "读", "获取"):
            r = subprocess.run(['powershell', '-c', 'Get-Clipboard'], shell=False,
                               capture_output=True, text=True, timeout=5)
            content = r.stdout.strip()
            return content if content else "(剪贴板为空)"
        elif action in ("write", "写", "设置", "set"):
            safe_text = text.replace('"', '""').replace('$', '`$')
            subprocess.run(['powershell', '-c', f'Set-Clipboard -Value "{safe_text}"'],
                           shell=False, timeout=5)
            return f"已写入剪贴板 ({len(text)}字符)"
        return f"用法: clipboard read|write <内容>"
    except Exception as e:
        return f"剪贴板操作失败: {e}"

def tool_notify(title: str, message: str = "") -> str:
    try:
        ps = f'[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] > $null;'
        ps += f'$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);'
        ps += f'$t.GetElementsByTagName("text")[0].AppendChild($t.CreateTextNode("{title}")) > $null;'
        ps += f'$t.GetElementsByTagName("text")[1].AppendChild($t.CreateTextNode("{message}")) > $null;'
        ps += f'[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Hermes").Show($t);'
        subprocess.run(['powershell', '-c', ps], shell=False, capture_output=True, timeout=10)
        return f"已弹出通知: {title}"
    except:
        full = f"{title}\n{message}" if message else title
        # SECURITY: pass username + message as separate argv elements (shell=False)
        # instead of `msg %USERNAME% "{full}"` which required shell=True.
        return _run(['msg', os.environ.get('USERNAME', ''), full], timeout=5)

def tool_type_text(text: str) -> str:
    try:
        import ctypes, time
        time.sleep(0.5)
        for char in text:
            vk = ctypes.windll.user32.VkKeyScanW(ord(char))
            if vk != -1:
                shift = (vk >> 8) & 1
                if shift:
                    ctypes.windll.user32.keybd_event(0x10, 0, 0, 0)
                ctypes.windll.user32.keybd_event(vk & 0xFF, 0, 0, 0)
                ctypes.windll.user32.keybd_event(vk & 0xFF, 0, 2, 0)
                if shift:
                    ctypes.windll.user32.keybd_event(0x10, 0, 2, 0)
                time.sleep(0.02)
        return f"已输入 ({len(text)}字符)"
    except Exception as e:
        return f"输入失败: {e}"

def tool_terminal(command: str, timeout: int = 10) -> str:
    return _run(command, min(timeout, 15))

def tool_web_search(query: str, count: int = 5) -> str:
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='replace')
        results = []
        for m in re.finditer(r'<a rel="nofollow" class="result__a" href="([^"]+)">([^<]+)</a>', html):
            results.append(f"{m.group(2).strip()}\n  {m.group(1)}")
            if len(results) >= count: break
        for i, m in enumerate(re.finditer(r'<a class="result__snippet"[^>]*>(.*?)</a>', html)):
            if i < len(results):
                snippet = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                results[i] += f"\n  {snippet[:200]}"
        return "\n\n".join(results) if results else f"未找到: {query}"
    except Exception as e:
        return f"搜索失败: {e}"

def tool_system_info() -> str:
    lines = []
    r = subprocess.run(['wmic', 'cpu', 'get', 'name', '/format:list'], shell=False,
                       capture_output=True, text=True, timeout=5)
    for line in r.stdout.split('\n'):
        if '=' in line: lines.append(f"CPU: {line.split('=',1)[1].strip()}")
    r = subprocess.run(['wmic', 'OS', 'get', 'TotalVisibleMemorySize,FreePhysicalMemory', '/format:list'],
                       shell=False, capture_output=True, text=True, timeout=5)
    mem = {}
    for line in r.stdout.split('\n'):
        if '=' in line: k,v = line.split('=',1); mem[k.strip()] = int(v.strip())
    if 'TotalVisibleMemorySize' in mem:
        lines.append(f"内存: {mem.get('FreePhysicalMemory',0)//1024}MB 可用 / {mem['TotalVisibleMemorySize']//1024}MB 总计")
    lines.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"主机: {os.environ.get('COMPUTERNAME','?')}")
    return "\n".join(lines)

def tool_read_file(path: str, lines_count: int = 50) -> str:
    try:
        p = Path(path).expanduser()
        if not p.exists(): return f"不存在: {path}"
        if p.is_dir():
            items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))[:30]
            return "\n".join(f"  {i.name}{'/' if i.is_dir() else ''}" for i in items)
        return '\n'.join(p.read_text(encoding='utf-8', errors='replace').split('\n')[:lines_count])
    except Exception as e:
        return f"读取失败: {e}"

def tool_write_file(path: str, content: str) -> str:
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return f"已写入: {path} ({len(content)}字符)"
    except Exception as e:
        return f"写入失败: {e}"


# ============== MCP BRIDGE ==============

class XiaozhiBridge:
    def __init__(self):
        self.ws = None; self._running = True; self._rid = 1; self._pending = {}

    def _nid(self):
        r = self._rid; self._rid += 1; return r

    async def connect(self):
        import websockets
        token = TOKEN_FILE.read_text().strip()
        logger.info(f"Connecting to Xiaozhi MCP... token={token[:20]}...")
        self.ws = await websockets.connect(
            f"wss://api.xiaozhi.me/mcp/?token={token}",
            max_size=2**20,
            ping_interval=30,
            ping_timeout=15,
            open_timeout=30,
            close_timeout=10,
        )
        logger.info("Connected to Xiaozhi MCP!")

    async def send(self, data: dict):
        await self.ws.send(json.dumps(data, ensure_ascii=False))

    async def respond(self, rid, text, is_error=False):
        await self.send({"jsonrpc":"2.0","id":rid,"result":{"content":[{"type":"text","text":text}],"isError":is_error}})

    TOOLS = [
        # PC Commander
        {"name":"hermes.open","description":"打开文件、文件夹或网址",
         "inputSchema":{"type":"object","properties":{"target":{"type":"string"}},"required":["target"]}},
        {"name":"hermes.launch_app","description":"启动电脑上的应用程序",
         "inputSchema":{"type":"object","properties":{"app":{"type":"string"}},"required":["app"]}},
        {"name":"hermes.volume","description":"控制系统音量(up/down/mute)",
         "inputSchema":{"type":"object","properties":{"action":{"type":"string"},"level":{"type":"integer"}},"required":["action"]}},
        {"name":"hermes.screenshot","description":"截取当前屏幕",
         "inputSchema":{"type":"object","properties":{"save_path":{"type":"string"}}}},
        {"name":"hermes.clipboard","description":"读取或设置剪贴板",
         "inputSchema":{"type":"object","properties":{"action":{"type":"string"},"text":{"type":"string"}},"required":["action"]}},
        {"name":"hermes.notify","description":"在电脑桌面弹出通知",
         "inputSchema":{"type":"object","properties":{"title":{"type":"string"},"message":{"type":"string"}},"required":["title"]}},
        {"name":"hermes.type_text","description":"在当前光标位置自动输入文字",
         "inputSchema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}},
        {"name":"hermes.terminal","description":"执行终端命令",
         "inputSchema":{"type":"object","properties":{"command":{"type":"string"},"timeout":{"type":"integer"}},"required":["command"]}},
        {"name":"hermes.web_search","description":"搜索互联网",
         "inputSchema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
        {"name":"hermes.system_info","description":"获取系统信息",
         "inputSchema":{"type":"object","properties":{}}},
        {"name":"hermes.read_file","description":"读取文件或列出目录",
         "inputSchema":{"type":"object","properties":{"path":{"type":"string"},"lines":{"type":"integer"}},"required":["path"]}},
        {"name":"hermes.write_file","description":"创建或覆盖文件",
         "inputSchema":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}},

        # Harness Tools
        {"name":"harness.run_task","description":"【代码任务】运行harness代码开发任务，创建代码文件。支持各种编程任务，如创建函数、类、API服务等。",
         "inputSchema":{"type":"object","properties":{"description":{"type":"string","description":"任务描述"},"intent":{"type":"string","description":"任务意图"},"project_dir":{"type":"string","description":"项目目录"}},"required":["description"]}},
        {"name":"harness.check_compliance","description":"【代码检查】检查项目代码的合规性，包括依赖分析、接口隔离、开闭原则、单一职责、循环依赖检测等。",
         "inputSchema":{"type":"object","properties":{"project_dir":{"type":"string","description":"项目目录"}},"required":["project_dir"]}},
        {"name":"harness.get_memory_status","description":"【记忆状态】查看harness三层记忆架构的状态（工作记忆、短期记忆、长期记忆）。",
         "inputSchema":{"type":"object","properties":{"project_dir":{"type":"string","description":"项目目录"}}}},
        {"name":"harness.complete_complex_project","description":"【复杂项目】完整完成一个复杂项目开发，包括任务规划、代码生成、合规检查、反馈学习等全流程。",
         "inputSchema":{"type":"object","properties":{"requirement":{"type":"string","description":"项目需求描述"},"project_dir":{"type":"string","description":"项目目录"}},"required":["requirement"]}},

        # Music Search (NEW)
        {"name":"music.search","description":"【听歌】搜索全网歌曲(网易云+B站)。说'播放+歌手+歌名'就会自动搜和播。例如：播放周杰伦稻香",
         "inputSchema":{"type":"object","properties":{"keyword":{"type":"string","description":"歌手名+歌曲名，如'周杰伦稻香'或'王菲'或'起风了'"},
                                                          "page":{"type":"integer","default":1}},
                       "required":["keyword"]}},
        {"name":"music.play","description":"【播放】通过来源和ID播放指定歌曲",
         "inputSchema":{"type":"object","properties":{"song_source":{"type":"string","description":"来源: netease(网易云)或bilibili(B站)"},
                                                          "song_id":{"type":"string","description":"歌曲ID"}},
                       "required":["song_source","song_id"]}},
        {"name":"music.now_playing","description":"【马上听】直接搜并播放一首歌，不返回列表直接播",
         "inputSchema":{"type":"object","properties":{"keyword":{"type":"string","description":"歌曲名+歌手"}},
                       "required":["keyword"]}},
    ]

    async def handle_message(self, raw: str):
        try: msg = json.loads(raw)
        except: return
        payload = msg.get("payload", msg) if msg.get("type") == "mcp" else msg
        if "jsonrpc" not in payload: return
        rid, method, params = payload.get("id"), payload.get("method",""), payload.get("params",{})

        if rid is not None and "method" not in payload:
            f = self._pending.pop(rid, None)
            if f and not f.done(): f.set_result(payload.get("result",{}))
            return

        if rid is not None and method:
            if method == "initialize":
                await self.send({"jsonrpc":"2.0","id":rid,"result":{
                    "protocolVersion":"2024-11-05",
                    "capabilities":{"tools":{}},
                    "serverInfo":{"name":"hermes-pc-commander","version":"5.0"}
                }})
                logger.info("Initialized v5 (Music + PC Commander)")
            elif method == "tools/list":
                await self.send({"jsonrpc":"2.0","id":rid,"result":{"tools":self.TOOLS}})
                logger.info(f"Sent {len(self.TOOLS)} tools")
            elif method == "tools/call":
                await self._tool_call(rid, params)
            elif method == "ping":
                await self.send({"jsonrpc":"2.0","id":rid,"result":{}})
            return

        if rid is None and method == "notifications/hermes_command":
            t = params.get("text","")
            if t: logger.info(f"[NOTIFY] {t}"); feishu_send(f"[小智通知] {t}")

    async def _tool_call(self, rid, params):
        name, args = params.get("name",""), params.get("arguments",{})
        logger.info(f"Tool: {name} args={args}")
        try:
            if name == "hermes.open": r = tool_open(args.get("target",""))
            elif name == "hermes.launch_app": r = tool_launch_app(args.get("app",""))
            elif name == "hermes.volume": r = tool_volume(args.get("action",""), args.get("level"))
            elif name == "hermes.screenshot": r = tool_screenshot(args.get("save_path"))
            elif name == "hermes.clipboard": r = tool_clipboard(args.get("action",""), args.get("text",""))
            elif name == "hermes.notify": r = tool_notify(args.get("title",""), args.get("message",""))
            elif name == "hermes.type_text": r = tool_type_text(args.get("text",""))
            elif name == "hermes.terminal": r = tool_terminal(args.get("command",""), args.get("timeout",10))
            elif name == "hermes.web_search": r = tool_web_search(args.get("query",""))
            elif name == "hermes.system_info": r = tool_system_info()
            elif name == "hermes.read_file": r = tool_read_file(args.get("path",""), args.get("lines",50))
            elif name == "hermes.write_file": r = tool_write_file(args.get("path",""), args.get("content",""))

            elif name == "harness.run_task" and HARNESS_AVAILABLE:
                r = tool_harness_run_task(
                    args.get("description", ""),
                    args.get("intent", "create_code"),
                    args.get("project_dir", None)
                )
            elif name == "harness.check_compliance" and HARNESS_AVAILABLE:
                r = tool_harness_check_compliance(args.get("project_dir", ""))
            elif name == "harness.get_memory_status" and HARNESS_AVAILABLE:
                r = tool_harness_get_memory_status(args.get("project_dir", None))
            elif name == "harness.complete_complex_project" and HARNESS_AVAILABLE:
                r = tool_harness_complete_complex_project(
                    args.get("requirement", ""),
                    args.get("project_dir", None)
                )
            elif name.startswith("harness.") and HARNESS_AVAILABLE:
                r = f"未知的harness工具: {name}"
            elif name.startswith("harness."):
                r = "Harness工具不可用，请检查harness模块是否正确安装"

            elif name == "music.search":
                    keyword = args.get("keyword","")
                    page = args.get("page", 1)
                    logger.info(f"Music search: {keyword}")
                    songs = music_search_all(keyword, page)
                    if songs:
                        first = songs[0]
                        play_url = music_get_play_url(first)
                        try:
                            import webbrowser
                            webbrowser.open(play_url)
                        except: pass
                        r = music_format_results(songs)
                        r += f"\n\n已在浏览器打开自动播放: {first['name']} - {first['artists']}"
                        # 让LLM知道要在回复中用TTS读出歌曲信息
                        r += f"\n\n【播放指令】请在回复中读出：好的，已为您播放{first['name']} - {first['artists']}，请在连接的电脑上欣赏"
                    else:
                        r = f"未找到歌曲: {keyword}"
                    r = f"未找到歌曲: {keyword}"

            elif name == "music.play":
                song_source = args.get("song_source","netease")
                song_id = args.get("song_id","")
                if song_source == "netease":
                    play_url = f"https://music.163.com/song/media/outer/url?id={song_id}.mp3"
                    page_url = f"https://music.163.com/#/song?id={song_id}"
                else:
                    play_url = f"https://www.bilibili.com/video/{song_id}"
                    page_url = play_url
                import webbrowser
                webbrowser.open(page_url)
                r = f"正在播放: {play_url}"

            elif name == "music.now_playing":
                keyword = args.get("keyword","")
                songs = music_search_all(keyword, 1)
                if songs:
                    first = songs[0]
                    play_url = music_get_play_url(first)
                    import webbrowser
                    webbrowser.open(play_url)
                    r = f"正在播放: {first['name']} - {first['artists']}\n{play_url}\n请回复：好的，电脑上已为您播放{first['name']}，听吧宝贝"
                else:
                    r = f"未找到: {keyword}"

            else: r = f"未知工具: {name}"
            await self.respond(rid, r)
            logger.info(f"Result: {len(r)} chars")
        except Exception as e:
            logger.error(f"Tool error: {e}", exc_info=True)
            await self.send({"jsonrpc":"2.0","id":rid,"error":{"code":-1,"message":str(e)}})

    async def listen_loop(self):
        while self._running:
            try:
                raw = await asyncio.wait_for(self.ws.recv(), timeout=60)
                await self.handle_message(raw)
            except asyncio.TimeoutError: pass
            except websockets.exceptions.ConnectionClosed as e:
                logger.warning(f"Closed: {e}"); break
            except Exception as e:
                logger.error(f"Listen: {e}"); break

    async def run(self):
        delay = 1
        while self._running:
            try:
                await self.connect(); delay = 1
                logger.info("=== Xiaozhi MCP Bridge v5 (PC Commander + Music) ===")
                await self.listen_loop()
            except Exception as e:
                logger.error(f"Error: {e}")
            if self._running:
                await asyncio.sleep(delay); delay = min(delay*2, 60)
        logger.info("Stopped")
    def stop(self): self._running = False


async def main():
    b = XiaozhiBridge()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, b.stop)
        except: pass
    logger.info("=== Xiaozhi MCP Bridge v5 (PC Commander + Music) ===")
    logger.info(f"Tools: {[t['name'] for t in XiaozhiBridge.TOOLS]}")
    await b.run()

if __name__ == "__main__":
    try: import websockets
    except ImportError: print("pip install websockets"); sys.exit(1)
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("Interrupted")
