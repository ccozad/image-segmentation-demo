import numpy as np
import pytest

# OpenCV is CPU-installable (dev extra); skip cleanly if unavailable.
pytest.importorskip("cv2")

from worker.segmentation import overlay_masks

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_overlay_masks_returns_png():
    image = np.zeros((20, 30, 3), dtype=np.uint8)
    mask = np.zeros((20, 30), dtype=bool)
    mask[5:15, 5:20] = True

    out = overlay_masks(image, [mask], boxes=[[5, 5, 20, 15]], scores=[0.91])

    assert out[:8] == PNG_SIGNATURE


def test_overlay_masks_blends_color_into_region():
    import cv2

    image = np.zeros((20, 30, 3), dtype=np.uint8)
    mask = np.zeros((20, 30), dtype=bool)
    mask[5:15, 5:20] = True

    out = overlay_masks(image, [mask], alpha=0.5)
    decoded = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)

    # The masked region is no longer all-black after blending.
    assert decoded[10, 10].sum() > 0
    # A pixel outside the mask stays black.
    assert decoded[0, 0].sum() == 0
