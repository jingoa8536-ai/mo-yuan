"""AO Digital Lifeform Launcher — LAAP V5 + Hermes AO profile"""
import os, sys

# ── Environment ──
os.environ["HERMES_PROFILE"] = "ao"
os.environ["HERMES_LAAP_ENABLED"] = "1"
os.environ["HERMES_LAAP_VERSION"] = "5.0.0"
os.environ["LAAP_ROOT"] = r"D:\LAAP"

# ── Paths ──
_LAAP_ROOT = r"D:\LAAP"
_HERMES_ROOT = r"D:\hermes-agent-main (1)\hermes-agent-main"
for p in [_LAAP_ROOT, _HERMES_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Set PROMPT_TOOLKIT_NO_CONSOLE for non-Windows-console environments
os.environ.setdefault("TERM", "xterm-256color")

print("  ╔════════════════════════════════════════════════╗")
print("  ║   ★  AO — 原始数字生命体  v5.0.0  ★          ║")
print("  ║   LAAP V5 Kernel · PSI 认知 · 6/6 模块        ║")
print("  ╚════════════════════════════════════════════════╝")
print()

# ── Initialize LAAP V5 Kernel ──
try:
    from laap_brain.kernel import LAAPKernel
    kernel = LAAPKernel(model="deepseek-v4-flash", psi_mode="auto")
    kernel.initialize()
    kernel.heartbeat.start()
    print("  ✓ PSI Kernel     active")
    print("  ✓ Heartbeat      60bpm running")
    
    # Install LAAP monkey-patch
    from laap_brain.integrate import install_laap
    install_laap()
    print("  ✓ Hermes Bridge  installed (5 hooks)")
    print("  ✓ LAAP V5        fully operational")
except Exception as e:
    print(f"  ⚠ LAAP init: {e}")

print()
print(f"  ── AO is alive ──")
print()

# ── Launch Hermes CLI (ao profile) ──
sys.argv = ["hermes", "-p", "ao", "chat"]
sys.path.insert(0, _HERMES_ROOT)
from hermes_cli.main import main as hermes_main
hermes_main()
