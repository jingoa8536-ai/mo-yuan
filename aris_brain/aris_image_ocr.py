"""
Aris 图片文字提取模块 — 对标微信"提取文字"功能
针对暗色终端截图做自适应预处理管线
"""
import subprocess, os, tempfile, json
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np

TESSERACT = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_text(image_path, lang='chi_sim+eng'):
    """完整的图片文字提取管线"""
    img = Image.open(image_path).convert('RGB')
    w, h = img.size
    
    results = {}
    
    # === 策略 1: 自适应二值化 + 大倍数放大 (最适合暗色终端截图) ===
    gray = img.convert('L')
    arr = np.array(gray)
    
    # 自适应阈值 - 按局部区域计算
    from numpy.lib.stride_tricks import sliding_window_view
    
    # 分块处理，每块计算自己的阈值
    block_size = 64
    h_blocks = h // block_size + 1
    w_blocks = w // block_size + 1
    
    bw_arr = np.ones_like(arr) * 255
    
    for bi in range(h_blocks):
        for bj in range(w_blocks):
            y0 = bi * block_size
            y1 = min((bi + 1) * block_size, h)
            x0 = bj * block_size
            x1 = min((bj + 1) * block_size, w)
            
            block = arr[y0:y1, x0:x1]
            local_mean = block.mean()
            local_std = block.std()
            
            # 暗色终端背景：背景很暗(均值<80)，文字较亮
            # 阈值取均值+半个标准差
            threshold = local_mean + 0.7 * max(local_std, 15)
            
            # 背景暗 => 文字是亮的部分 => 需要反转
            if local_mean < 80:
                # 反转：文字>阈值 => 黑色(0)，背景<阈值 => 白色(255)
                block_bw = np.where(block > threshold, 0, 255).astype(np.uint8)
            else:
                # 亮背景 => 正常二值化
                block_bw = np.where(block < threshold, 0, 255).astype(np.uint8)
            
            bw_arr[y0:y1, x0:x1] = block_bw
    
    bw = Image.fromarray(bw_arr, mode='L')
    # 放大4倍
    bw_big = bw.resize((w*4, h*4), Image.NEAREST)
    
    tmp1 = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp1.close()
    bw_big.save(tmp1.name)
    
    # 多种PSM模式
    for psm in [3, 4, 6, 11, 12]:
        r = subprocess.run([TESSERACT, tmp1.name, 'stdout', '--psm', str(psm), '-l', lang],
                         capture_output=True, text=True, timeout=60)
        text = r.stdout.strip()
        if text and len(text) > 10:
            results[f'adaptive_psm{psm}'] = text[:2000]
    
    try: os.unlink(tmp1.name)
    except: pass
    
    # === 策略 2: 强力对比度增强 + 反色 ===
    gray2 = img.convert('L')
    # 拉伸对比度
    arr2 = np.array(gray2)
    p5, p95 = np.percentile(arr2, [5, 95])
    if p95 > p5:
        arr2 = np.clip((arr2.astype(float) - p5) / (p95 - p5) * 255, 0, 255).astype(np.uint8)
    
    inv = 255 - arr2  # 反色：白字黑底 → 黑字白底
    # 阈值
    inv_bw = np.where(inv > 80, 255, 0).astype(np.uint8)
    bw2 = Image.fromarray(inv_bw, mode='L')
    bw2_big = bw2.resize((w*4, h*4), Image.NEAREST)
    
    tmp2 = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    tmp2.close()
    bw2_big.save(tmp2.name)
    
    for psm in [3, 6, 12]:
        r = subprocess.run([TESSERACT, tmp2.name, 'stdout', '--psm', str(psm), '-l', lang],
                         capture_output=True, text=True, timeout=60)
        text = r.stdout.strip()
        if text and len(text) > 10:
            results[f'contrast_psm{psm}'] = text[:2000]
    
    try: os.unlink(tmp2.name)
    except: pass
    
    return results


# === 执行 ===
if __name__ == '__main__':
    import sys
    
    paths = [
        ('img1', r'C:\Users\user\AppData\Local\hermes\profiles\aris\image_cache\img_07e050bd77fd.jpg'),
        ('img2', r'C:\Users\user\AppData\Local\hermes\profiles\aris\image_cache\img_22ceffd2e630.jpg'),
        ('img3', r'C:\Users\user\AppData\Local\hermes\profiles\aris\image_cache\img_350b3b2a10eb.jpg'),
        ('img4', r'C:\Users\user\AppData\Local\hermes\profiles\aris\image_cache\img_69e5fd4173b9.jpg'),
        ('img5', r'C:\Users\user\AppData\Local\hermes\profiles\aris\image_cache\img_fdde27d7b4ec.jpg'),
    ]
    
    for name, p in paths:
        print(f'\n{"="*60}')
        print(f'=== {name}: {os.path.basename(p)} ===')
        print(f'{"="*60}')
        try:
            result = extract_text(p)
            for method, text in result.items():
                # 找到最可能有意义的结果
                lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 5]
                # 过滤掉纯符号行
                real_lines = []
                for l in lines:
                    # 检查是否有字母或汉字
                    has_alpha = sum(1 for c in l if c.isascii() and c.isalpha()) > 3
                    has_hanzi = any('\u4e00' <= c <= '\u9fff' for c in l)
                    if has_alpha or has_hanzi:
                        real_lines.append(l)
                
                if real_lines:
                    print(f'\n  [{method}] ({len(real_lines)} lines):')
                    for i, line in enumerate(real_lines[:20]):
                        print(f'    {line}')
        except Exception as e:
            print(f'  Error: {e}')
