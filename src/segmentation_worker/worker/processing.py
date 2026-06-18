import io

from PIL import Image, ImageDraw, ImageFont


def render_annotation(image_bytes: bytes, prompt: str) -> bytes:
    """M2 fake processing: draw a labeled rectangle in the center of the image.

    Replaced by real SAM 3 + OpenCV inference in M3.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    x0, y0, x1, y1 = int(w * 0.25), int(h * 0.25), int(w * 0.75), int(h * 0.75)
    line_width = max(2, min(w, h) // 100)
    draw.rectangle([x0, y0, x1, y1], outline=(255, 0, 0), width=line_width)

    try:
        font = ImageFont.load_default(size=max(14, min(w, h) // 15))
    except TypeError:  # Pillow < 10.1 has no size argument
        font = ImageFont.load_default()
    draw.text((x0 + line_width + 2, y0 + line_width + 2), prompt, fill=(255, 0, 0), font=font)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
