# utils/avatar_generator.py
from PIL import Image, ImageDraw, ImageFont
import hashlib


def name_to_color(name):
    """Generate a consistent color from a name."""
    hash_digest = hashlib.md5(name.encode()).hexdigest()
    # Use first 6 characters for RGB
    r = int(hash_digest[:2], 16)
    g = int(hash_digest[2:4], 16)
    b = int(hash_digest[4:6], 16)
    return f"#{r:02x}{g:02x}{b:02x}"


def create_initials_avatar(name, size=128, font_color="#fff",):
    initials = "".join([part[0] for part in name.split()][:2]).upper()
    bg_color = name_to_color(name)

    img = Image.new('RGB', (size, size), color=bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", size // 2)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initials, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    draw.text(
        ((size - text_width) / 2, (size - text_height) / 2),
        initials,
        fill=font_color,
        font=font
    )

    return img

