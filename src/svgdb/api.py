from asyncio import gather
from typing import Literal

from httpx import ConnectTimeout, Response
from pydantic import BaseModel, RootModel, ValidationError

from src.constants import DEFAULT_HEADERS, REQUEST_CLIENT
from src.utils.rate_limit import rate_limit

SVGDB_URL = "https://svgdb.me/"
SVGDB_API_URL = SVGDB_URL + "api/"
SVGDB_API_EN_URL = SVGDB_API_URL + "en/"
SVGDB_API_CARDS_URL = SVGDB_API_URL + "cards/en/"
SVGDB_API_CENSORED_URL = SVGDB_API_URL + "censored/"
SVGDB_ASSETS_URL = SVGDB_URL + "assets/"
SVGDB_FULLART_URL = SVGDB_ASSETS_URL + "fullart/"
SVGDB_CENSORED_ART_URL = SVGDB_ASSETS_URL + "censored/"

type SVGDBCardType = Literal["Follower", "Amulet", "Spell"]
type SVGDBRarity = Literal["Bronze", "Silver", "Gold", "Legendary"]
type SVGDBCraft = Literal[
    "Bloodcraft",
    "Dragoncraft",
    "Forestcraft",
    "Havencraft",
    "Neutral",
    "Portalcraft",
    "Runecraft",
    "Shadowcraft",
    "Swordcraft",
]


class SVGDBCensoredCards(RootModel[set[int]]):
    pass


class SVGDBCard(BaseModel):
    name_: str
    id_: int
    pp_: int
    craft_: SVGDBCraft
    rarity_: SVGDBRarity
    type_: SVGDBCardType
    trait_: str
    expansion_: str
    baseEffect_: str
    baseFlair_: str
    rotation_: bool
    baseAtk_: int
    baseDef_: int
    evoAtk_: int
    evoDef_: int
    evoEffect_: str
    evoFlair_: str
    tokens_: list[int]
    alts_: list[int]
    restricted_count: int
    restricted_count_main: int
    restricted_count_sub: int
    resurgent_card: bool | None = None
    original_card: int | None = None
    artist: str = "Shadowverse"

    _censored: bool | None = None

    def can_evolve(self) -> bool:
        return self.type_ == "Follower"


class SVGDBCardMetadata(SVGDBCard):
    evolved: bool = False
    censored: bool = False


class SVGDBCards(RootModel[dict[int, SVGDBCard]]):
    pass


@rate_limit()
async def get_cards() -> SVGDBCards | Response:
    resp = await REQUEST_CLIENT.get(SVGDB_API_EN_URL, headers=DEFAULT_HEADERS)
    if resp.is_error:
        return resp
    return SVGDBCards.model_validate_json(resp.content)


@rate_limit()
async def get_censored_cards() -> SVGDBCensoredCards | Response:
    resp = await REQUEST_CLIENT.get(SVGDB_API_CENSORED_URL, headers=DEFAULT_HEADERS)
    if resp.is_error:
        return resp
    return SVGDBCensoredCards.model_validate_json(resp.content)


@rate_limit()
async def get_card(id_: int) -> SVGDBCard | Response:
    resp = await REQUEST_CLIENT.get(
        SVGDB_API_CARDS_URL + str(id_), headers=DEFAULT_HEADERS
    )
    if resp.is_error:
        return resp
    try:
        return SVGDBCard.model_validate_json(resp.content)
    except ValidationError:
        return resp


@rate_limit()
async def get_card_fullart(id_: int, evolved: bool = False) -> bytes | Response | None:
    url = f"{SVGDB_FULLART_URL}{id_}{int(evolved)}.png"
    try:
        resp = await REQUEST_CLIENT.get(url)
    except ConnectTimeout:
        print(f"Connection timed out with image: {url}")
        return None
    if resp.is_error:
        return resp
    return resp.content


@rate_limit()
async def get_card_censored_art(
    id_: int, evolved: bool = False
) -> bytes | Response | None:
    url = f"{SVGDB_CENSORED_ART_URL}{id_}{int(evolved)}.png"
    try:
        resp = await REQUEST_CLIENT.get(url)
    except ConnectTimeout:
        print(f"Connection timed out with image: {url}")
        return None
    if resp.is_error:
        return resp
    return resp.content


def construct_card_metadatas(
    card: SVGDBCard, censored_cards: SVGDBCensoredCards
) -> list[SVGDBCardMetadata]:
    card_dump = card.model_dump()
    metas: list[SVGDBCardMetadata] = [SVGDBCardMetadata(**card_dump)]
    if can_evolve := card.can_evolve():
        metas.append(SVGDBCardMetadata(**card_dump, evolved=True))
    if card.id_ in censored_cards.root:
        metas.append(SVGDBCardMetadata(**card_dump, censored=True))
        if can_evolve:
            metas.append(SVGDBCardMetadata(**card_dump, evolved=True, censored=True))
    return metas


async def gather_all_cards() -> list[SVGDBCardMetadata]:
    cards, censored = await gather(get_cards(), get_censored_cards())

    if not isinstance(cards, SVGDBCards):
        raise ValueError(f"Failed to get cards: {cards.status_code} {cards.text}")

    if not isinstance(censored, SVGDBCensoredCards):
        raise ValueError(
            f"Failed to get censored cards: {censored.status_code} {censored.text}"
        )

    # All cards seem to be in the data already
    """ def get_associated_ids(card: SVGDBCard) -> list[int]:
        ids: list[int] = card.tokens_ + card.alts_
        if card.original_card is not None:
            ids.append(card.original_card)
        return [id_ for id_ in ids if id_ not in all_cards]

    extra_ids: list[int] = []
    for card in all_cards.values():
        if card.id_ == 104522010:
            print(card)
        extra_ids += get_associated_ids(card)

    while extra_ids:
        extra_cards: dict[int, SVGDBCard] = {}

        async def add_card(id_: int) -> None:
            result = await get_card(id_)
            if isinstance(result, Response):
                if not result.is_error:
                    print(f"Encountered id with no data: {id_}")
                    return
                raise ValueError(
                    f"Failed to add card: {id_} {result.status_code} {result.text}"
                )
            extra_cards[id_] = result

        await gather(*[add_card(id_) for id_ in extra_ids])

        print("extras", extra_cards)
        all_cards.update(extra_cards)

        extra_ids.clear()
        for card in extra_cards.values():
            extra_ids += get_associated_ids(card) """

    all_cards: list[SVGDBCardMetadata] = []
    for card in cards.root.values():
        all_cards += construct_card_metadatas(card, censored)

    return all_cards
