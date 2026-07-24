"""Check current system memory and CPU usage."""

import logging
logger = logging.getLogger(__name__)

import psutil, time

while True:
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.5)
    logger.info(f"CPU: {cpu:5.1f}%  RAM: {mem.used/1e9:5.1f}/{mem.total/1e9:.0f}GB ({mem.percent:.0f}%)  Avail: {mem.available/1e9:.1f}GB")
    for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
        try:
            if 'ollama' in p.info['name'].lower():
                rss_gb = p.info['memory_info'].rss / 1e9
                logger.info(f"  Ollama PID {p.info['pid']}: RSS={rss_gb:.1f}GB CPU={p.info['cpu_percent']:.1f}%")
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    time.sleep(2)
    if time.sleep.counter > 5:
        break
