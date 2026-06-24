"""Lightweight COCO object detector for the camera visualization panel."""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


def _color_for_class(class_id: int) -> tuple[int, int, int]:
    rng = (class_id * 2654435761) & 0xFFFFFFFF
    return (int(rng & 0xFF), int((rng >> 8) & 0xFF), int((rng >> 16) & 0xFF))


class ObjectDetector:
    """Lazy-loaded YOLO COCO detector with thread-safe, fail-soft inference."""

    def __init__(
        self,
        model_name: str = "yolo11n.pt",
        confidence_threshold: float = 0.35,
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.device = device

        self._model: Any = None
        self._lock = threading.Lock()
        self._available: Optional[bool] = None
        self._error: Optional[str] = None

    def _ensure_model(self) -> bool:
        """Load the YOLO model once; return True if it is ready to use."""
        if self._available is not None:
            return self._available

        with self._lock:
            if self._available is not None:
                return self._available
            try:
                from ultralytics import YOLO  # type: ignore[import-not-found]

                self._model = YOLO(self.model_name).to(self.device)
                self._available = True
                logger.info("Object detector loaded: %s on %s", self.model_name, self.device)
            except ImportError as exc:
                self._error = (
                    "ultralytics not installed. Install the extra: "
                    "pip install '.[yolo_vision]'"
                )
                self._available = False
                logger.warning("Object detection unavailable: %s (%s)", self._error, exc)
            except Exception as exc:  # noqa: BLE001 - model download/load can fail many ways
                self._error = f"Failed to load model '{self.model_name}': {exc}"
                self._available = False
                logger.warning("Object detection unavailable: %s", self._error)
            return self._available

    @property
    def available(self) -> bool:
        """Whether detection can run (attempts to load the model on first call)."""
        return self._ensure_model()

    @property
    def error(self) -> Optional[str]:
        """Human-readable reason detection is unavailable, if any."""
        return self._error

    def detect(self, frame_bgr: NDArray[np.uint8]) -> List[Dict[str, Any]]:
        """Run detection on a BGR frame."""
        if not self._ensure_model():
            return []

        try:
            with self._lock:
                results = self._model(frame_bgr, verbose=False, conf=self.confidence_threshold)
            if not results:
                return []
            result = results[0]
            names = getattr(result, "names", {}) or getattr(self._model, "names", {})
            boxes = getattr(result, "boxes", None)
            if boxes is None or boxes.xyxy is None:
                return []

            xyxy = boxes.xyxy.cpu().numpy()
            confs = boxes.conf.cpu().numpy() if boxes.conf is not None else np.ones(len(xyxy))
            class_ids = (
                boxes.cls.cpu().numpy().astype(int)
                if boxes.cls is not None
                else np.zeros(len(xyxy), dtype=int)
            )

            detections: List[Dict[str, Any]] = []
            for box, conf, class_id in zip(xyxy, confs, class_ids):
                detections.append(
                    {
                        "label": str(names.get(int(class_id), str(int(class_id)))),
                        "confidence": float(conf),
                        "class_id": int(class_id),
                        "bbox": [int(box[0]), int(box[1]), int(box[2]), int(box[3])],
                    }
                )
            return detections
        except Exception as exc:  # noqa: BLE001 - inference must never crash the route
            logger.error("Object detection inference failed: %s", exc)
            return []

    def annotate(
        self,
        frame_bgr: NDArray[np.uint8],
        detections: List[Dict[str, Any]],
    ) -> NDArray[np.uint8]:
        """Draw detection boxes and labels onto a copy of the frame."""
        import cv2

        annotated = frame_bgr.copy()
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            color = _color_for_class(det.get("class_id", 0))
            label = f"{det['label']} {det['confidence'] * 100:.0f}%"
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, max(0, y1 - th - 6)), (x1 + tw + 4, y1), color, -1)
            cv2.putText(
                annotated,
                label,
                (x1 + 2, max(10, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
        return annotated


_detector_singleton: Optional[ObjectDetector] = None
_detector_lock = threading.Lock()


def get_object_detector() -> ObjectDetector:
    """Return the process-wide object detector (created lazily)."""
    global _detector_singleton
    if _detector_singleton is None:
        with _detector_lock:
            if _detector_singleton is None:
                _detector_singleton = ObjectDetector()
    return _detector_singleton
