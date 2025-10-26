from asyncio import get_running_loop
from collections.abc import Buffer, Iterable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from logging import exception
from os import PathLike
from pathlib import Path
from typing import Any

from httpx import Response
from pathvalidate import sanitize_filename
from pydantic import ValidationError

from src.svgdb.api import SVGDBCardMetadata, get_card_censored_art, get_card_fullart
from src.utils.image import save_optimized_image
from src.utils.metadata import (
    create_xmp_sidecar,
    read_xmp_metadata,
    save_xmp_sidecar,
    write_custom_xmp_metadata,
)


def construct_card_image_filename(
    card: SVGDBCardMetadata,
    out_directory: str | PathLike[str],
    file_suffix: str = ".png",
) -> Path:
    censoring = "censored" if card.censored else "uncensored"
    is_evolved = "evolved" if card.evolved else "unevolved"

    if card.artist:
        artist_parts = card.artist.split("/")
        artist = (
            artist_parts[0]
            if len(artist_parts) > 1 and artist_parts[0].upper() == artist_parts[1]
            else " ".join(artist_parts)
        )
    else:
        artist = card.artist
    filename = f"{card.id_} {card.type_} {card.craft_} {is_evolved} {censoring} {
        sanitize_filename(card.name_)
    } ({artist}) [] {{}}{file_suffix}"
    return Path(out_directory, filename)


def _prefix_svgdb_key(key: str | bool | float, delimiter: str = ":") -> str:
    return f"svgdb{delimiter}{key}"


def format_svgdb_xmp_data(card: SVGDBCardMetadata) -> dict[str, Any]:
    card_dump = {f"svgdb.{key}": value for key, value in card.model_dump().items()}
    # Set Dublin Core XMP keywords to allow more efficient filtering in digiKam
    card_dump["dc.subject"] = [
        _prefix_svgdb_key(key, ":")
        for key in (card.id_, card.craft_, card.rarity_, card.type_)
    ]
    return card_dump


def save_svgdb_image(
    card: SVGDBCardMetadata,
    image: Buffer,
    out: str | PathLike[str],
) -> None:
    try:
        save_xmp_sidecar(
            out,
            write_custom_xmp_metadata(
                create_xmp_sidecar(), data=format_svgdb_xmp_data(card)
            ),
        )
        save_optimized_image(image, out)
    except Exception:
        exception(f"Failed to save SVGDB image for card '{card.id_}':")


async def download_and_save_svgdb_image(
    card: SVGDBCardMetadata,
    out_directory: str | PathLike[str],
    executor: ThreadPoolExecutor,
) -> Path | None:
    image: Buffer | Response | None
    if card.censored:
        image = await get_card_censored_art(card.id_, evolved=card.evolved)
    else:
        image = await get_card_fullart(card.id_, evolved=card.evolved)

    if not image:
        return

    if isinstance(image, Response):
        if "404 Not Found" in image.text:
            if not card.original_card:
                print(
                    f"Card image not found for card '{card.id_}' | evolved: {card.evolved} | censored: {card.censored}"
                )
            return
        else:
            raise ValueError(
                f"Failed to download image for card '{card.id_}' | evolved: {card.evolved} | censored: {card.censored}"
            )

    image_path = construct_card_image_filename(card, out_directory)
    await get_running_loop().run_in_executor(
        executor, save_svgdb_image, card, image, image_path
    )

    return image_path


def list_existing_svgdb_cards(
    data_directory: str | PathLike[str], executor: ThreadPoolExecutor
) -> list[SVGDBCardMetadata]:
    path = Path(data_directory)
    cards: list[SVGDBCardMetadata] = []
    futures: list[Future[None]] = []

    def read_existing_svgdb_card(card_path: Path) -> None:
        if (
            card_path.suffix == ".xmp"
            and card_path.is_file()
            and card_path.with_suffix("").exists()
        ):
            try:
                cards.append(
                    SVGDBCardMetadata(
                        **{
                            key[key.rindex(".") + 1 :]: value
                            for key, value in read_xmp_metadata(card_path).items()
                        }
                    )
                )
            except ValidationError as exc:
                print(f"XMP data for '{card_path}' is invalid: {exc}")

    for file in path.iterdir():
        futures.append(executor.submit(read_existing_svgdb_card, file))

    for _future in as_completed(futures):
        pass

    return cards


async def list_cards_to_download(
    all_cards: Iterable[SVGDBCardMetadata],
    data_directory: str | PathLike[str],
    executor: ThreadPoolExecutor,
) -> list[SVGDBCardMetadata]:
    """Lists missing cards and those whose data doesn't match the data in `all_cards`."""
    existing_cards = list_existing_svgdb_cards(data_directory, executor)
    lookup_table = {
        (card.id_, card.evolved, card.censored): card for card in existing_cards
    }
    missing_cards: list[SVGDBCardMetadata] = []
    for card in all_cards:
        key = (card.id_, card.evolved, card.censored)
        if key not in lookup_table or lookup_table[key] != card:
            missing_cards.append(card)
    return missing_cards
