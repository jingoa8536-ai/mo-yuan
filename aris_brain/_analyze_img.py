"""分析图片特征"""
import sys, os, json
from PIL import Image
import numpy as np

path = sys.argv[1]
img = Image.open(path).convert("L")
arr = np.array(img)

white = int((arr > 200).sum())
black = int((arr < 50).sum())
total = arr.size

result = {
    "path": path,
    "size": img.size,
    "white_pct": round(white / total * 100, 1),
    "black_pct": round(black / total * 100, 1),
    "other_pct": round((total - white - black) / total * 100, 1),
}
print(json.dumps(result))
