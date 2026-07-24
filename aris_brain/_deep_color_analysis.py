"""
Deep color analysis of the image - check for specific patterns.
"""

import logging
logger = logging.getLogger(__name__)

from PIL import Image
from collections import Counter

path = r'C:\Users\user\AppData\Local\hermes\profiles\laap-avatar-v4\image_cache\img_1cdd68034bd5.jpg'
img = Image.open(path)
pixels = list(img.getdata())

logger.info(f"Image: {img.size[0]}x{img.size[1]} = {img.size[0]*img.size[1]} px")
print()

# 1. Check corners for background color
corners = {
    'top-left': pixels[0],
    'top-right': pixels[219],
    'bottom-left': pixels[-220],
    'bottom-right': pixels[-1],
}
logger.info("Corner colors:")
for name, rgb in corners.items():
    logger.info(f"  {name}: RGB{rgb}")
center = []
for y in range(80, 141):
    for x in range(80, 141):
        center.append(pixels[y * 220 + x])
avg_r = sum(p[0] for p in center) / len(center)
avg_g = sum(p[1] for p in center) / len(center)
avg_b = sum(p[2] for p in center) / len(center)
logger.info(f"\nCenter region (80..140,80..140):")
logger.info(f"  Average: RGB({avg_r:.0f},{avg_g:.0f},{avg_b:.0f})")
top = [px for y in range(60) for px in pixels[y*220:(y+1)*220]]
bottom = [px for y in range(160, 220) for px in pixels[y*220:(y+1)*220]]
top_avg = (sum(p[0] for p in top)/len(top), sum(p[1] for p in top)/len(top), sum(p[2] for p in top)/len(top))
bot_avg = (sum(p[0] for p in bottom)/len(bottom), sum(p[1] for p in bottom)/len(bottom), sum(p[2] for p in bottom)/len(bottom))
logger.info(f"\nTop 60 rows avg: RGB({top_avg[0]:.0f},{top_avg[1]:.0f},{top_avg[2]:.0f})")
logger.info(f"Bottom 60 rows avg: RGB({bot_avg[0]:.0f},{bot_avg[1]:.0f},{bot_avg[2]:.0f})")
horiz_changes = 0
for y in range(1, 220):
    for x in range(1, 220):
        p1 = pixels[y*220 + x]
        p2 = pixels[y*220 + x - 1]
        diff = abs(p1[0]-p2[0]) + abs(p1[1]-p2[1]) + abs(p1[2]-p2[2])
        if diff > 100:
            horiz_changes += 1
logger.info(f"\nEdge pixels (high contrast): {horiz_changes} ({horiz_changes*100/48400:.1f}%)")
reddish = sum(1 for p in pixels if p[0] > 150 and p[1] < 100 and p[2] < 100)
warm_red = sum(1 for p in pixels if p[0] > 180 and p[0] > p[1] * 1.5 and p[0] > p[2] * 1.5)
logger.info(f"Reddish pixels: {reddish}")
logger.info(f"Warm red/orange: {warm_red}")
green_dominant = sum(1 for p in pixels if p[1] > p[0] * 1.2 and p[1] > p[2] * 1.2)
logger.info(f"Green-dominant px: {green_dominant}")
blue_dominant = sum(1 for p in pixels if p[2] > p[0] * 1.1 and p[2] > p[1] * 1.1)
logger.info(f"Blue-dominant px: {blue_dominant}")
total = len(pixels)
logger.info(f"\nScene analysis:")
if green_dominant > total * 0.3:
    logger.info("  Likely: NATURE / FOREST / PLANTS (30%+ green)")
if blue_dominant > total * 0.15:
    logger.info("  Likely: SKY / WATER (15%+ blue)")
if reddish > total * 0.05:
    logger.info(f"  Possible: FLOWERS / WARM OBJECTS ({reddish*100/total:.1f}% red)")
if warm_red > total * 0.03:
    logger.info(f"  Possible: FLOWERS / ART ({warm_red*100/total:.1f}% warm red)")
if top_avg[2] > top_avg[0] and top_avg[2] > top_avg[1]:
    logger.info("  Sky likely at top (blue dominant)")
if bot_avg[1] > bot_avg[0] and bot_avg[1] > bot_avg[2]:
    logger.info("  Ground/plants likely at bottom (green dominant)")
import math
colorfulness = 0
for r, g, b in pixels:
    rg = abs(r - g)
    yb = abs(0.5*(r+g) - b)
    colorfulness += math.sqrt(rg*rg + yb*yb)
colorfulness /= total
logger.info(f"Colorfulness score: {colorfulness:.1f} (higher = more colorful)")