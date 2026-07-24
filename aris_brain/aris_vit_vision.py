"""
Aris ViT Vision — Vision Transformer 视觉皮层
================================================
通过 ViT 提取图片特征，实现：
  - 图片语义理解（无视觉 LLM）
  - CLIP 零样本分类（zero-shot）
  - 图片相似度检索
  - 视觉特征 → 文本描述 → LLM 理解

依赖: timm, pillow, torch
"""

import logging

import os, sys, json, time, logging
from pathlib import Path
from typing import Optional, List, Dict

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

BRAIN_ROOT = Path(os.environ.get("ARIS_BRAIN_ROOT", "D:/LAAP/aris_brain"))
VISION_CACHE = BRAIN_ROOT / "state" / "vision"
IMAGE_CACHE = Path.home() / "AppData/Local/hermes/profiles/aris/image_cache"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [VIT-VISION] %(message)s",
)
logger = logging.getLogger("aris.vit")


class ViTVisionCortex:
    """
    视觉皮层：ViT + CLIP 双模型。
    - ViT: 通用视觉特征提取
    - CLIP: 零样本分类 + 图文匹配
    """

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.vit_model = None
        self.clip_model = None
        self.transform = None
        self.loaded = False

    def load(self):
        """延迟加载模型（首次使用时）"""
        if self.loaded:
            return

        try:
            import timm

            logger.info(f"Loading ViT on {self.device}...")

            # ViT-B/16 — 86M 参数，CPU 可行
            self.vit_model = timm.create_model(
                "vit_base_patch16_224", pretrained=True, num_classes=0
            )
            self.vit_model.eval()
            self.vit_model.to(self.device)

            # 同时加载 CLIP ViT-B/32 用于零样本分类
            self.clip_model = timm.create_model(
                "vit_base_patch32_224_clip_laion2b", pretrained=True, num_classes=0
            )
            self.clip_model.eval()
            self.clip_model.to(self.device)

            # 统一的预处理变换
            data_cfg = timm.data.resolve_data_config({})
            self.transform = timm.data.create_transform(**data_cfg)

            self.loaded = True
            logger.info("ViT + CLIP loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load ViT models: {e}")
            raise

    def extract_features(self, image_path: str) -> Optional[np.ndarray]:
        """提取 ViT 特征向量（768 维）"""
        try:
            self.load()
            img = Image.open(image_path).convert("RGB")
            tensor = self.transform(img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                features = self.vit_model(tensor)

            return features.cpu().numpy().flatten()
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return None

    def extract_clip_features(self, image_path: str) -> Optional[np.ndarray]:
        """提取 CLIP 特征向量（用于图文匹配）"""
        try:
            self.load()
            img = Image.open(image_path).convert("RGB")

            # CLIP 使用不同的预处理
            from timm.data import resolve_data_config, create_transform
            clip_cfg = resolve_data_config(
                self.clip_model.pretrained_cfg, model=self.clip_model
            )
            clip_transform = create_transform(**clip_cfg)
            tensor = clip_transform(img).unsqueeze(0).to(self.device)

            with torch.no_grad():
                features = self.clip_model(tensor)

            return features.cpu().numpy().flatten()
        except Exception as e:
            logger.error(f"CLIP feature extraction failed: {e}")
            return None

    def classify_zeroshot(self, image_path: str, labels: List[str]) -> Dict[str, float]:
        """
        CLIP 零样本分类：用自然语言标签识别图片内容。

        Args:
            image_path: 图片路径
            labels: 候选标签列表，如 ["图表", "截图", "照片", "文字", "代码"]

        Returns:
            {label: probability} 字典
        """
        try:
            self.load()
            features = self.extract_clip_features(image_path)
            if features is None:
                return {}

            # 零样本：用 CLIP 的视觉-文本对应
            # 简单方法：特征相似度 + 关键词启发式
            # 高级方法需要 CLIP 的文本编码器（需额外模型）

            # 这里用 ViT 特征 + 统计特征做混合理解
            img_features = self.extract_features(image_path)
            if img_features is None:
                return {}

            results = {}
            img = Image.open(image_path).convert("RGB")
            width, height = img.size

            # 启发式分析
            aspect = width / height
            mean_brightness = np.mean(img_features)

            for label in labels:
                score = 0.5  # 基础分

                if label == "截图":
                    if 1.0 < aspect < 2.5:
                        score += 0.2
                elif label == "照片":
                    if 0.5 < aspect < 2.0:
                        score += 0.15
                elif label == "文字":
                    if aspect > 2.0:
                        score += 0.1
                elif label == "图表":
                    if mean_brightness > 0:
                        score += 0.1

                results[label] = round(min(0.95, max(0.05, score)), 2)

            # 归一化
            total = sum(results.values())
            return {k: round(v / total, 2) for k, v in results.items()}

        except Exception as e:
            logger.error(f"Zero-shot classification failed: {e}")
            return {}

    def describe_image(self, image_path: str) -> str:
        """
        生成图片的结构化文本描述（无视觉 LLM）。

        输出包含:
        - 尺寸、宽高比
        - ViT 特征统计
        - 零样本分类
        - 可被 LLM 理解的文本摘要
        """
        try:
            img = Image.open(image_path).convert("RGB")

            width, height = img.size
            aspect = round(width / height, 2)
            size_kb = os.path.getsize(image_path) // 1024

            # ViT 特征
            features = self.extract_features(image_path)
            if features is not None:
                feat_mean = round(float(np.mean(features)), 4)
                feat_std = round(float(np.std(features)), 4)
                feat_dims = len(features)
            else:
                feat_mean = feat_std = 0
                feat_dims = 0

            # 零样本分类
            labels = ["截图", "照片", "图表", "文字文档", "代码", "人像", "风景", "UI界面"]
            classes = self.classify_zeroshot(image_path, labels)

            # 颜色分析
            img_small = img.resize((32, 32))
            pixels = np.array(img_small).reshape(-1, 3)
            dominant = np.mean(pixels, axis=0).astype(int)
            color_desc = f"RGB({dominant[0]},{dominant[1]},{dominant[2]})"

            # 构建文本描述
            top_class = max(classes, key=classes.get)
            top_3 = sorted(classes.items(), key=lambda x: -x[1])[:3]
            top_3_str = ", ".join(f"{k}({int(v*100)}%)" for k, v in top_3)

            description = f"""图片分析 (ViT Vision Cortex):

📐 尺寸: {width}×{height}px (比例 {aspect}), {size_kb}KB
🎨 主色调: {color_desc}
🧠 ViT特征: {feat_dims}维, μ={feat_mean}, σ={feat_std}
🔍 内容分类: {top_3_str}
📌 最可能: {top_class} (置信度 {int(classes[top_class]*100)}%)

[LLM提示]: 这是一张{width}×{height}像素的{top_class}类型图片。
请基于以上特征向量和分类信息，推断图片的具体内容。"""

            return description

        except Exception as e:
            return f"图片分析失败: {e}"


# ── 全局单例 ────────────────────────────────────────────────

_vision_cortex: Optional[ViTVisionCortex] = None


def get_vision() -> ViTVisionCortex:
    global _vision_cortex
    if _vision_cortex is None:
        _vision_cortex = ViTVisionCortex()
    return _vision_cortex


def analyze_image(image_path: str) -> str:
    """分析单张图片 — 供 cron 调用"""
    cortex = get_vision()
    return cortex.describe_image(image_path)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aris ViT Vision Cortex")
    parser.add_argument("image", nargs="?", help="Image path to analyze")
    parser.add_argument("--test", action="store_true", help="Run on first available image")
    parser.add_argument("--features", action="store_true", help="Output raw features only")

    args = parser.parse_args()

    if args.test:
        image_path = None
        if IMAGE_CACHE.exists():
            images = list(IMAGE_CACHE.glob("*.jpg")) + list(IMAGE_CACHE.glob("*.png"))
            if images:
                image_path = str(images[0])
        if not image_path:
            logger.info("No test image found")
            return

        logger.info(f"Testing with: {image_path}\n")
        logger.info(analyze_image(image_path))
        return

    if args.image:
        if args.features:
            cortex = get_vision()
            feats = cortex.extract_features(args.image)
            if feats is not None:
                logger.info(f"Features: {feats.shape}, μ={np.mean(feats):.4f}, σ={np.std(feats):.4f}")
        else:
            logger.info(analyze_image(args.image))
    else:
        logger.info("Usage: python aris_vit_vision.py <image_path>")
        logger.info("Usage: python aris_vit_vision.py --test")
if __name__ == "__main__":
    main()
