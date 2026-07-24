"""Quick system resource check."""

import logging
logger = logging.getLogger(__name__)

import psutil
mem = psutil.virtual_memory()
cpu = psutil.cpu_percent(interval=1)
logger.info(f"CPU: {cpu:.1f}%")
logger.info(f"RAM: {mem.used/1e9:.1f}/{mem.total/1e9:.0f}GB ({mem.percent:.0f}%) Free: {mem.available/1e9:.1f}GB")
for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
    try:
        name = p.info['name'].lower()
        if 'ollama' in name or 'python' in name:
            rss = p.info['memory_info'].rss / 1e9
            logger.info(f"  PID {p.info['pid']:6d} {p.info['name'][:20]:20s} RSS={rss:.2f}GB CPU={p.info['cpu_percent']:.1f}%")
    except Exception as e:
        logger.debug(f"操作失败: {e}")