from asyncio import gather, run
from collections.abc import Awaitable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.svgdb.api import gather_all_cards
from src.svgdb.storage import (
    download_and_save_svgdb_image,
    list_cards_to_download,
)
from src.utils.metadata import (
    register_xmp_namespace,
    xmp_parser_context,
)

SAVE_DIR = Path("/data/barracuda/Lataukset/Pictures/Shadowverse Database/")
NUM_THREADS = 4


async def main():
    all_cards = await gather_all_cards()

    register_xmp_namespace("svgdb/", "svgdb")
    with xmp_parser_context(), ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        save_tasks: list[Awaitable[Path | None]] = [
            download_and_save_svgdb_image(card, SAVE_DIR, executor)
            for card in await list_cards_to_download(all_cards, SAVE_DIR, executor)
        ]
        print(f"Downloading {len(save_tasks)} images...")
        await gather(*save_tasks)
        print("Downloads finished")


""" def fix_xmp_data(card: SVGDBCardMetadata, out_dir: Path) -> None:
    save_xmp_sidecar(
        construct_card_image_filename(card, out_dir),
        write_custom_xmp_metadata(
            create_xmp_sidecar(), data=format_svgdb_xmp_data(card)
        ),
    )


async def temp_main():
    register_xmp_namespace("svgdb/", "svgdb")
    with xmp_parser_context(), ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        existing_cards = list_existing_svgdb_cards(SAVE_DIR, executor)
        futures: list[Future[None]] = []
        for card in existing_cards:
            futures.append(executor.submit(fix_xmp_data, card, SAVE_DIR))
        for _future in as_completed(futures):
            pass """


run(main())
