"""Aris 极简图片读取器 — 零依赖"""
import sys, base64, json
from PIL import Image

path = sys.argv[1]
img = Image.open(path)
print(f"尺寸: {img.size[0]}x{img.size[1]}")
print(f"格式: {img.format}")
print(f"文件: {path.split('/')[-1].split('\\\\')[-1]}")
print(f"大小: ~{img.size[0]*img.size[1]*3//1024}KB RGB")
