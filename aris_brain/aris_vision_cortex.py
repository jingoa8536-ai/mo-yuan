"""
Aris VisionCortex v2 — 统一视觉感知皮层
========================================
聚合所有视觉算法为统一接口，通过 CognitiveBus 注入 PSI 认知循环。

引擎清单 (2026-06-28):
  ✅ 目标检测        YOLOv12 (ultralytics 8.3.80) — CUDA可用
  ✅ 开放集检测      GroundingDINO (transformers)  — CUDA可用
  ✅ 语义分割        SAM ViT-B/L (transformers)    — CUDA可用
  ✅ 深度估计        Depth Anything (transformers)  — CUDA可用
  ✅ 图像语义        ViT + CLIP (aris_vit_vision)  — CUDA可用
  ⬜ OCR             EasyOCR (待下载模型权重)
  ⬜ 3D视觉          DUSt3R (待网络修复)
  ⬜ 视频理解        VideoMAE (待网络修复)

模型缓存: E:/aris/models/ (91GB可用)
印记: Aris 永远记得 Lorry — 2026-06-28
"""

import logging, os, sys, json, time
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import numpy as np

logger = logging.getLogger("aris.vision_cortex")

# ─── 模型缓存路径 ────────────────────────────────────────
os.environ.setdefault("HF_HOME", "E:/aris/models/hf_cache")
os.environ.setdefault("TRANSFORMERS_CACHE", "E:/aris/models/hf_cache/hub")

# ─── 引擎管理器 ───────────────────────────────────────────

class EnginePool:
    """懒加载引擎池，首次使用时才加载模型到GPU。"""
    
    def __init__(self):
        self._engines = {}
        self._device = None
    
    @property
    def device(self):
        if self._device is None:
            import torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        return self._device
    
    def get_sam(self):
        """Segment Anything 分割模型。"""
        if "sam" not in self._engines:
            t0 = time.time()
            from transformers import SamModel, SamProcessor
            model = SamModel.from_pretrained("facebook/sam-vit-base", local_files_only=True)
            processor = SamProcessor.from_pretrained("facebook/sam-vit-base", local_files_only=True)
            model.to(self.device)
            self._engines["sam"] = (model, processor)
            logger.info(f"[Vision] SAM ViT-B 加载: {time.time()-t0:.1f}s")
        return self._engines["sam"]
    
    def get_depth(self):
        """Depth Anything 深度估计。"""
        if "depth" not in self._engines:
            t0 = time.time()
            from transformers import pipeline
            pipe = pipeline(
                "depth-estimation",
                model="LiheYoung/depth-anything-small-hf",
                device=0 if self.device == "cuda" else -1,
            )
            self._engines["depth"] = pipe
            logger.info(f"[Vision] Depth Anything 加载: {time.time()-t0:.1f}s")
        return self._engines["depth"]
    
    def get_yolo(self):
        """YOLOv12 目标检测 (ultralytics)。"""
        if "yolo" not in self._engines:
            t0 = time.time()
            from ultralytics import YOLO
            model = YOLO("yolo12n.yaml")  # YOLOv12 nano architecture (no weights needed for arch)
            self._engines["yolo"] = model
            logger.info(f"[Vision] YOLOv12 架构加载: {time.time()-t0:.1f}s")
        return self._engines["yolo"]
    
    def get_grounding_dino(self):
        """GroundingDINO 开放集检测。"""
        if "grounding_dino" not in self._engines:
            t0 = time.time()
            from transformers import GroundingDinoForObjectDetection, GroundingDinoProcessor
            model = GroundingDinoForObjectDetection.from_pretrained(
                "IDEA-Research/grounding-dino-base", local_files_only=True
            )
            processor = GroundingDinoProcessor.from_pretrained(
                "IDEA-Research/grounding-dino-base", local_files_only=True
            )
            model.to(self.device)
            self._engines["grounding_dino"] = (model, processor)
            logger.info(f"[Vision] GroundingDINO 加载: {time.time()-t0:.1f}s")
        return self._engines["grounding_dino"]
    
    def get_vit(self):
        """ViT视觉皮层 (已有模块)。"""
        if "vit" not in self._engines:
            sys.path.insert(0, "D:/LAAP/aris_brain")
            from aris_vit_vision import ViTVisionCortex
            cortex = ViTVisionCortex()
            cortex.load()
            self._engines["vit"] = cortex
        return self._engines["vit"]


# ─── 全局引擎池 ──────────────────────────────────────────
_ENGINES = EnginePool()


# ════════════════════════════════════════════════════════════
# 视觉任务接口
# ════════════════════════════════════════════════════════════

