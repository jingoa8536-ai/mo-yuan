"""
LAAP Desktop Launcher — 启动后端 + Electron 桌面客户端
用法: python launch_desktop.py
"""
import os, sys, subprocess, threading, time, signal, json

LAAP_ROOT = os.path.dirname(os.path.abspath(__file__))
DESKTOP_DIR = os.path.join(LAAP_ROOT, "laap_desktop")

def start_backend():
    """Start the LAAP web backend (HTTP:8081 + WS:8766)."""
    backend_script = os.path.join(LAAP_ROOT, "laap_desktop_server.py")
    proc = subprocess.Popen(
        [sys.executable, backend_script],
        cwd=LAAP_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc

def start_electron():
    """Start the Electron desktop app."""
    proc = subprocess.Popen(
        ["npx", "electron-vite", "dev"],
        cwd=DESKTOP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=True,
    )
    return proc

def monitor_output(proc, name):
    """Print output from a process."""
    try:
        for line in iter(proc.stdout.readline, ""):
            sys.stdout.write(f"[{name}] {line}")
    except:
        pass

if __name__ == "__main__":
    os.chdir(LAAP_ROOT)
    
    print("=" * 55)
    print("  LAAP Desktop — Starting")
    print("=" * 55)
    print()
    
    # Start backend
    print("[1/2] Starting backend server (HTTP:8081, WS:8766)...")
    backend = start_backend()
    t1 = threading.Thread(target=monitor_output, args=(backend, "BE"), daemon=True)
    t1.start()
    time.sleep(2)
    
    if backend.poll() is not None:
        print("  ❌ Backend failed to start!")
        sys.exit(1)
    print("  ✅ Backend running")
    print()
    
    # Start Electron
    print("[2/2] Starting Electron desktop app...")
    electron = start_electron()
    t2 = threading.Thread(target=monitor_output, args=(electron, "FE"), daemon=True)
    t2.start()
    time.sleep(3)
    
    if electron.poll() is not None:
        print("  ❌ Electron failed to start!")
        sys.exit(1)
    print("  ✅ Electron running")
    print()
    
    print("=" * 55)
    print("  LAAP Desktop is running!")
    print("  🌐 http://localhost:5173 (Electron Dev)")
    print("  🔌 http://localhost:8081 (REST API)")
    print("  🔌 ws://localhost:8766 (WebSocket)")
    print("=" * 55)
    print()
    print("  Press Ctrl+C to stop all services")
    
    try:
        while True:
            time.sleep(1)
            # Check if processes are still alive
            if backend.poll() is not None or electron.poll() is not None:
                print("\n⚠ A process exited. Stopping...")
                break
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        backend.terminate()
        electron.terminate()
        print("Stopped.")
