#!/usr/bin/env python
"""
arisocr — Aris OCR 命令行工具
用法:
  arisocr <图片路径>              OCR 单张图片
  arisocr <图片路径> --json       输出 JSON 格式
  arisocr --clip                  OCR 剪贴板中的图片
  arisocr --watch                监听剪贴板，自动 OCR
  arisocr --server start         启动微服务
  arisocr --server stop          停止微服务
  arisocr --server status        查看微服务状态
"""
import sys, os, json, subprocess, argparse, time

MICRO_URL = "http://127.0.0.1:18923"
MICRO_PID_FILE = os.path.expanduser("~/.aris_vision_pid")
MICRO_SCRIPT = os.path.expanduser(r"D:\LAAP\aris_brain\vision_microservice.py")
MICRO_PYTHON = r"C:\Python313\python.exe"


def micro_running():
    """检查微服务是否在运行"""
    try:
        import urllib.request
        req = urllib.request.Request(f"{MICRO_URL}/health", data=b'{}', method='POST')
        req.add_header('Content-Type', 'application/json')
        resp = urllib.request.urlopen(req, timeout=3)
        return json.loads(resp.read())
    except:
        return None


def ocr_image(path):
    """调用微服务 OCR 一张图片"""
    import urllib.request
    data = json.dumps({"path": path}).encode()
    req = urllib.request.Request(f"{MICRO_URL}/ocr_enhanced", data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    resp = urllib.request.urlopen(req, timeout=180)
    return json.loads(resp.read())


def start_server():
    if micro_running():
        print("✅ 微服务已在运行")
        return
    proc = subprocess.Popen(
        [MICRO_PYTHON, MICRO_SCRIPT],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    with open(MICRO_PID_FILE, 'w') as f:
        f.write(str(proc.pid))
    # 等待启动
    for _ in range(10):
        if micro_running():
            print(f"✅ 微服务已启动 (PID: {proc.pid})")
            return
        time.sleep(0.5)
    print("❌ 微服务启动超时")


def stop_server():
    if os.path.exists(MICRO_PID_FILE):
        with open(MICRO_PID_FILE) as f:
            pid = f.read().strip()
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        os.unlink(MICRO_PID_FILE)
        print("✅ 微服务已停止")
    else:
        # 尝试查端口
        r = subprocess.run(
            'netstat -ano | findstr "18923"',
            capture_output=True, text=True, shell=True
        )
        for line in r.stdout.strip().split('\n'):
            parts = line.strip().split()
            if parts:
                pid = parts[-1]
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        print("✅ 已清理端口 18923")


def main():
    parser = argparse.ArgumentParser(description="Aris OCR 命令行工具")
    parser.add_argument("path", nargs="?", help="图片路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--clip", action="store_true", help="OCR 剪贴板图片")
    parser.add_argument("--watch", action="store_true", help="监听剪贴板")
    parser.add_argument("--server", choices=["start", "stop", "status"], help="管理微服务")
    
    args = parser.parse_args()
    
    # 服务管理
    if args.server:
        if args.server == "start":
            start_server()
        elif args.server == "stop":
            stop_server()
        elif args.server == "status":
            status = micro_running()
            if status:
                print(f"✅ 微服务运行中: {json.dumps(status, ensure_ascii=False)}")
            else:
                print("❌ 微服务未运行 (执行 'arisocr --server start' 启动)")
        return
    
    # 确保微服务在运行
    if not micro_running():
        print("⚠️ 微服务未运行，正在启动...")
        start_server()
        if not micro_running():
            print("❌ 无法启动微服务")
            sys.exit(1)
    
    # OCR 剪贴板
    if args.clip:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img is None:
                print("❌ 剪贴板中无图片")
                return
            tmp = os.path.expanduser("~/.aris_clip_ocr.png")
            img.save(tmp)
            args.path = tmp
        except Exception as e:
            print(f"❌ 读取剪贴板失败: {e}")
            return
    
    # OCR 监听模式
    if args.watch:
        print("👁️ 监听剪贴板中... (Ctrl+C 退出)")
        last_hash = None
        try:
            while True:
                from PIL import ImageGrab
                import hashlib
                img = ImageGrab.grabclipboard()
                if img is not None:
                    data = img.tobytes()
                    h = hashlib.md5(data).hexdigest()
                    if h != last_hash:
                        last_hash = h
                        tmp = os.path.expanduser(f"~/.aris_watch_{int(time.time())}.png")
                        img.save(tmp)
                        print(f"\n📸 检测到新图片，OCR中...")
                        result = ocr_image(tmp)
                        if isinstance(result, dict) and "text" in result:
                            print(result["text"])
                        os.unlink(tmp)
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 停止监听")
        return
    
    # OCR 单张图片
    if not args.path:
        parser.print_help()
        return
    
    if not os.path.exists(args.path):
        print(f"❌ 文件不存在: {args.path}")
        sys.exit(1)
    
    print(f"📖 OCR中: {os.path.basename(args.path)}")
    result = ocr_image(args.path)
    
    if isinstance(result, dict) and "error" in result:
        print(f"❌ OCR 失败: {result['error'][:200]}")
        sys.exit(1)
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif isinstance(result, dict) and "text" in result:
        print(result["text"])
        if result.get("total_items", 0) > 0:
            print(f"\n--- {result['total_items']} 条文本 ---")


if __name__ == "__main__":
    main()
