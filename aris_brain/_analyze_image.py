"""Analyze image metadata and colors."""

import logging
logger = logging.getLogger(__name__)

from PIL import Image
from collections import Counter

path = r'C:\Users\user\AppData\Local\hermes\profiles\laap-avatar-v4\image_cache\img_1cdd68034bd5.jpg'
img = Image.open(path)
logger.info(f"Size: {img.size}")
logger.info(f"Mode: {img.mode}")
logger.info(f"Format: {img.format}")
p = img.quantize(colors=32)
palette = p.getpalette()
used = p.getcolors()
if used:
    used.sort(reverse=True)
    logger.info(f"\nTotal color clusters: {len(used)}")
    logger.info("Top palette colors:")
    for i, (count, idx) in enumerate(used[:20]):
        if count > 50:
            r, g, b = palette[idx*3:idx*3+3]
            logger.info(f"  {count:5d}px  RGB({r:3d},{g:3d},{b:3d})")
pixels = list(img.getdata())
gray = [int(0.299*r + 0.587*g + 0.114*b) for r,g,b in pixels]
# Brightness distribution
bright = sum(1 for v in gray if v > 200)
dark = sum(1 for v in gray if v < 50)
mid = len(gray) - bright - dark
logger.info(f"\nBrightness distribution:")
logger.info(f"  Bright (>200): {bright}px ({bright*100/len(gray):.1f}%)")
logger.info(f"  Mid range:     {mid}px ({mid*100/len(gray):.1f}%)")
logger.info(f"  Dark (<50):    {dark}px ({dark*100/len(gray):.1f}%)")
avg = sum(gray) / len(gray)
logger.info(f"  Average:       {avg:.1f}")