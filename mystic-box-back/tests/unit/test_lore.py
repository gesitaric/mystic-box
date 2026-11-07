from mystic_shared.cards import CHARACTERS, get_character
from mystic_shared.lore import (
    BONDS,
    CHRONICLE,
    REGIONS,
    SECRET_UNLOCK_ASCENSION,
    SECRETS,
    STORIES,
    public_lore,
    public_world,
    unlocked_secret_title,
)
from mystic_shared.stats import ELEMENTS

REGION_IDS = {region["id"] for region in REGIONS}


def test_every_character_has_a_story():
    assert set(STORIES) == {character["file_name"] for character in CHARACTERS}


def test_stories_are_well_formed():
    for file_name, lore in STORIES.items():
        assert lore["region"] in REGION_IDS, file_name
        assert lore["title"].strip(), file_name
        assert len(lore["story"]) >= 3, file_name
        assert all(isinstance(p, str) and p.strip() for p in lore["story"]), file_name


def test_regions_are_unique_and_on_the_map():
    assert len(REGION_IDS) == len(REGIONS)
    for region in REGIONS:
        assert 0 <= region["x"] <= 100 and 0 <= region["y"] <= 100, region["id"]
        assert region["name"] and region["description"], region["id"]


def test_bonds_point_to_real_characters():
    pairs = set()
    for a, b, a_about_b, b_about_a in BONDS:
        assert get_character(a) and get_character(b), (a, b)
        assert a != b
        assert a_about_b.strip() and b_about_a.strip()
        pair = frozenset((a, b))
        assert pair not in pairs, (a, b)
        pairs.add(pair)


def test_every_character_has_a_bond():
    bonded = {name for a, b, *_ in BONDS for name in (a, b)}
    missing = {c["file_name"] for c in CHARACTERS} - bonded
    assert not missing


def test_public_lore_shows_both_sides_of_a_bond():
    malachar = public_lore(get_character("malachar.jfif"))
    mortis = public_lore(get_character("mortis.jfif"))

    assert malachar["region"] == {"id": "nocthaven", "name": "Nocthaven", "element": "umbra"}
    to_mortis = next(b for b in malachar["bonds"] if b["file_name"] == "mortis.jfif")
    to_malachar = next(b for b in mortis["bonds"] if b["file_name"] == "malachar.jfif")
    assert to_mortis["name"] == "Mortis"
    assert to_mortis["relation"].startswith("Pulled him")
    assert to_malachar["relation"].startswith("His master")


def test_public_lore_returns_a_copy():
    character = get_character("malachar.jfif")
    public_lore(character)["story"].append("changed")
    assert public_lore(character)["story"][-1] != "changed"


def test_public_lore_of_unknown_card_is_none():
    assert public_lore(None) is None
    assert public_lore({"file_name": "missing.png"}) is None


def test_public_world_places_every_character_once():
    world = public_world()
    placed = [c["file_name"] for r in world["regions"] for c in r["characters"]]

    assert world["world"]["name"]
    assert sorted(placed) == sorted(c["file_name"] for c in CHARACTERS)
    nocthaven = next(r for r in world["regions"] if r["id"] == "nocthaven")
    assert "story" not in nocthaven["characters"][0]


def test_get_world_endpoint_is_public():
    import json

    from get_world import app as get_world

    ret = get_world.lambda_handler({"httpMethod": "GET"}, "")
    assert ret["statusCode"] == 200
    assert json.loads(ret["body"]) == public_world()


def test_every_character_has_a_secret_chapter():
    assert set(SECRETS) == {c["file_name"] for c in CHARACTERS}
    for file_name, (title, text) in SECRETS.items():
        assert title.strip() and text.strip(), file_name


def test_secret_text_only_leaves_the_server_after_ascending():
    character = get_character("ignis.jfif")

    locked = public_lore(character, ascension=SECRET_UNLOCK_ASCENSION - 1)["secret"]
    assert locked["unlocked"] is False
    assert locked["text"] is None
    assert locked["title"] == SECRETS["ignis.jfif"][0]
    assert locked["unlockAscension"] == SECRET_UNLOCK_ASCENSION

    unlocked = public_lore(character, ascension=SECRET_UNLOCK_ASCENSION)["secret"]
    assert unlocked["unlocked"] is True
    assert unlocked["text"] == SECRETS["ignis.jfif"][1]


def test_bonds_mark_which_characters_the_player_owns():
    bonds = public_lore(get_character("malachar.jfif"), owned={"mortis.jfif"})["bonds"]
    owned = {b["file_name"]: b["owned"] for b in bonds}

    assert owned["mortis.jfif"] is True
    assert owned["zarathor.jfif"] is False
    assert all("owned" not in b for b in public_lore(get_character("malachar.jfif"))["bonds"])


def test_regions_have_a_valid_element_and_whisper():
    for region in REGIONS:
        assert region["element"] is None or region["element"] in ELEMENTS, region["id"]
        assert region["whisper"].strip(), region["id"]


def test_world_has_a_chronicle():
    world = public_world()
    assert world["chronicle"] == CHRONICLE
    assert all(entry["era"] and entry["title"] and entry["text"] for entry in CHRONICLE)


def test_unlocked_secret_title_only_on_the_unlocking_ascension():
    ignis = get_character("ignis.jfif")
    level = SECRET_UNLOCK_ASCENSION

    assert unlocked_secret_title(ignis, level - 1, level) == SECRETS["ignis.jfif"][0]
    assert unlocked_secret_title(ignis, level, level + 1) is None
    assert unlocked_secret_title(None, 0, 1) is None
