from collections.abc import Buffer
from io import BytesIO
from os import PathLike

from PIL import Image


def save_optimized_image(
    image: Buffer,
    out_path: str | PathLike[str],
    format_: str = "PNG",
) -> None:
    with Image.open(BytesIO(image)) as img:
        img.save(out_path, format=format_, optimize=True)
