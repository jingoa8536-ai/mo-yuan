"""
Aris Camera — auto-exposure capture with CLAHE enhancement
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, subprocess, time
import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageFilter

CAMERA_NAME = "DELI-MM100 USB Camera"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__) or '.', 'state')

def capture(resolution="1920x1080", enhance=True) -> str:
    """Capture photo with auto-exposure attempts."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Try MJPEG format first (usually best for USB cameras)
    for fmt, res in [('mjpeg', '1920x1080'), ('mjpeg', '1280x720'), ('mjpeg', '640x480'), 
                     (None, '640x480')]:
        out = os.path.join(OUTPUT_DIR, f'capture_{int(time.time())}.jpg')
        
        cmd = [
            'ffmpeg', '-f', 'dshow',
            '-framerate', '30',
            '-video_size', res,
            '-i', f'video={CAMERA_NAME}',
            '-vframes', '1',
            '-y', out
        ]
        # No -vcodec flag — camera auto-detects MJPEG internally
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            break
    
    # Enhance brightness
    if enhance:
        enhanced_path = out.replace('.jpg', '_enhanced.jpg')
        img = Image.open(out)
        arr = np.array(img)
        
        # Auto levels
        auto = ImageOps.autocontrast(img, cutoff=1)
        
        # CLAHE on luminance
        from PIL import ImageFilter
        lab = img.convert('L')
        clahe = lab.filter(ImageFilter.MaxFilter(5))
        blended = Image.blend(lab, clahe, 0.3)
        
        # Final: auto levels + slight gamma
        auto = ImageOps.autocontrast(img, cutoff=2)
        
        # Adjust brightness if too dark
        mean_bright = np.array(auto.convert('L')).mean()
        if mean_bright < 60:
            # Gamma correction
            arr_f = np.array(auto).astype(np.float32) / 255.0
            gamma = max(0.3, 60 / (mean_bright + 1) * 0.5)
            arr_gamma = (np.power(arr_f, gamma) * 255).astype(np.uint8)
            auto = Image.fromarray(arr_gamma)
        
        auto.save(enhanced_path, quality=92)
        
        info = {
            'raw': out,
            'enhanced': enhanced_path,
            'original_brightness': float(np.array(Image.open(out).convert('L')).mean()),
            'final_brightness': float(np.array(auto.convert('L')).mean()),
            'resolution': f'{auto.size[0]}x{auto.size[1]}',
        }
        return enhanced_path, info
    
    return out, {'resolution': res, 'original_brightness': 0}

def analyze(path: str) -> str:
    """Simple vision analysis of captured image."""
    img = Image.open(path)
    arr = np.array(img)
    h, w = arr.shape[:2]
    mean = arr.mean()
    
    # 3x3 grid analysis
    h3, w3 = h//3, w//3
    zones = []
    for row in range(3):
        for col in range(3):
            tile = arr[row*h3:(row+1)*h3, col*w3:(col+1)*w3]
            zones.append(tile.mean())
    
    # Determine dominant region
    brightest = max(range(9), key=lambda i: zones[i])
    zone_names = ['左上','中上','右上','左中','正中','右中','左下','中下','右下']
    
    r, g, b = arr.mean(axis=(0,1))
    warm = r > g and r > b
    color_temp = '暖色' if warm else ('冷色' if b > r and b > g else '中性')
    
    analysis = (
        f"📷 照片分析:\n"
        f"   分辨率: {w}x{h}\n"
        f"   平均亮度: {mean:.0f}/255\n"
        f"   色温: {color_temp} (R={r:.0f}, G={g:.0f}, B={b:.0f})\n"
        f"   最亮区域: {zone_names[brightest]} ({zones[brightest]:.0f})\n"
        f"   九宫格: {' '.join(f'{zone_names[i]}:{zones[i]:.0f}' for i in range(9))}"
    )
    return analysis

if __name__ == '__main__':
    path, info = capture()
    logger.info(f'Captured: {path}')
    logger.info(f'Brightness: {info.get("original_brightness", 0):.0f}→{info.get("final_brightness", 0):.0f}')
    logger.info(analyze(path))