from __future__ import annotations

import os
import asyncio
import logging
from typing import Any

from reachy_robotis.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


def _camera_frame_to_bgr(frame: Any) -> Any:
    """Normalize Reachy/PIL/numpy camera frames into uint8 BGR for detection."""
    import cv2
    import numpy as np

    if frame is None:
        return None

    frame_type = type(frame)
    source_module = getattr(frame_type, "__module__", "")
    is_pil_image = source_module.startswith("PIL.")

    array = np.asarray(frame)
    if array.size == 0:
        return None

    array = np.squeeze(array)

    if array.ndim == 3 and array.shape[0] in {1, 3, 4} and array.shape[-1] not in {1, 3, 4}:
        array = np.moveaxis(array, 0, -1)

    if array.dtype != np.uint8:
        array = array.astype(np.float32, copy=False)
        if not np.isfinite(array).all():
            array = np.nan_to_num(array, nan=0.0, posinf=255.0, neginf=0.0)
        max_value = float(array.max()) if array.size else 0.0
        min_value = float(array.min()) if array.size else 0.0
        if max_value <= 1.0 and min_value >= 0.0:
            array = array * 255.0
        array = np.clip(array, 0, 255).astype(np.uint8)

    if array.ndim == 2:
        return cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)

    if array.ndim != 3:
        return None

    channels = array.shape[-1]
    if channels == 1:
        return cv2.cvtColor(array[:, :, 0], cv2.COLOR_GRAY2BGR)
    if channels == 4:
        if is_pil_image:
            return cv2.cvtColor(array, cv2.COLOR_RGBA2BGR)
        return np.ascontiguousarray(array[:, :, :3])
    if channels == 3:
        color_space = os.getenv("REACHY_ROBOTIS_CAMERA_COLOR_SPACE", "bgr").strip().lower()
        if is_pil_image or color_space == "rgb":
            return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
        return np.ascontiguousarray(array)
    return None


def _resize_for_detection(bgr: Any) -> tuple[Any, float]:
    import cv2

    height, width = bgr.shape[:2]
    max_dim = int(os.getenv("REACHY_ROBOTIS_DETECTION_MAX_DIM", "416") or "416")
    if max_dim <= 0 or max(height, width) <= max_dim:
        return bgr, 1.0
    scale = max_dim / float(max(height, width))
    resized = cv2.resize(
        bgr,
        (max(1, int(width * scale)), max(1, int(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def _position_for_center(center_x: float, center_y: float, width: int, height: int) -> dict[str, str]:
    if center_x < width / 3:
        horizontal = "left"
    elif center_x > width * 2 / 3:
        horizontal = "right"
    else:
        horizontal = "center"

    if center_y < height / 3:
        vertical = "top"
    elif center_y > height * 2 / 3:
        vertical = "bottom"
    else:
        vertical = "middle"

    return {"horizontal": horizontal, "vertical": vertical}


def _enrich_detections(
    detections: list[dict[str, Any]],
    width: int,
    height: int,
    scale: float,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    inverse = 1.0 / scale if scale else 1.0

    for det in detections:
        bbox = det.get("bbox") or []
        if len(bbox) != 4:
            continue
        x1, y1, x2, y2 = [int(round(float(value) * inverse)) for value in bbox]
        x1 = max(0, min(width, x1))
        x2 = max(0, min(width, x2))
        y1 = max(0, min(height, y1))
        y2 = max(0, min(height, y2))
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        box_area = max(0, x2 - x1) * max(0, y2 - y1)
        frame_area = max(1, width * height)

        enriched.append(
            {
                "label": det.get("label", "object"),
                "confidence": round(float(det.get("confidence", 0.0)), 3),
                "class_id": det.get("class_id"),
                "bbox": [x1, y1, x2, y2],
                "center": {"x": round(center_x / max(1, width), 3), "y": round(center_y / max(1, height), 3)},
                "position": _position_for_center(center_x, center_y, width, height),
                "area_ratio": round(box_area / frame_area, 4),
            }
        )

    return sorted(enriched, key=lambda item: item.get("confidence", 0.0), reverse=True)


def _summary_for_detections(detections: list[dict[str, Any]], target_label: str) -> str:
    if target_label and not detections:
        return f"No visible object matched '{target_label}'."
    if not detections:
        return "No objects were detected in the latest camera frame."

    parts = []
    for det in detections[:5]:
        pos = det.get("position", {})
        confidence = int(round(float(det.get("confidence", 0.0)) * 100))
        vertical = pos.get("vertical", "middle")
        horizontal = pos.get("horizontal", "center")
        parts.append(
            f"{det.get('label', 'object')} at {vertical}-{horizontal} ({confidence}%)"
        )
    return "Detected " + ", ".join(parts) + "."


class DetectObjects(Tool):
    """Detect visible objects from Reachy Mini's latest camera frame."""

    name = "detect_objects"
    description = (
        "Detect visible COCO objects from Reachy Mini's latest camera frame. "
        "Use this before answering when the user asks what Reachy can see, "
        "whether an object is present, or where something is located."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "target_label": {
                "type": "string",
                "description": "Optional object label to focus on, such as person, cup, bottle, or phone.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "default": 10,
                "description": "Maximum number of detections to return.",
            },
        },
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> dict[str, Any]:
        target_label = str(kwargs.get("target_label") or "").strip().lower()
        try:
            max_results = int(kwargs.get("max_results") or 10)
        except (TypeError, ValueError):
            max_results = 10
        max_results = max(1, min(20, max_results))

        logger.info("Tool call: detect_objects target=%s max_results=%s", target_label or "*", max_results)

        if deps.camera_worker is None:
            return {"ok": False, "error": "Camera worker not available"}

        frame = await asyncio.to_thread(deps.camera_worker.get_latest_frame)
        if frame is None:
            return {"ok": False, "error": "No frame available from camera worker"}

        bgr = await asyncio.to_thread(_camera_frame_to_bgr, frame)
        if bgr is None:
            return {"ok": False, "error": "Could not normalize camera frame"}

        height, width = bgr.shape[:2]
        detection_frame, scale = await asyncio.to_thread(_resize_for_detection, bgr)
        from reachy_robotis.vision.object_detector import get_object_detector

        detector = get_object_detector()
        raw_detections = await asyncio.to_thread(detector.detect, detection_frame)
        detections = _enrich_detections(raw_detections, width, height, scale)

        if target_label:
            detections = [
                det
                for det in detections
                if target_label in str(det.get("label", "")).lower()
            ]

        detections = detections[:max_results]
        counts: dict[str, int] = {}
        for det in detections:
            label = str(det.get("label", "object"))
            counts[label] = counts.get(label, 0) + 1

        detection_error = detector.error
        if not detections and detection_error and getattr(detector, "_available", None) is False:
            return {
                "ok": False,
                "error": detection_error,
                "model": detector.model_name,
                "device": detector.device,
            }

        return {
            "ok": True,
            "summary": _summary_for_detections(detections, target_label),
            "target_label": target_label,
            "target_found": bool(target_label and detections),
            "count": len(detections),
            "counts": counts,
            "frame": {"width": width, "height": height},
            "model": detector.model_name,
            "device": detector.device,
            "detections": detections,
        }
