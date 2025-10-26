from collections.abc import Buffer, Generator, Iterable, Mapping
from contextlib import contextmanager
from os import PathLike
from pathlib import Path
from typing import Any

import exiv2


@contextmanager
def xmp_parser_context() -> Generator[None]:
    """WARNING: Make sure to use the same context for all threads."""
    exiv2.XmpParser.initialize()
    try:
        yield None
    finally:
        exiv2.XmpParser.terminate()


# Use image.io() as a Buffer (bytes-like) instead
# @contextmanager
# def get_file_data(image: exiv2.Image) -> Generator[bytes]:
#     exiv_io = image.io()
#     exiv_io.open()
#     try:
#         yield exiv_io.mmap()
#     finally:
#         exiv_io.munmap()
#         exiv_io.close()


def register_xmp_namespace(uri: str, namespace: str) -> None:
    """
    Registers a new namespace for XMP.
    The namespace URI should always end in an XML name separator such as '/' or '#'.

    WARNING: This method is not thread safe."""
    exiv2.XmpProperties.registerNs(uri, namespace)


def create_xmp_sidecar() -> Buffer:
    return exiv2.ImageFactory().create(exiv2.ImageType.xmp).io()


def save_xmp_sidecar(path: str | PathLike[str], data: Buffer) -> Path:
    path = Path(path)
    if not path.suffix == ".xmp":
        path = path.with_name(f"{path.name}.xmp")
    with open(path, "wb") as sidecar:
        sidecar.write(data)
    return path


type XmpDict = dict[str, exiv2.XmpTextValue | exiv2.XmpArrayValue | exiv2.LangAltValue]


def _parse_value(value: str) -> bool | int | float | str | None:
    if not value:
        return ""
    if value == "None":
        return None
    if value == "True" or value == "False":
        return value == "True"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def parse_xmp_value(
    value: exiv2.XmpTextValue | exiv2.XmpArrayValue | exiv2.LangAltValue,
) -> bool | int | float | str | list[bool | int | float | str]:
    if isinstance(value, exiv2.XmpTextValue):
        return _parse_value(str(value))
    elif isinstance(value, exiv2.XmpArrayValue):
        return [_parse_value(val) for val in value]


def read_xmp_metadata(image: Buffer | str | PathLike[str]) -> dict[str, Any]:
    if not isinstance(image, Buffer):
        image = str(image)
    img: exiv2.Image = exiv2.ImageFactory.open(image)
    img.readMetadata()
    xmp_data = img.xmpData()
    data: XmpDict = {}
    for datum in xmp_data:
        data[datum.key()] = parse_xmp_value(datum.value())
    return data


def set_xmp_bag(
    key: str, xmp_data: exiv2.XmpData, values: Iterable[float | str | bool]
):
    array = exiv2.XmpTextValue()
    array.setXmpArrayType(exiv2.XmpValue.XmpArrayType.xaBag)
    xmp_data[key] = array
    for idx, value in enumerate(values):
        xmp_data[f"{key}[{idx + 1}]"] = str(value)


def write_custom_xmp_metadata(
    image: Buffer | str | PathLike[str],
    data: Mapping[str, bool | float | str | Iterable[float] | Iterable[str]],
) -> Buffer:
    img: exiv2.Image = exiv2.ImageFactory.open(image)
    img.readMetadata()
    xmp_data = img.xmpData()
    for key, value in data.items():
        xmp_key = f"Xmp.{key}"
        if not isinstance(value, str) and isinstance(value, Iterable):
            set_xmp_bag(xmp_key, xmp_data, value)
        else:
            xmp_data[xmp_key] = str(value)
    img.writeMetadata()
    return img.io()
