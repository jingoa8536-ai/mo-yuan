"""
启动飞书桥 — 自动加载 Hermes config 的 DeepSeek key
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, yaml, subprocess

_DIR = os.path.dirname(os.path.abspath(__file__))

# 从 Hermes config 读 key
hermes_config = os.path.expanduser(
    r"~/AppData/Local/hermes/profiles/aris/config.yaml"
)
if os.path.exists(hermes_config):
    with open(hermes_config) as f:
        cfg = yaml.safe_load(f)
    key = cfg.get("providers", {}).get("deepseek", {}).get("api_key", "")
    model = cfg.get("default", "deepseek-chat")
    os.environ["DEEPSEEK_API_KEY"] = key
    os.environ["DEEPSEEK_MODEL"] = model
    logger.info(f"DeepSeek key loaded: sk-{key[:5]}...{key[-4:]}")
    logger.info(f"Model: {model}")
os.environ["ARIS_MODE"] = "llm"

# 启动桥
bridge_path = os.path.join(_DIR, "aris_feishu_bridge.py")
logger.info(f"启动 {bridge_path}...")
subprocess.run([sys.executable, bridge_path])
