# utils/avatar_generator.py
import requests
from io import BytesIO
from PIL import Image

DICEBEAR_BASE = "https://api.dicebear.com/9.x/initials/png"


def create_initials_avatar(name):
    """
    Generate an avatar using DiceBear's Initials style.
    Returns a PIL Image object.
    """
    params = {
        "seed": name,
    }
    response = requests.get(DICEBEAR_BASE, params=params)
    response.raise_for_status()

    img = Image.open(BytesIO(response.content))
    return img

