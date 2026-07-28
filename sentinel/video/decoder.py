"""Decoder helpers (thin wrappers around OpenCV/FFmpeg used by sources)."""

from __future__ import annotations

import cv2
import numpy as np


def resize_keep_aspect(image: np.ndarray, target_width: int) -> np.ndarray:
    h, w = image.shape[:2]
    if w == target_width:
        return image
    scale = target_width / w
    return cv2.resize(image, (target_width, int(h * scale)))
