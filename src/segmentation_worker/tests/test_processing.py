import io

from PIL import Image

from worker.processing import render_annotation


def test_render_annotation_returns_png_same_size(png_bytes):
    out = render_annotation(png_bytes, "cars")
    img = Image.open(io.BytesIO(out))
    assert img.format == "PNG"
    assert img.size == (64, 48)
    # Drawing the red rectangle/label introduces pure-red pixels absent from
    # the flat source image.
    colors = {color for _count, color in img.convert("RGB").getcolors(maxcolors=100000)}
    assert (255, 0, 0) in colors
