"""Check system resources."""

import logging
logger = logging.getLogger(__name__)

import psutil
import os

mem = psutil.virtual_memory()
logger.info(f"RAM Total: {mem.total/1e9:.1f} GB")
logger.info(f"RAM Available: {mem.available/1e9:.1f} GB")
logger.info(f"RAM Used: {mem.percent}%")
swap = psutil.swap_memory()
logger.info(f"Swap: {swap.total/1e9:.1f} GB used {swap.used/1e9:.1f} GB")
logger.info(f"CPU cores: {psutil.cpu_count(logical=True)}")
logger.info(f"CPU freq: {psutil.cpu_freq()}")
logger.info("\nTop processes by memory:")
for p in sorted(psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']), 
                key=lambda p: p.info.get('memory_info', psutil._common.smem(0,0,0,0,0,0)).rss if p.info.get('memory_info') else 0, 
                reverse=True)[:10]:
    try:
        mem_mb = p.info['memory_info'].rss / 1e6
        logger.info(f"  PID {p.info['pid']:6d} {mem_mb:8.1f}MB  {p.info['name'][:30]}")
    except Exception as e:
        logger.debug(f"操作失败: {e}")