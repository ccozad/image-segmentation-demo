"""Real SAM 3 + OpenCV 5 segmentation (M3).

Heavy dependencies (torch, sam3, cv2) are imported lazily inside the class /
functions so that importing this module — and therefore the worker plumbing —
does not require a GPU stack. That keeps the loop/idempotency unit tests
runnable on a CPU-only dev box; only the real ``Segmenter`` needs the GPU.
"""
import io

import numpy as np
import structlog
from PIL import Image

log = structlog.get_logger()


class SegmentationError(Exception):
    """Raised when inference fails; the worker reports the job as failed."""


# Per-instance overlay colors (RGB). Cycled across detected instances.
_PALETTE: list[tuple[int, int, int]] = [
    (255, 56, 56),
    (56, 255, 56),
    (56, 56, 255),
    (255, 214, 56),
    (214, 56, 255),
    (56, 255, 214),
    (255, 128, 0),
    (0, 200, 255),
]


def _to_numpy(value):
    if value is None:
        return None
    if hasattr(value, "detach"):  # torch.Tensor
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def overlay_masks(image_rgb, masks, boxes=None, scores=None, alpha: float = 0.5) -> bytes:
    """Blend each instance mask as a translucent colored region; draw boxes +
    score labels. Returns PNG bytes (preserves edges cleanly). Pure/CPU — uses
    OpenCV but no model, so it is unit-testable with synthetic masks.
    """
    import cv2

    img = np.ascontiguousarray(image_rgb[:, :, :3].astype(np.uint8))
    overlay = img.copy()

    masks = _to_numpy(masks)
    for i, mask in enumerate(masks):
        m = np.asarray(mask)
        if m.ndim == 3:  # e.g. [1, H, W]
            m = m.squeeze(0)
        region = m.astype(bool)
        overlay[region] = _PALETTE[i % len(_PALETTE)]

    blended = cv2.addWeighted(overlay, alpha, img, 1.0 - alpha, 0.0)

    boxes = _to_numpy(boxes)
    scores = _to_numpy(scores)
    if boxes is not None:
        for i, box in enumerate(boxes):
            x0, y0, x1, y1 = (int(v) for v in np.asarray(box)[:4])
            color = _PALETTE[i % len(_PALETTE)]
            cv2.rectangle(blended, (x0, y0), (x1, y1), color, 2)
            if scores is not None and i < len(scores):
                label = f"{float(scores[i]):.2f}"
                cv2.putText(
                    blended,
                    label,
                    (x0, max(12, y0 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    1,
                    cv2.LINE_AA,
                )

    # cv2 encodes BGR; our array is RGB.
    ok, buf = cv2.imencode(".png", cv2.cvtColor(blended, cv2.COLOR_RGB2BGR))
    if not ok:
        raise SegmentationError("failed to encode annotated PNG")
    return buf.tobytes()


def _png_bytes(pil_image: Image.Image) -> bytes:
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    return buf.getvalue()


def _mask_count(masks) -> int:
    if masks is None:
        return 0
    if hasattr(masks, "shape"):
        return int(masks.shape[0])
    return len(masks)


class Segmenter:
    """Wraps the SAM 3 image model. Built once at worker startup and reused for
    every request (the model is large; per-request reload would be unusable).
    """

    def __init__(self) -> None:
        import torch  # noqa: PLC0415 - heavy, deferred
        from sam3.model.sam3_image_processor import Sam3Processor  # noqa: PLC0415
        from sam3.model_builder import build_sam3_image_model  # noqa: PLC0415

        if not torch.cuda.is_available():
            raise SegmentationError(
                "CUDA GPU not available — SAM 3 requires an NVIDIA GPU host"
            )

        log.info("sam3.loading")
        model = build_sam3_image_model().to("cuda")
        self._processor = Sam3Processor(model)
        log.info("sam3.loaded")

    def segment(self, image_bytes: bytes, prompt: str) -> tuple[bytes, int]:
        """Run text-prompted segmentation. Returns (annotated_png, mask_count).

        Zero matches -> the original image unchanged with mask_count 0.
        Any inference failure -> SegmentationError (worker marks job failed).
        """
        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        try:
            state = self._processor.set_image(pil)
            output = self._processor.set_text_prompt(state=state, prompt=prompt)
            masks = output["masks"]
            boxes = output.get("boxes")
            scores = output.get("scores")
        except Exception as exc:  # noqa: BLE001 - any inference failure -> failed job
            raise SegmentationError(f"inference failed: {exc}") from exc

        count = _mask_count(masks)
        if count == 0:
            log.info("sam3.no_masks", prompt=prompt)
            return _png_bytes(pil), 0

        annotated = overlay_masks(np.array(pil), masks, boxes, scores)
        return annotated, count
