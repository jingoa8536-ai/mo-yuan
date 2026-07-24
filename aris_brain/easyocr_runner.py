"""由 vision_microservice 通过 subprocess 调用的 EasyOCR 包装器
在导入任何包之前先切换工作目录，避免 torch/_C 目录冲突
"""
import os
# 切换到安全目录再导入 torch
os.chdir(os.path.dirname(os.path.abspath(__file__)))  # LAAP/aris_brain/
import sys
import easyocr

image_path = sys.argv[1]
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
result = reader.readtext(image_path, detail=1, paragraph=False)

output = []
for bbox, text, conf in result:
    y = int((bbox[0][1] + bbox[2][1]) / 2)
    output.append({"text": text, "confidence": round(conf, 3), "y_center": y})

output.sort(key=lambda x: x["y_center"])
print(json.dumps(output, ensure_ascii=False))
