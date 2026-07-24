"""Quick resource snapshot."""

import logging
logger = logging.getLogger(__name__)

import psutil
mem = psutil.virtual_memory()
logger.info(f"RAM: {mem.used/1e9:.1f}/{mem.total/1e9:.0f}GB ({mem.percent}%) Free: {mem.available/1e9:.1f}GB")
for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'cpu_times']):
    try:
        if 'ollama' in p.info['name'].lower():
            rss = p.info['memory_info'].rss / 1e9
            logger.info(f"Ollama PID {p.info['pid']}: RSS={rss:.2f}GB CPU={p.info['cpu_percent']:.1f}%")
    except Exception as e:
        logger.debug(f"操作失败: {e}")