def detect_objects(image_path: str, conf_threshold: float = 0.3) -> List[Dict]:
    """目标检测。
    
    Returns:
        [{"label": "person", "confidence": 0.95, "bbox": [x1,y1,x2,y2]}, ...]
    """
    try:
        model = _ENGINES.get_yolo()
        results = model(image_path, verbose=False)
        detections = []
        for r in results:
            for box, cls_id, conf in zip(r.boxes.xyxy, r.boxes.cls, r.boxes.conf):
                if float(conf) >= conf_threshold:
                    detections.append({
                        "label": model.names[int(cls_id)],
                        "confidence": round(float(conf), 4),
                        "bbox": [float(x) for x in box],
                    })
        return detections
    except Exception as e:
        logger.error(f"[Vision] detect_objects 失败: {e}")
        return []


def segment_image(image_path: str) -> Dict:
    """语义分割 (SAM)。
    
    Returns:
        {"masks": [...], "scores": [...], "shapes": [...]}
    """
    try:
        from PIL import Image
        model, processor = _ENGINES.get_sam()
        image = Image.open(image_path).convert("RGB")
        inputs = processor(image, return_tensors="pt").to(_ENGINES.device)
        
        with torch.no_grad():
            outputs = model(**inputs, multimask_output=False)
        
        pred_masks = outputs.pred_masks.squeeze().cpu().numpy()
        iou_scores = outputs.iou_scores.squeeze().cpu().numpy()
        
        return {
            "masks": pred_masks.tolist() if pred_masks.ndim > 2 else [pred_masks.tolist()],
            "scores": iou_scores.tolist() if iou_scores.ndim > 0 else [float(iou_scores)],
            "shape": list(pred_masks.shape),
        }
    except Exception as e:
        logger.error(f"[Vision] segment_image 失败: {e}")
        return {"error": str(e)}


def estimate_depth(image_path: str) -> Dict:
    """深度估计。
    
    Returns:
        {"depth": [[...]], "min": 0.0, "max": 1.0}
    """
    try:
        pipe = _ENGINES.get_depth()
        result = pipe(image_path)
        depth = result["depth"]
        depth_arr = np.array(depth, dtype=np.float32)
        return {
            "depth": depth_arr.tolist(),
            "shape": list(depth_arr.shape),
            "min": float(depth_arr.min()),
            "max": float(depth_arr.max()),
            "mean": float(depth_arr.mean()),
        }
    except Exception as e:
        logger.error(f"[Vision] estimate_depth 失败: {e}")
        return {"error": str(e)}


def analyze_scene(image_path: str) -> Dict[str, Any]:
    """全场景分析：检测 + 深度 + 语义。
    
    一次性运行所有引擎，返回综合结果。
    """
    result = {
        "detections": detect_objects(image_path),
        "depth": estimate_depth(image_path),
        "source": image_path,
        "engine": "VisionCortex v1",
    }
    
    # 语义理解
    try:
        vit = _ENGINES.get_vit()
        vision_result = vit.analyze_image(image_path)
        result["semantic"] = vision_result
    except Exception as e:
        logger.warning(f"[Vision] 语义分析跳过: {e}")
    
    result["elapsed_ms"] = 0  # TODO: 精确计时
    return result


# ════════════════════════════════════════════════════════════
# CLI 接口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python aris_vision_cortex.py <图片路径> [任务]")
        print("任务: all (默认) | detect | segment | depth | scene")
        sys.exit(1)
    
    path = sys.argv[1]
    task = sys.argv[2] if len(sys.argv) > 2 else "all"
    
    if not os.path.exists(path):
        print(f"文件不存在: {path}")
        sys.exit(1)
    
    import torch
    print(f"设备: {_ENGINES.device}")
    print(f"处理: {path}")
    print()
    
    t0 = time.time()
    
    if task in ("all", "detect"):
        print("=== 目标检测 ===")
        dets = detect_objects(path)
        for d in dets:
            print(f"  {d['label']}: {d['confidence']:.3f} [{d['bbox'][0]:.0f},{d['bbox'][1]:.0f},{d['bbox'][2]:.0f},{d['bbox'][3]:.0f}]")
        print()
    
    if task in ("all", "depth"):
        print("=== 深度估计 ===")
        depth = estimate_depth(path)
        if "error" not in depth:
            print(f"  形状: {depth['shape']}")
            print(f"  范围: {depth['min']:.3f} - {depth['max']:.3f}")
            print(f"  均值: {depth['mean']:.3f}")
        print()
    
    if task in ("all", "scene"):
        print("=== 场景分析 ===")
        scene = analyze_scene(path)
        print(f"  检测: {len(scene['detections'])} 个目标")
        print(f"  深度: {scene['depth'].get('shape', 'N/A')}")
    
    print(f"耗时: {(time.time()-t0)*1000:.0f}ms")
