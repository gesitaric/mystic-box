"""Mundo, regiões, histórias e laços entre as personagens.

Fonte única da história do jogo: o frontend só exibe o que a API devolve.
- `WORLD` e `REGIONS`: o mapa-múndi (`GET /world`). `x`/`y` são a posição da
  região no mapa (0 a 100) e `terrain` é a chave do visual da região.
- `STORIES`: de onde cada carta vem (`region`), o título e a história em
  parágrafos. Toda carta de `cards.py` precisa estar aqui (teste `test_lore.py`).
- `BONDS`: laços entre duas personagens, com o que cada uma pensa da outra.
- `RIVALRIES`: rivalidades, com o que cada uma diz ao encontrar a outra em batalha.
  `public_lore` devolve os laços de uma carta já com o nome da outra.
"""

import copy

from .cards import CHARACTERS, get_character

WORLD = {
    "name": "Aethra",
    "epithet": "The Shattered Realms",
    "story": [
        "Long ago Aethra was a single land, warmed by the Aetherwell, the spring of "
        "living magic at its heart. Beneath the spring slept the Hollow, a hunger "
        "older than the stars. To keep it asleep, the Seven Wardens forged the "
        "Mystic Box and locked the Hollow inside.",
        "A generation ago, a plague swept through the kingdom of Nocthaven. "
        "Malachar, the last of the Wardens, opened the Box in search of a cure. "
        "The Hollow breathed out, and the land cracked into the Shattered Realms in "
        "a single night that every child of Aethra now calls the Sundering.",
        "The Box was never closed again. It drifts in the Riftheart, the crater "
        "where the Sundering began, and it calls champions from every realm, "
        "binding them into cards for the summoners it chooses. No one knows whether "
        "it is gathering an army to seal the Hollow again, or simply choosing who "
        "will be standing when the Hollow wakes.",
    ],
}

REGIONS = [
    {
        "id": "riftheart",
        "name": "The Riftheart",
        "epithet": "Where the world broke",
        "terrain": "rift",
        "x": 50, "y": 50,
        "description": "A crater of floating stone and violet light where the "
        "Sundering began. The Mystic Box drifts at its center, humming. Nobody lives "
        "here; everyone who has seen it dreams about it afterward.",
    },
    {
        "id": "hrimvald",
        "name": "Hrimvald",
        "epithet": "The frozen north",
        "terrain": "frost",
        "x": 46, "y": 11,
        "description": "Endless tundra, ice cliffs and a single mountain pass that "
        "connects the north to the rest of Aethra. The wind-wolves still howl here, "
        "and the knights of the pass answer them.",
    },
    {
        "id": "zephyrine",
        "name": "The Zephyrine Isles",
        "epithet": "Islands that float on the wind",
        "terrain": "isles",
        "x": 20, "y": 15,
        "description": "Fragments of land torn into the sky by the Sundering, now "
        "ruled by an empress who steers them with the wind. Dragons nest on their "
        "undersides, and waterfalls pour into the clouds.",
    },
    {
        "id": "nocthaven",
        "name": "Nocthaven",
        "epithet": "The kingdom that would not die",
        "terrain": "shadow",
        "x": 78, "y": 18,
        "description": "The kingdom where the plague began and the Box was opened. "
        "Its graveyards stretch to the horizon, its libraries read their readers, "
        "and its nobles bargain with shadows to keep their thrones.",
    },
    {
        "id": "skyspire",
        "name": "The Skyspire",
        "epithet": "The stair to the stars",
        "terrain": "sky",
        "x": 60, "y": 31,
        "description": "A tower of cloud and marble that rises from the Riftheart's "
        "edge into the heavens. Angels, astrologers and star-hunters live on its "
        "terraces, watching the cracked sky for what falls through it.",
    },
    {
        "id": "greenhollow",
        "name": "Greenhollow Vale",
        "epithet": "The quiet heartland",
        "terrain": "meadow",
        "x": 35, "y": 40,
        "description": "Farms, meadows and sleepy villages that the Sundering "
        "somehow spared. At its edge lies the Mirewood swamp, and the vale's "
        "folk know better than to go there after dark.",
    },
    {
        "id": "sylvaran",
        "name": "The Sylvaran Wilds",
        "epithet": "The forest that remembers",
        "terrain": "forest",
        "x": 13, "y": 44,
        "description": "The oldest forest in Aethra, home of the elves, the moon "
        "flowers and the spirit beasts. Its trees remember the world before the "
        "Sundering and do not forgive those who forgot it.",
    },
    {
        "id": "aurelian",
        "name": "The Aurelian Dominion",
        "epithet": "The kingdom of the sun",
        "terrain": "holy",
        "x": 75, "y": 47,
        "description": "Golden cathedrals, sun temples and the knightly orders sworn "
        "to protect them. The Dominion survived the Sundering by holding its gates "
        "shut, and some of its knights still have not forgiven themselves for it.",
    },
    {
        "id": "hoshigane",
        "name": "The Hoshigane Isles",
        "epithet": "The islands of falling petals",
        "terrain": "blossom",
        "x": 93, "y": 58,
        "description": "Eastern islands of cherry blossoms, temple lanterns and "
        "sword clans. Their duels are poems, and their feuds last for generations.",
    },
    {
        "id": "spirehollow",
        "name": "Spirehollow",
        "epithet": "The city of a thousand rooftops",
        "terrain": "city",
        "x": 59, "y": 66,
        "description": "A free city of spires and night markets built on the "
        "crossroads of every trade route. Everything is for sale here, including "
        "secrets, and especially loyalty.",
    },
    {
        "id": "ironfang",
        "name": "The Ironfang Highlands",
        "epithet": "The mountains of old grudges",
        "terrain": "mountain",
        "x": 29, "y": 70,
        "description": "Rocky peaks and wind-scoured passes ruled by warrior clans, "
        "arenas and caravans. The earth here is restless and full of runes nobody "
        "remembers carving.",
    },
    {
        "id": "thalassar",
        "name": "The Thalassar Coast",
        "epithet": "The drowned shore",
        "terrain": "sea",
        "x": 11, "y": 84,
        "description": "A coast of tide-temples, sunken cities and harbor towns. The "
        "Sundering drowned half of it, and on quiet nights the bells of the sunken "
        "temples can still be heard beneath the waves.",
    },
    {
        "id": "cinderpeak",
        "name": "Cinderpeak",
        "epithet": "The burning south",
        "terrain": "volcano",
        "x": 47, "y": 88,
        "description": "Volcanoes, lava falls and fortresses of black glass. The "
        "Everfire burns somewhere in its depths, and the dragons that once ruled "
        "here have not given up on returning.",
    },
    {
        "id": "cogsreach",
        "name": "Cogsreach",
        "epithet": "The steam cities",
        "terrain": "steam",
        "x": 79, "y": 79,
        "description": "Cities of brass, steam and captured lightning, run by "
        "barons who grew rich selling machines to the realms rebuilding after the "
        "Sundering. Not everyone in Cogsreach got rich.",
    },
]

_REGION_IDS = {region["id"] for region in REGIONS}

def _story(region, title, *paragraphs):
    return {"region": region, "title": title, "story": list(paragraphs)}


# Ordem: 5★, 4★ e 3★, como em `cards.py`.
STORIES = {
    # ---------- 5★ ----------
    "malachar.jfif": _story(
        "nocthaven",
        "The Warden Who Opened the Box",
        "Malachar was the youngest of the Seven Wardens and the keeper of their "
        "archive, a quiet scholar who knew the name of every star and every poison. "
        "When the plague came to Nocthaven he read every forbidden tome for a cure, "
        "and every tome pointed to the same place: inside the Mystic Box.",
        "He opened it. He found no cure, only the Hollow, and the Hollow breathed "
        "out. The Sundering cracked the world, and the plague dead of Nocthaven rose "
        "and would not lie down again. Malachar bound their souls into his tome so "
        "they would not be devoured, and has carried them ever since.",
        "He rules Nocthaven's endless graveyards now, called a tyrant by the living "
        "and a jailer by the dead. Only he knows the truth: if he ever lets the "
        "souls go, the Hollow will eat them. He answers the Box because he made it "
        "what it is, and he means to be there when it finally closes.",
    ),
    "boreas.jfif": _story(
        "hrimvald",
        "The Wall of the Northern Gale",
        "On the night of the Sundering a shepherd girl in Hrimvald found a wind-wolf "
        "dying in the snow, its pack torn apart by something that crawled out of the "
        "cracking ice. She sheltered the wolf in her own cloak until dawn. The wolf, "
        "Hrimfang, died at sunrise, and gave her everything it had left.",
        "She woke clad in ice that never melts, with the northern gale howling "
        "inside her helm. She took the name Boreas and has never removed the helm "
        "since, not even for her squire Glacius, who has served her for twenty years "
        "without seeing her face.",
        "Boreas holds the Frostgate, the only pass between the tundra and the south, "
        "against the hollowborn that still creep out of the deep ice. She has never "
        "lost the pass. She has, however, been searching for Hrimfang's scattered "
        "pack for a generation, and she has started to hear their howl again in the "
        "south, coming from the forests of the Sylvaran Wilds.",
    ),
    "astra.jfif": _story(
        "skyspire",
        "The Cartographer of Stars",
        "Astra was born in Greenhollow on the night of the Sundering, at the exact "
        "moment the sky cracked. The midwife swore a falling star landed in the "
        "cradle. By the age of nine she could read the constellations; by fifteen "
        "she could pull them down; by sixteen she had climbed the Skyspire and "
        "talked her way into its observatory.",
        "She is now its youngest master, redrawing the broken heavens one stolen "
        "star at a time. Her greatest frustration is the archer Lyra, whose arrows "
        "keep adding new stars where Astra's maps say there should be none.",
        "She left an apprentice, Albin, in her old study in Greenhollow and keeps "
        "promising to come back and teach him properly. She also believes the "
        "cracks in the sky form a map of their own, and that it points straight at "
        "the Mystic Box.",
    ),
    "seraphiel.jfif": _story(
        "aurelian",
        "The Storm-Blessed Guardian",
        "Seraphiel was a simple guard at the temple of Ithrel, on the eastern edge "
        "of the Aurelian Dominion. On the night of the Sundering he prayed beneath "
        "the falling stars, and holy lightning struck him without burning, filling "
        "him with a light that has never faded.",
        "Ithrel lies in ruins now, but Seraphiel never left it. He turned its broken "
        "halls into a shelter for anyone the Dominion turned away, and there he "
        "raised a frightened orphan named Annelise, who grew up to be a healer.",
        "He does not consider himself a hero, only a man who was given more light "
        "than he needs. So he gives it away, mending the wounded and lifting the "
        "fallen. The Dominion's high orders call him a deserter. The people of "
        "Ithrel call him the reason they survived.",
    ),
    "ignis.jfif": _story(
        "cinderpeak",
        "The Knight Inside the Flame",
        "Ignis was a knight sworn to guard the Everfire, the flame in the heart of "
        "Cinderpeak that kept the southern realms warm through the long night after "
        "the Sundering. When the volcano lords came to steal it, Ignis swallowed the "
        "flame whole rather than let it fall into their hands.",
        "The fire never left. It burns inside the cracked armor, behind the red "
        "eyes, along the jagged blade. Ignis no longer remembers the face beneath the "
        "helm, only the vow: as long as the fire burns, the knight still stands. On "
        "that same night Ignis carried a burned boy out of a dying village; the boy "
        "was Pyralis, and he has followed the knight's legend ever since.",
        "The volcano lords who betrayed the dragon-queen of Cinderpeak still hunt "
        "the Everfire. Ignis knows they will come again, and knows the flame cannot "
        "burn forever inside one body. Ignis is looking for a worthy heir, and "
        "refuses to admit it may already have been found.",
    ),
    "leoric.jfif": _story(
        "aurelian",
        "The Lion of the Fallen Cathedral",
        "Leoric was the youngest knight of the Lion Order when the Sundering split "
        "the ground beneath the cathedral of Valdremont. While his brothers fled, he "
        "held the doors with the order's shield until every pilgrim was out, and the "
        "collapsing stone could not bring itself to crush him.",
        "He is the last of the Lion Order. His brothers died in the chaos, and the "
        "Dominion, ashamed, chose to forget them. Leoric did not. He still keeps "
        "vigil in the ruins, polishing a row of empty helms, and he has sworn to "
        "find the twelve lost blades of his order.",
        "He has found three. The fourth, he heard, ended up in a barn in "
        "Greenhollow, in the hands of a frightened farm boy who thinks it is just a "
        "rusty sword. Leoric has not decided yet whether to take it back, or to see "
        "if the boy is worthy of it.",
    ),
    "lunara.jfif": _story(
        "thalassar",
        "Keeper of the Moon Tides",
        "The moon pulls the oceans, and Lunara pulls the moon. She was raised by the "
        "tide-witches of the Amethyst Shoals, who taught her to sing the crystals "
        "awake and to hear the rhythm of the sea in every living heart.",
        "When the Sundering drowned half the Thalassar Coast, the tide-witches sang "
        "for three days to stop the flood, and only Lunara survived the song. She "
        "has kept the tides calm alone ever since, with the help of Celestine above "
        "and Isolde's knights along the shore.",
        "She heals the wounded by drawing pain out like a receding wave, and those "
        "she mends hear the ocean for days. But each full moon the tide pulls toward "
        "the Riftheart instead of the shore, and Lunara is starting to suspect the "
        "Mystic Box is calling the sea itself.",
    ),
    "mortis.jfif": _story(
        "nocthaven",
        "The Smiling Crypt-Keeper",
        "Mortis was the royal jester of Nocthaven, and he was buried alive during "
        "the plague when a panicked physician mistook his best trick for death. He "
        "was still laughing in his coffin when Malachar opened the Box and the dead "
        "began to rise.",
        "Malachar pulled him out of the grave and made him keeper of the crypts. "
        "Mortis has never decided whether to thank him or to haunt him, so he does "
        "both. The skulls that orbit him whisper secrets, and he trades them for "
        "favors, curses and Aether.",
        "Facing Mortis means never knowing which trick comes next, and by the time "
        "his enemies figure it out, he is already wearing their strength like a "
        "borrowed coat. He has only one rule: nobody makes fun of Malachar except him.",
    ),
    "drakara.jfif": _story(
        "cinderpeak",
        "Daughter of the Molten Crown",
        "Drakara is the last child of Ysmera, the dragon-queen of Cinderpeak, and "
        "half dragon herself. After the Sundering the volcano lords betrayed her "
        "mother, and Ysmera's brother, the dragon sovereign Draemir, refused to fly "
        "south to save her.",
        "Drakara walked into the lava falls alone and came out carrying the "
        "greatsword the traitors had melted into the mountain's heart. She has "
        "hunted the volcano lords one by one since then, and she has not forgiven "
        "her uncle. She is not sure she ever will.",
        "She fights to reclaim her mother's throne, but she has learned that a "
        "crown is worth nothing without people to protect. Every summoner who calls "
        "her is tested: those who flinch at fire are left behind, and those who "
        "stand with her are never left alone.",
    ),
    "gorvane.jfif": _story(
        "ironfang",
        "The Warlord Who Would Not Fall",
        "Gorvane was the chieftain of the Ironfang clans, who held the highlands "
        "against every empire that wanted their iron. In the Sundering the mountain "
        "opened beneath his warband, and he walked into the Hollow's breath to drag "
        "his warriors back out. He saved most of them. He did not come back alone.",
        "Since that day the earth refuses to take him. He has been killed four "
        "times, and four times he has risen angrier than before. His axe drinks the "
        "fury of the fallen, and the scholar Eldric believes the runes on it are "
        "the Hollow's own writing.",
        "His son Brannoc fights in the arenas to prove he is nothing like his "
        "father. His old shieldbearer Garrick left him after the fourth death, "
        "unable to watch. Gorvane wanders from war to war looking for an enemy "
        "strong enough to keep him in the ground, and he is starting to fear there "
        "is none.",
    ),
    "elysia.jfif": _story(
        "skyspire",
        "The Choir of the Silent Wind",
        "Elysia was the voice that sang the dawn hymn in the sky cathedral of "
        "Aerith. When the Sundering tore the cathedral loose and sent it drifting on "
        "the winds, she kept singing for forty days so that the pilgrims inside "
        "would not lose hope, and the wind itself began to answer.",
        "The cathedral finally came to rest against the Skyspire, where Uriel "
        "anchored it with a spear of light. Elysia has sung beside the angel every "
        "dawn since, and the breezes carry her hymns across the realms, mending "
        "wounds and lifting the fallen.",
        "She rarely speaks, and when she does, those who hear her forget what they "
        "were afraid of. Only Uriel knows that she has not sung a single note "
        "since the Box began calling champions. She says she is listening to "
        "something that is singing back.",
    ),
    "uriel.jfif": _story(
        "skyspire",
        "The Spear of the First Dawn",
        "Uriel was the first light to touch Aethra when it was young. Long before "
        "the Sundering, the angel stood guard at the Gate of Dawn, making sure every "
        "night ended. Uriel also watched the Seven Wardens forge the Mystic Box, "
        "and warned them that a lock is only as strong as the hand that holds the key.",
        "When Malachar opened the Box, the Gate of Dawn shattered with the sky. "
        "Uriel came down to the Skyspire to search for its pieces, and has spent a "
        "generation anchoring falling cathedrals, guiding lost stars and keeping "
        "watch over the Riftheart.",
        "The golden spear has pierced storms, curses and armies of shadow, but "
        "Uriel's true weapon is patience. Uriel does not hate Malachar; the angel "
        "pities him. That pity is the only thing Malachar has never been able to bear.",
    ),
    "celestine.png": _story(
        "thalassar",
        "Herald of the High Tide",
        "Celestine was the high priestess of the sea-temples of Thalassar. When the "
        "Sundering sank them, she refused to sink with them. The tide-goddess she "
        "served gave her wings of sea foam turned to feathers and a spear forged "
        "from the light that falls on deep water.",
        "She commands the currents from above the clouds, calling rain onto burning "
        "fields and floods onto invading fleets. Her younger sister Isolde stayed on "
        "the ground and built the Tidewatch, and the two have argued for twenty "
        "years about which of them truly protects the coast.",
        "Sailors say that if the sky turns gold before a storm, Celestine is "
        "passing overhead. Her temples still ring beneath the waves, and on some "
        "nights she dives to the drowned altar to listen for the goddess, who has "
        "not answered since the Sundering.",
    ),
    "lyra.png": _story(
        "skyspire",
        "The Archer Who Shoots the Constellations",
        "Every arrow Lyra fires becomes a star. She was an elf of the Sylvaran Wilds "
        "who climbed the tallest tree in the forest to see what lay beyond the "
        "cracked sky, and kept climbing until she reached the Skyspire.",
        "She drifts on the high winds between realms, laughing at gravity and at "
        "anyone who tries to predict her. She has filled half the new sky by "
        "herself, which drives the astrologer Astra mad, and her old stars "
        "sometimes fall, which keeps the huntress Stellara very busy.",
        "Enemies who think they have her cornered usually discover that the Lyra "
        "they were chasing was only starlight. Beneath the jokes, though, she has a "
        "secret: every star she fires is aimed at a crack in the sky, and slowly, "
        "one arrow at a time, she is stitching it closed.",
    ),
    "zarathor.jfif": _story(
        "nocthaven",
        "The Pact-Bound Dark Lord",
        "Zarathor was a minor lord of Nocthaven when the Sundering came. As the "
        "Hollow's breath swept over his city of Vharoth, he offered his shadow to "
        "the thing inside it in exchange for the power to save his people. The city "
        "survived. His shadow grew horns.",
        "He rules Vharoth with fear and red fire, and his people are the safest in "
        "all the Shattered Realms. He is also Malachar's bitterest rival: Zarathor "
        "believes the Box should be opened all the way and its power used, not "
        "feared. Nocturna, the sorceress of the violet sigil, was once his advisor "
        "and more; she left him the night his shadow first spoke.",
        "Zarathor answers the Mystic Box to keep his shadow fed: as long as it has "
        "enemies to devour, it will not turn on him. Morwen has sworn to kill him, "
        "and the assassin Vesper has accepted her contract. He knows both, and he "
        "is waiting.",
    ),
    "vaelora.jfif": _story(
        "zephyrine",
        "Empress of the Floating Isles",
        "When the Sundering tore the western hills into the sky, a young noblewoman "
        "named Vaelora refused to let them fall. She bound the winds with a jeweled "
        "scepter and steered the broken land into the clouds, and the survivors "
        "crowned her empress of the Zephyrine Isles.",
        "Her crystal dragon, Lirien, hatched from a gem in her crown on the day she "
        "was crowned. Her sky guard is led by Kyrielle and her storm dragon, and "
        "her court is visited each year by the dragon sovereign Draemir, whose "
        "citadel drifts at the edge of her isles.",
        "She is elegant, merciless toward tyrants and endlessly generous toward "
        "travelers. When her isles drift over a realm at war, the fighting tends to "
        "stop, not out of fear, but because no one wants to be the one Lirien "
        "decides to dislike.",
    ),
    "draemir.jfif": _story(
        "zephyrine",
        "The Dragon-Blooded Sovereign",
        "Draemir drank from the Sunwell of the dragons as a boy and has not aged a "
        "day since. Chosen by the great wyrms to speak for them among mortals, he "
        "has ruled the dragons of Aethra for five hundred years from a citadel that "
        "drifts above the Zephyrine Isles.",
        "When the volcano lords of Cinderpeak betrayed his sister Ysmera, Draemir "
        "did not fly south. The dragons were dying in the Sundering, and he chose "
        "to save the many over the one. His niece Drakara has never forgiven him, "
        "and he has never asked her to.",
        "His blazing sword has ended wars before they began. He answers the Mystic "
        "Box with the patience of something ancient, but he carries one hope he "
        "tells no one: that somewhere in a battle beside Drakara, he will finally "
        "be able to say he is sorry.",
    ),
    "kyrielle.jfif": _story(
        "zephyrine",
        "Rider of the Storm Wyrm",
        "Kyrielle found the silver dragon Aurvex as an egg cracked by lightning on "
        "the stormiest island of the Zephyrine sky. Every storm since has been a "
        "lesson: she learned to call thunder by listening to Aurvex's heartbeat, "
        "and the dragon learned to trust a human by listening to hers.",
        "As captain of Empress Vaelora's sky guard, she patrols the auroras above "
        "the isles, striking down sky pirates and guiding lost ships home. Aurvex "
        "is a grandchild of Draemir's own wyrm, and the sovereign watches the pair "
        "with an interest Kyrielle finds flattering and a little worrying.",
        "Years ago, a lonely boy in Cogsreach saw Aurvex fly over the walls of "
        "Brasshelm and spent his childhood building a dragon of his own. Kyrielle "
        "has no idea she inspired him, but she would very much like to meet Spark.",
    ),
    # ---------- 4★ ----------
    "kaito.jfif": _story(
        "hoshigane",
        "The Last Dragonfly",
        "Kaito wears the dragonfly crest of the Tonbo clan, whose castle burned the "
        "night after the Sundering while the islands were still shaking. Masked "
        "assassins of the Kurokage, the shadow clan, did it on a rival lord's "
        "orders. Kaito, eleven years old, survived by hiding in the castle well.",
        "He is the last swordsman of his clan, wandering the Hoshigane Isles with a "
        "blade drawn faster than the wind. His rival and closest friend, Hayato, "
        "has beaten him in exactly as many duels as he has lost to him.",
        "Kaito hunts the Kurokage still. He does not know that the quiet fighter "
        "with blue fire in his fists, the one who has saved his life twice, was "
        "raised by them.",
    ),
    "solara.jfif": _story(
        "aurelian",
        "The Sun-Crowned Priestess",
        "Solara was chosen as the sun's priestess on the longest day of the year, "
        "when the light crowned her in front of the whole city. A month later the "
        "Sundering broke the temple of Solmarr, and she spent her first years as "
        "priestess praying in the rubble.",
        "A stonemason named Cassius rebuilt the temple for her, stone by stone, and "
        "the sun blessed him for it. She is the only person who can make Cassius "
        "laugh, and he is the only one who has seen her cry.",
        "Her staff burns with the heat of noon, and her spells can turn a "
        "battlefield into a desert. She believes the sun does not hate the "
        "darkness; it simply refuses to let it win.",
    ),
    "aurelius.jfif": _story(
        "aurelian",
        "The Paladin Who Kept the Gates",
        "Aurelius swore his oath in the Sun Hall at twelve and has never broken it. "
        "On the night of the Sundering his oath was to keep the gates of the "
        "capital shut, and he did, while refugees begged outside. The city "
        "survived. Thousands outside it did not.",
        "His twin sister Valeria rode out against orders and saved hundreds. She "
        "was made commander; he was given a medal. He has worn the medal every day "
        "since, as a reminder.",
        "He is stern, honest to a fault and always the first to step in front of "
        "danger, as if he could stand in front of every blow he failed to take that "
        "night. The ruined knight Leoric is the only one who has ever told him he "
        "did nothing wrong. Aurelius did not believe him.",
    ),
    "scarlett.jfif": _story(
        "cogsreach",
        "The Gunpowder Darling",
        "Scarlett grew up in the steam foundries of Cogsreach, where her mother "
        "lost her hand to a machine and the baron who owned it never paid a coin. "
        "So Scarlett robbed his bank. Then she robbed it again.",
        "Her twin pistols were built by her cousin Brina out of a broken clock "
        "tower and a lot of gunpowder. She is the most wanted outlaw in the steam "
        "cities, mostly because she keeps returning the stolen money to the "
        "workers it was stolen from.",
        "The guard Dorian has been ordered to catch her nine times. Nine times he "
        "has failed, and Scarlett is fairly sure it is not because he is bad at his "
        "job. She laughs in every fight and never misses.",
    ),
    "sylva.jfif": _story(
        "sylvaran",
        "The Voice of the Old Grove",
        "Sylva grew up in a temple built inside a hollow tree, the oldest in the "
        "Sylvaran Wilds, where the priests taught her that every root in the world "
        "is connected. She can hear the earth breathing and heal the wounded by "
        "borrowing its strength.",
        "Her elder sister Elowen tends the moon-flower forest; together they "
        "raised Verdana, a baby the forest itself left in a nest of flowers. Sylva "
        "is quiet and gentle, but when the grove is threatened, the roots answer "
        "her call faster than any army.",
        "Since the Sundering the roots have been whispering something new to her: "
        "a pulse, far to the east, beating like a second heart. She is almost sure "
        "it comes from the Riftheart.",
    ),
    "rosalind.jfif": _story(
        "sylvaran",
        "The Butterfly Archer",
        "Rosalind guards the crystal groves of the elves, where butterflies carry "
        "the forest's memories from flower to flower. Her bow is made of living "
        "crystal, and her arrows bloom on impact.",
        "She and Faelyn trained together under the old marksman Thalion and have "
        "competed at everything since: archery, tracking, and who can annoy "
        "Thalion the most. Rosalind currently leads on the last one.",
        "She looks delicate, and she likes it that way. Enemies who underestimate "
        "her soon find themselves tangled in roots and stung by petals sharper "
        "than steel.",
    ),
    "thalion.jfif": _story(
        "sylvaran",
        "The Golden Leaf Marksman",
        "Thalion has guarded the edge of the Sylvaran Wilds for three centuries and "
        "has never let an arrow fly without purpose. His golden bow was shaped from "
        "the forest's oldest tree, which gave its branch willingly.",
        "He trained two great archers, Faelyn and Rosalind, and lost one great "
        "friend: a human warden named Aldric who guarded the forest's edge with "
        "him for fifty years. Aldric's grandson Rowan now carries his bow, and "
        "Thalion watches over the boy without letting him know.",
        "He is stoic, precise and fast as a gust of wind. Elven children say that "
        "if a leaf falls in Thalion's forest, he knows exactly where it landed.",
    ),
    "vesper.jfif": _story(
        "spirehollow",
        "The Masked Twilight",
        "No one knows Vesper's face, and few who have seen it lived to describe it. "
        "The assassin's daggers are forged from the shadows that fall at twilight, "
        "and they cut through spells as easily as through flesh.",
        "Vesper trained the guild enforcer Corvus, and is the only person in "
        "Spirehollow he fears. Vesper takes contracts only against those who prey "
        "on the powerless, and the latest one came from a widow in black: Morwen of "
        "the dead forest, who wants Lord Zarathor dead.",
        "Vesper has accepted. Whether this is a moral code or a personal grudge, "
        "Vesper has never said. But the mask was made in Nocthaven, and the shadows "
        "in the daggers look a great deal like the ones that follow Zarathor.",
    ),
    "pyralis.jfif": _story(
        "cinderpeak",
        "The Ember Prodigy",
        "Pyralis was six when the volcano lords burned his village, and he would "
        "have burned with it if a knight made of fire had not carried him out. He "
        "never learned the knight's name, only the legend: Ignis, guardian of the "
        "Everfire.",
        "He set his first fire at seven and his first forest at eight. The fire "
        "mages of Emberhold took him in before he could set the whole south ablaze "
        "and taught him to shape the flame instead of feeding it. His best friend, "
        "the stone-singer Torvin, keeps the lava calm whenever Pyralis forgets to.",
        "He is cocky, loud and genuinely brilliant. He wants to become the next "
        "guardian of the Everfire, and he has no idea Ignis has been watching him "
        "for years, wondering the same thing.",
    ),
    "glacius.jfif": _story(
        "hrimvald",
        "The Frostbound Squire",
        "Glacius has served Boreas as her squire for twenty years and has never seen "
        "her face. Ten years ago he fell through the ice of a frozen lake while "
        "defending a village from hollowborn, and stayed under it for a full winter. "
        "Boreas cut through the ice herself to bring him back.",
        "When he climbed out, his armor had become ice and his heart had become as "
        "calm as the deep water. He speaks rarely and moves slowly, but nothing "
        "gets past him.",
        "He is the only one who knows Boreas weeps under the helm when the wolves "
        "howl. He has never told anyone, and he never will.",
    ),
    "isolde.jfif": _story(
        "thalassar",
        "The Tidewatch Knight",
        "Isolde commands the Tidewatch, the knights who guard the coastal castles "
        "from the creatures that rise with the high tide. She built the order from "
        "nothing after the Sundering, while her elder sister Celestine took to the "
        "skies.",
        "The two love each other and argue constantly: Celestine thinks Isolde is "
        "too stubborn to ask for help, and Isolde thinks Celestine is too far away "
        "to understand the people she protects. Both are right.",
        "Her blessing comes from the sea, and she uses it to mend her knights "
        "between the waves. She never asks them to face a danger she would not "
        "face first, and the tide-witch Lunara is the only person she trusts to "
        "watch her back.",
    ),
    "elowen.jfif": _story(
        "sylvaran",
        "The Night-Blooming Healer",
        "Elowen tends the moon-flower forest of Lirael, where flowers bloom only "
        "under the moon. She knows the name of every plant, and every plant knows "
        "hers, which is why the forest grows paths for her that it hides from "
        "everyone else.",
        "One spring night she found a baby sleeping in a nest of flowers and "
        "raised her with her sister Sylva; the baby was Verdana. Years later she "
        "took on a young herbalist, Liesel, as her apprentice.",
        "Her golden staff carries the forest's life into battle, closing wounds and "
        "calming fears. She smiles often, and her smile is said to be the best "
        "medicine she has.",
    ),
    "hayato.jfif": _story(
        "hoshigane",
        "The Blade of Falling Petals",
        "Hayato trained at the Temple of a Thousand Lanterns, where students learn "
        "to cut a cherry petal in half before it touches the ground. He was the "
        "first in a century to cut it into four.",
        "He met Kaito when both were twelve, in a duel that ended in a draw and a "
        "lifelong rivalry. His younger brother Ryuji has never been able to cut a "
        "single petal, and Hayato secretly envies him for having the courage to "
        "fight with his fists instead.",
        "His katana carries the wind of the mountain passes, and he fights with a "
        "calm that unsettles his enemies. He believes a duel is won in the breath "
        "before the first strike.",
    ),
    "maren.jfif": _story(
        "thalassar",
        "The Tidal Spellbreaker",
        "Maren was the most brilliant student of the storm tower of Voltaris, in "
        "Cogsreach, until she discovered how easily spells could be unraveled and "
        "started unraveling her master's. Expelled, she left with her staff and a "
        "library's worth of secrets. Her friend Ophira still writes to her.",
        "She settled on the Thalassar Coast, where the drowned temples are full of "
        "old wards that need breaking and old curses that need lifting. Isolde's "
        "Tidewatch hires her more often than either of them admits.",
        "She fights by twisting her enemies' magic like a riptide, turning their "
        "strength against them. Few mages want to duel her twice.",
    ),
    "fenric.jfif": _story(
        "hrimvald",
        "The Wolf Without a Pack",
        "Fenric was born in Hrimvald under a black moon, half man and half wolf, a "
        "child of the wind-wolf pack that lost its leader, Hrimfang, on the night "
        "of the Sundering. The pack blamed his strange birth for their bad luck and "
        "cast him out.",
        "He went south into the Sylvaran Wilds and made the dark woods his home, "
        "learning to shoot arrows that glow with green spirit-fire. The shaman "
        "Tavik and his spirit-wolf Kesh are the closest thing to family he has.",
        "His howl carries far on cold nights, far enough to reach the Frostgate. "
        "The knight who holds it, Boreas, carries the last of Hrimfang's strength. "
        "Fenric does not know that she has been looking for him for twenty years.",
    ),
    "faelyn.jfif": _story(
        "sylvaran",
        "The Wind-Leaf Ranger",
        "Faelyn is the scout the elves send when they want something found and not "
        "seen. She moves through the forest like a falling leaf and fires arrows "
        "that curve on the wind to strike from impossible angles.",
        "She trained under Thalion alongside Rosalind, and the two have been rivals "
        "and best friends ever since. She also grew up with Lyra, and still has not "
        "forgiven her for climbing to the sky without saying goodbye.",
        "She enjoys leading enemies in circles until they are lost, tired and "
        "convinced the forest itself is mocking them. In a way, it is.",
    ),
    "amethia.jfif": _story(
        "nocthaven",
        "The Starlit Librarian",
        "Amethia catalogs spells the way other librarians catalog books, and she "
        "has never lost a single one. She guards the Warden Archive of Nocthaven, "
        "the library Malachar left behind, including the dangerous shelves that "
        "read their readers back.",
        "She is the younger sister of the sorceress Nocturna, and the two have not "
        "spoken since Nocturna left the archive to serve Zarathor. Amethia "
        "sends her a letter every year anyway. None have been answered, but none "
        "have been returned either.",
        "She is gentle, patient and very hard to anger, which makes it all the more "
        "terrifying when she finally opens one of those books in battle.",
    ),
    "valeria.jfif": _story(
        "aurelian",
        "The Radiant Commander",
        "On the night of the Sundering, Valeria disobeyed the order to keep the "
        "capital's gates shut and rode out with forty knights to save the refugees "
        "outside. She brought back hundreds. Her twin brother Aurelius stayed and "
        "held the gate, as ordered.",
        "She was made commander of the Order of the Sunlit Shield for it, and she "
        "has never stopped trying to convince her brother that both of them did "
        "the right thing. Her runed sword shines brighter the more injustice it faces.",
        "She is demanding, fearless and fair. Her soldiers would follow her "
        "anywhere, and they often have to, because she always charges first.",
    ),
    "stellara.jfif": _story(
        "skyspire",
        "The Comet Huntress",
        "Stellara serves the Celestial Order of the Skyspire, catching falling stars "
        "before they crash into the world. Her golden bow fires arrows of pure light "
        "that can bring down a comet.",
        "Most of the stars she catches were fired by Lyra, who thinks this is "
        "hilarious. Stellara does not. She has, however, noticed that Lyra's stars "
        "only fall when a crack in the sky widens, and she has started to wonder "
        "whether they are falling, or being pulled.",
        "Her arrows also heal: a light arrow that strikes an ally restores what the "
        "darkness took from them. She never hesitates and never misses her mark.",
    ),
    "morwen.jfif": _story(
        "nocthaven",
        "The Widow of the Dead Forest",
        "Morwen's forest died the night her betrothed, Edric, was taken by "
        "Zarathor's horned shadow. She followed it into the dark, and when she came "
        "back her hair had turned silver and burning ghosts followed her like a "
        "bridal train.",
        "She has sworn to kill Zarathor and has hired the assassin Vesper to help. "
        "Ravenna, the guide of souls, has told her Edric's soul is still trapped in "
        "the shadow, which is why Morwen has never let Vesper strike.",
        "She curses those who prey on the weak and steals their strength for "
        "herself. She has not smiled since that night, but the ghosts around her "
        "seem to smile for her.",
    ),
    "kage.jfif": _story(
        "hoshigane",
        "The Blue Flame in the Dark",
        "Kage was raised by the Kurokage, the shadow clan of Hoshigane, and trained "
        "to fight without being seen. He was a child when the clan burned the "
        "Tonbo castle; he remembers a boy hiding in a well, and he remembers not "
        "telling anyone.",
        "Years later he broke the clan's only rule when he lit his fists with blue "
        "spirit-fire to save a stranger, and he has been a fugitive ever since. The "
        "stranger was Kaito, the boy from the well.",
        "He no longer hides in the dark; he carries his own light into it. He has "
        "saved Kaito twice now, and he is running out of reasons not to tell him "
        "the truth.",
    ),
    "odette.jfif": _story(
        "thalassar",
        "The Puppeteer of Tides",
        "Odette's puppets dance with strings made of seawater, and her performances "
        "made her the most beloved artist of the harbor town of Merrow. Her "
        "favorite puppet, Colette, was carved from driftwood that washed ashore "
        "from Celestine's sunken temple.",
        "Colette sometimes moves on its own, and on stormy nights it sings hymns no "
        "one in Merrow has heard in twenty years. Odette insists this is normal. "
        "Celestine, who heard it sing once, went very quiet and flew away.",
        "In battle, the strings of Odette's magic mend her allies as gently as she "
        "repairs her dolls.",
    ),
    "nocturna.jfif": _story(
        "nocthaven",
        "Mistress of the Violet Sigil",
        "Nocturna left the Warden Archive, and her sister Amethia, to become Lord "
        "Zarathor's advisor and, for a time, much more. She left him too, the night "
        "his horned shadow spoke to her in his voice.",
        "She leads a coven now, in a gothic chamber where candles burn with violet "
        "flame. Her sigils can silence a storm or open a door to places that should "
        "stay closed. She keeps every letter Amethia has sent her, unopened, in a "
        "locked drawer.",
        "She is polite, amused and utterly confident. Rival sorcerers who visit her "
        "chamber often leave a little less powerful than they arrived, and "
        "Zarathor, it is said, still visits once a year, and leaves without a word.",
    ),
    "eldric.png": _story(
        "ironfang",
        "The Rune-Serpent Scholar",
        "Eldric spent ten years in a windowless library in the Ironfang Highlands, "
        "translating the runes that appeared in the mountains after the Sundering. "
        "When he spoke the last word, the runes rose from the page and coiled into "
        "a serpent of blue light that has followed him ever since.",
        "The silver in his hair came from that night. So did a terrible suspicion: "
        "the runes are the Hollow's own writing, and the same runes glow on the axe "
        "of Gorvane, the warlord who cannot die.",
        "He follows Gorvane from battle to battle, taking notes. Gorvane tolerates "
        "him, mostly because Eldric is the only one who has ever promised to find "
        "a way for him to rest.",
    ),
    "ravenna.png": _story(
        "nocthaven",
        "The Raven of the Last Rites",
        "Ravenna performs the last rites in the graveyard of Duskmere, guiding souls "
        "that cannot find their way. Her raven, burning with violet fire, carries "
        "the messages the dead cannot deliver themselves.",
        "She believes Malachar's tome is a prison, and that the souls inside it "
        "deserve to move on, whatever waits beyond. Malachar believes she will feed "
        "them to the Hollow. They have argued about it for twenty years, and they "
        "are the only two people in Nocthaven who truly understand each other.",
        "She is kind to spirits and cruel to the living who disturb them. She has "
        "told Morwen that Edric's soul is still trapped in Zarathor's shadow, and "
        "she has promised to guide it home.",
    ),
    "cassius.png": _story(
        "aurelian",
        "The Hammer of the Mountain Temple",
        "Cassius was a stonemason who rebuilt the temple of Solmarr with his own "
        "hands after the Sundering shattered it, because a young priestess was "
        "praying in the rubble and nobody else would help her. When the last stone "
        "was set, the sun blessed his hammer and crowned him with light.",
        "That priestess was Solara, and he has guarded her temple ever since. He "
        "still fights like a builder: steady, careful and impossible to move.",
        "Where Cassius plants his feet, the ground itself seems to stand with him. "
        "He has turned down three knighthoods. He says he already has a job.",
    ),
    "nyra.jfif": _story(
        "spirehollow",
        "The Claw of the Moonlit Roofs",
        "Nyra hunts the thieves who hunt Spirehollow. From the rooftops she watches "
        "every alley, and her steel claws have ended the careers of more criminals "
        "than the city guard ever has.",
        "She used to be one of them. She and Lucan were the best pair of thieves in "
        "the city until a job went wrong and a child got hurt. She quit that night; "
        "Lucan did not. They have been dancing around each other on the rooftops "
        "ever since.",
        "She keeps a special eye on a young pickpocket named Jory, who reminds her "
        "of herself. Those she protects leave small offerings of bread on the "
        "rooftops. She always takes them.",
    ),
    "dorian.jfif": _story(
        "cogsreach",
        "The Clockwork Dragoon",
        "As a lonely boy in Brasshelm, Dorian watched a silver storm dragon fly over "
        "the city walls with a rider on its back. He spent the next five years "
        "building a dragon of his own out of scrap and captured lightning, and "
        "named it Spark.",
        "Now he guards the walls of Brasshelm with Spark at his side and a "
        "crackling glaive in his hands. The barons have ordered him to catch the "
        "outlaw Scarlett nine times. He has failed nine times, very carefully.",
        "His one dream is to meet the dragon rider from his childhood. He does not "
        "know her name is Kyrielle, or that she would love to meet Spark.",
    ),
    "grizelda.jfif": _story(
        "greenhollow",
        "The Witch of the Mirewood",
        "Grizelda has lived in the Mirewood swamp, at the edge of Greenhollow Vale, "
        "for longer than anyone can remember, possibly since before the Seven "
        "Wardens. She brews potions nobody should drink and cackles at jokes "
        "nobody else understands.",
        "Her constant companion is Blub, a slime with too many eyes and a great "
        "deal of enthusiasm. Last spring Blub budded a little blue slime that "
        "bounced away into the meadows and adopted a shepherd boy named Wren. "
        "Grizelda pretends not to care. She checks on them every week.",
        "She sells rare mushrooms to the alchemist Silas, and she is the only "
        "person in Greenhollow who knows what the Mystic Box really is. When asked, "
        "she just laughs and says she told the Wardens it was a bad idea.",
    ),
    "ophira.jfif": _story(
        "cogsreach",
        "The Lightning Archivist",
        "Ophira keeps the storm archives of the tower of Voltaris, where each book "
        "holds a lightning bolt captured in its pages. The steam cities of "
        "Cogsreach run on the storms she releases, and she knows exactly which "
        "storm to release and when.",
        "She studied alongside Maren, the spellbreaker, and was the only student "
        "who stood up for her when she was expelled. They still write to each "
        "other every month.",
        "She is calm, precise and rarely raises her voice. She has never needed to: "
        "when Ophira opens a book, the thunder speaks for her.",
    ),
    "verdana.jfif": _story(
        "sylvaran",
        "The Moss-Clad Shepherd",
        "Verdana was found as a baby in a nest of flowers in the forest of Mossdeep, "
        "and raised by the sisters Elowen and Sylva. The elves say the forest "
        "itself gave birth to her in the spring after the Sundering, to replace "
        "what it had lost.",
        "Her armor is woven bark and living moss, and her crook guides lost animals "
        "and travelers home. Her companion, Puff, is a glowing ball of fluff that "
        "heals anyone who pets it.",
        "Verdana says Puff is the most powerful creature in the forest. Given that "
        "even Fenric becomes gentle when Puff sits on his lap, she may be right.",
    ),
    "tavik.jfif": _story(
        "sylvaran",
        "The Spirit-Wolf Wanderer",
        "Tavik walked into the Twilight Woods on his coming-of-age hunt and came "
        "out a week later with a wolf made of starlight. The elders say the "
        "spirit-wolf Kesh chose him, not the other way around.",
        "Kesh is the spirit of a wind-wolf pup from Hrimvald that died in the "
        "Sundering, and it led Tavik to an outcast half-wolf named Fenric, who "
        "has hunted beside them ever since.",
        "Tavik and Kesh travel, hunt and fight together. When Tavik's spear strikes, "
        "Kesh's lightning-fast jaws are never far behind, and lately Kesh keeps "
        "turning north, howling toward the Frostgate.",
    ),
    "lucan.jfif": _story(
        "spirehollow",
        "The Rooftop Scoundrel",
        "Lucan steals from nobles, lies to guards and flirts with everyone, all with "
        "the same crooked smile. His daggers trail black smoke, a gift from a "
        "shadow-imp named Grit that he won in a card game against Mortis, who "
        "claims he let him win.",
        "He and Nyra were once the best pair of thieves in Spirehollow. She quit; "
        "he did not. He tells everyone he does not miss her. Grit, perched on his "
        "shoulder, rolls its eyes every time.",
        "Together Lucan and Grit are the most annoying pair in the city, and the "
        "most effective.",
    ),
    # ---------- 3★ ----------
    "rowan.jfif": _story(
        "sylvaran",
        "The Young Forest Warden",
        "Rowan inherited his antler bow from his grandfather Aldric, the human "
        "warden who guarded the edge of the Sylvaran Wilds beside the elf Thalion "
        "for fifty years. With the bow came a promise to protect the forest.",
        "He is young and takes the promise very seriously, maybe too seriously. He "
        "has never met Thalion, and he has no idea the elf has saved his life at "
        "least six times from a distance.",
        "He stands between the woods and anyone who would harm them, and the forest "
        "stands behind him.",
    ),
    "corvus.jfif": _story(
        "spirehollow",
        "The Crow Among Thieves",
        "Corvus never shows his face and never gives his real name. He is the "
        "enforcer of the Spirehollow thieves' guild, and the guild is a little "
        "afraid of him. He is afraid of only one person: Vesper, who trained him.",
        "He fights dirty, with poisoned daggers and tricks in the dark, and he has "
        "no shame about it. Honor, he says, is for people who can afford to lose.",
        "The guild has ordered him to bring Nyra down. He has been finding reasons "
        "to delay for a year.",
    ),
    "tobin.jfif": _story(
        "greenhollow",
        "The Farm Boy With a Big Sword",
        "Tobin found a rusty sword in his family's barn in Greenhollow and decided "
        "he was destined to be a hero. The sword is too big for him. The destiny "
        "might be too.",
        "What Tobin does not know is that the sword is one of the twelve lost "
        "blades of the Lion Order, and that the last Lion knight, Leoric, has "
        "already come to the village twice to watch him train with it.",
        "He is terrified of almost everything, but he never runs away. The chickens "
        "of his village, at least, consider him a legend.",
    ),
    "garrick.jfif": _story(
        "ironfang",
        "The Shieldbearer Who Walked Away",
        "Garrick carried the shield of Gorvane, the Ironfang warlord, for fifteen "
        "years. After Gorvane's fourth death and fourth return, Garrick looked into "
        "his chieftain's eyes, did not recognize the man inside, and left.",
        "Now he guards caravans through the mountain passes and has never lost one. "
        "He has a scar for each bandit gang that tried its luck, and he always "
        "takes the first watch around the campfire.",
        "He still sends a coin each season to Brannoc, Gorvane's son, at the arena. "
        "Brannoc thinks it comes from his father. Garrick has never corrected him.",
    ),
    "maelis.jfif": _story(
        "greenhollow",
        "The Runaway Novice",
        "Maelis was a novice healer at the shelter of Ithrel, raised alongside "
        "Annelise under Seraphiel's care. When her first patient died in her arms, "
        "she ran away in the night, convinced she would never be good enough.",
        "She hides now in the taverns of Greenhollow, her staff under her cloak. "
        "Annelise writes her a letter every week, asking her to come home. Maelis "
        "reads each one a hundred times and never answers.",
        "But whenever someone gets hurt, she is the first to kneel beside them, "
        "tears in her eyes and healing light in her hands. She is braver than she "
        "thinks.",
    ),
    "jory.jfif": _story(
        "spirehollow",
        "The Pickpocket With a Conscience",
        "Jory steals coin purses in the taverns of Spirehollow to feed his two "
        "younger sisters, and he feels terrible about it every single time. He is "
        "also very bad at hiding how guilty he looks.",
        "The swindler Vexa uses him as a lookout. The rooftop hunter Nyra has "
        "caught him four times and let him go four times, each time with a loaf "
        "of bread and a warning.",
        "He is quick on his feet and quicker with a knife than anyone expects. A "
        "good summoner might give him a better way to earn his bread.",
    ),
    "albin.jfif": _story(
        "greenhollow",
        "The Apprentice With a Twig",
        "Albin is the apprentice of Astra, the great astrologer of the Skyspire, "
        "who took him in five years ago and has been home exactly twice since. He "
        "teaches himself from the books in her cluttered study in Greenhollow.",
        "His wand is a twig from the garden. It works anyway, mostly. He writes "
        "Astra a report every week, which she never reads, and leaves a candle "
        "burning in the window every night in case she comes back.",
        "His spells are small, but his heart is enormous, and his little sparks of "
        "light have mended more scraped knees than any archmage.",
    ),
    "brina.jfif": _story(
        "cogsreach",
        "The Tinker of the Brass Workshop",
        "Brina can fix anything with her glowing wrench, and she can break anything "
        "even faster. Her workshop in Cogsreach is full of half-finished inventions, "
        "and about a third of them are on fire at any given moment.",
        "She built the twin pistols of her cousin Scarlett, and every gadget the "
        "outlaw uses to escape the barons. Officially she has never met Scarlett.",
        "She channels the steam from her machines into scalding blasts that surprise "
        "every enemy who thought she was only a mechanic.",
    ),
    "silas.jfif": _story(
        "greenhollow",
        "The Mushroom Alchemist",
        "Silas runs a tiny alchemy shop in Greenhollow full of glowing mushrooms, "
        "bubbling flasks and potions that are labeled, he assures customers, almost "
        "correctly. Most of his rarest ingredients come from the witch Grizelda.",
        "He is curious about everything, especially things that might explode, and "
        "he is the only person in the vale who visits the Mirewood after dark on "
        "purpose.",
        "In battle, his vials are as dangerous to his enemies as they are mysterious "
        "to his friends.",
    ),
    "kael.jfif": _story(
        "spirehollow",
        "The Ruin Runner",
        "Kael explores the ruins the Sundering left behind, searching for treasure "
        "and trouble in equal measure. He usually finds more of the second, and "
        "sells the rest to Vexa in the night market of Spirehollow.",
        "He is cocky, fast and good with his twin daggers. He claims he has never "
        "met a trap he could not dodge, which is why he has so many burns.",
        "His dream is to reach the Riftheart and touch the Mystic Box. Everyone who "
        "hears this tells him he is mad. He takes it as encouragement.",
    ),
    "vexa.jfif": _story(
        "spirehollow",
        "The Lantern-Street Swindler",
        "Vexa runs a different scam on every street of the Spirehollow night "
        "market. She has sold the same bridge four times, and each buyer thanked "
        "her for the deal.",
        "She buys relics from the ruin runner Kael, uses the pickpocket Jory as a "
        "lookout and has been trying to con Lucan for years, without success, "
        "because he keeps trying to con her back.",
        "Her curved daggers come out only when the con fails, which is rare. She "
        "would rather steal your luck than your purse.",
    ),
    "torvin.jfif": _story(
        "cinderpeak",
        "The Stone-Singer",
        "Torvin grew up in the deep caverns under Cinderpeak, where the stones hum "
        "when lava flows beneath them. He learned their songs and how to make the "
        "rocks float and spin to his will.",
        "His best friend is the fire mage Pyralis, who keeps setting things on fire, "
        "and Torvin keeps singing the lava back to sleep. They argue constantly and "
        "would die for each other.",
        "Quiet and stubborn, he plants himself in front of his allies and lets the "
        "earth itself shield them.",
    ),
    "annelise.jfif": _story(
        "aurelian",
        "The Candlelight Novice",
        "Annelise was a frightened orphan when Seraphiel found her in the ruins of "
        "Ithrel. He raised her in the shelter he built there, and she now lights "
        "its candles every evening and prays for everyone who passes its doors.",
        "Her childhood friend Maelis ran away years ago. Annelise writes her a "
        "letter every week and leaves a bed made for her, just in case.",
        "Her staff shines with a soft silver light that soothes pain and fear. She "
        "is still a novice, but the people of Ithrel already call her a saint.",
    ),
    "brannoc.jfif": _story(
        "ironfang",
        "The Arena Brawler",
        "Brannoc is the son of Gorvane, the warlord who cannot die. He has fought "
        "in the arenas of the Ironfang Highlands for twenty years to prove he is "
        "nothing like his father, and every scar on his face is a story.",
        "He fights with his fists and a spiked gauntlet, never with an axe. Every "
        "season a coin arrives for him with no name on it, and he believes it comes "
        "from his father. It comes from Garrick.",
        "He stands in front of his friends like a wall that happens to punch back.",
    ),
    "ryuji.jfif": _story(
        "hoshigane",
        "The Iron-Fist Disciple",
        "Ryuji is the younger brother of the swordsman Hayato. He could never cut a "
        "single cherry petal, so he left the Temple of a Thousand Lanterns and "
        "joined a dojo of fist fighters, to his family's horror.",
        "He trains from dawn to dusk, punching wooden posts until his knuckles "
        "bleed. His master says he has more stubbornness than talent. Ryuji says "
        "that is the same thing.",
        "His fists strike like a gale, and his scars prove he has never backed down "
        "from a fight. He has no idea his famous brother is proud of him.",
    ),
    "liesel.jfif": _story(
        "sylvaran",
        "The Fox-Fire Herbalist",
        "Liesel gathers herbs in the misty forests of the Sylvaran Wilds as the "
        "apprentice of the healer Elowen, and bandages any creature she finds hurt.",
        "One of them was a fox with a tail of fire, far from its home in Cinderpeak, "
        "and it never left her side after she healed it. She named it Ember.",
        "Ember fights fiercely for the girl who saved it, while Liesel watches from "
        "behind with her staff and a nervous smile.",
    ),
    "wren.jfif": _story(
        "greenhollow",
        "The Meadow Boy and His Slime",
        "Wren was herding sheep in the hills of Greenhollow when a little blue slime "
        "bounced out of the grass and refused to leave. He named it Bloop, and they "
        "have been inseparable ever since.",
        "Bloop is a runaway bud of Blub, the many-eyed slime of the witch Grizelda, "
        "who visits every week pretending to be passing by.",
        "Wren is no great mage, but his simple staff and Bloop's bouncy enthusiasm "
        "have surprised more than one overconfident enemy.",
    ),
}

# Laços: (carta A, carta B, o que A pensa de B, o que B pensa de A).
BONDS = [
    # Nocthaven
    ("malachar.jfif", "mortis.jfif",
     "Pulled him from his grave. Regrets it daily.",
     "His master and his favorite joke. Only Mortis may laugh at him."),
    ("malachar.jfif", "zarathor.jfif",
     "A fool who wants to open the Box all the way.",
     "A coward who opened the Box and then feared it."),
    ("malachar.jfif", "ravenna.png",
     "She would free the souls he guards, and let the Hollow eat them.",
     "He keeps the dead in a cage and calls it mercy."),
    ("malachar.jfif", "uriel.jfif",
     "The angel who warned him. Its pity is unbearable.",
     "Uriel does not hate him. Uriel pities him."),
    ("malachar.jfif", "amethia.jfif",
     "The keeper of his old archive. He trusts her with his secrets.",
     "She guards his books, and the guilt written in their margins."),
    ("zarathor.jfif", "nocturna.jfif",
     "His former advisor and lost love. He still visits.",
     "She left him the night his shadow spoke in his voice."),
    ("zarathor.jfif", "morwen.jfif",
     "His shadow took her betrothed. He knows she is coming.",
     "She has sworn to kill him."),
    ("zarathor.jfif", "vesper.jfif",
     "The assassin hired to kill him. He is waiting.",
     "The target of a contract. Perhaps a personal one."),
    ("nocturna.jfif", "amethia.jfif",
     "Her younger sister. Keeps every letter, unopened.",
     "Her elder sister. Writes to her every year."),
    ("morwen.jfif", "vesper.jfif",
     "The assassin she hired, and has never let strike.",
     "A client whose grief Vesper understands."),
    ("morwen.jfif", "ravenna.png",
     "Promised to guide Edric's soul home.",
     "A widow whose betrothed is still trapped in the dark."),
    ("mortis.jfif", "lucan.jfif",
     "Lost the imp Grit to him at cards. On purpose, he claims.",
     "Won Grit from him in a card game. Probably."),
    # Céu, ilhas e dragões
    ("uriel.jfif", "elysia.jfif",
     "Anchored her drifting cathedral. They greet every dawn together.",
     "The angel who caught her cathedral. She sings beside it every dawn."),
    ("astra.jfif", "lyra.png",
     "Keeps ruining her star maps.",
     "Her favorite person to annoy."),
    ("lyra.png", "stellara.jfif",
     "Keeps the huntress very busy catching her falling stars.",
     "Catches the stars Lyra fires. Starting to suspect why they fall."),
    ("lyra.png", "faelyn.jfif",
     "Her childhood friend from the Wilds. Left without saying goodbye.",
     "Still has not forgiven her for climbing to the sky."),
    ("astra.jfif", "albin.jfif",
     "Her apprentice in Greenhollow. She keeps promising to return.",
     "His teacher, who has been home exactly twice."),
    ("draemir.jfif", "drakara.jfif",
     "His niece. He did not save her mother, and owes her an apology.",
     "The uncle who did not fly south when her mother needed him."),
    ("draemir.jfif", "vaelora.jfif",
     "The empress whose skies host his citadel.",
     "An ancient ally who visits her court every year."),
    ("draemir.jfif", "kyrielle.jfif",
     "Her dragon Aurvex is a grandchild of his own wyrm.",
     "The sovereign watches her and Aurvex closely. Flattering, a little worrying."),
    ("vaelora.jfif", "kyrielle.jfif",
     "Captain of her sky guard and her most trusted rider.",
     "Her empress. Kyrielle would fly into any storm for her."),
    ("kyrielle.jfif", "dorian.jfif",
     "Inspired him as a child without knowing it. Wants to meet Spark.",
     "The dragon rider from his childhood. Built Spark because of her."),
    # Cinderpeak
    ("ignis.jfif", "pyralis.jfif",
     "The boy carried from the fire. Possibly the heir to the Everfire.",
     "The legend who saved him and the guardian he wants to become."),
    ("ignis.jfif", "drakara.jfif",
     "The dragon princess whose mother the volcano lords betrayed.",
     "A guardian who kept the Everfire from the traitors. An ally."),
    ("pyralis.jfif", "torvin.jfif",
     "Best friend. Keeps the lava calm when Pyralis forgets to.",
     "Best friend. Keeps setting things on fire."),
    # Hrimvald e lobos
    ("boreas.jfif", "glacius.jfif",
     "Her squire of twenty years. Cut the ice to bring him back.",
     "His knight. He has never seen her face and never will ask."),
    ("boreas.jfif", "fenric.jfif",
     "The lost son of Hrimfang's pack. She has searched for him for twenty years.",
     "The knight of the Frostgate. He does not know she is looking for him."),
    ("fenric.jfif", "tavik.jfif",
     "The closest thing he has to family.",
     "His hunting partner, led to him by Kesh."),
    ("fenric.jfif", "verdana.jfif",
     "He becomes gentle when Puff sits on his lap. He denies it.",
     "A gruff wolf with a soft heart. Puff adores him."),
    # Domínio Aureliano
    ("leoric.jfif", "tobin.jfif",
     "The boy carries a lost blade of the Lion Order. Is he worthy of it?",
     "A strange knight who keeps watching him train. Terrifying."),
    ("leoric.jfif", "aurelius.jfif",
     "Told him he did nothing wrong that night.",
     "The only one who ever forgave him. He did not believe it."),
    ("aurelius.jfif", "valeria.jfif",
     "His twin. She rode out; he held the gate.",
     "Her twin. She wants him to forgive himself."),
    ("cassius.png", "solara.jfif",
     "Rebuilt her temple stone by stone. Guards it still.",
     "The stonemason who answered her prayers with his hands."),
    ("seraphiel.jfif", "annelise.jfif",
     "The orphan he raised in the ruins of Ithrel.",
     "The guardian who raised her. Her whole world."),
    ("seraphiel.jfif", "maelis.jfif",
     "A novice who ran away. He leaves the door open for her.",
     "The mentor she is too ashamed to face."),
    ("annelise.jfif", "maelis.jfif",
     "Her childhood friend. Writes to her every week.",
     "Reads every letter a hundred times. Never answers."),
    # Costa de Thalassar
    ("celestine.png", "isolde.jfif",
     "Her sister. Too stubborn to ask for help.",
     "Her sister. Too far away to understand the people below."),
    ("celestine.png", "odette.jfif",
     "Her puppet sings the hymns of the drowned temple.",
     "A winged priestess who heard Colette sing, and flew away in silence."),
    ("lunara.jfif", "isolde.jfif",
     "The knight she trusts with the shore.",
     "The only person she trusts to watch her back."),
    ("lunara.jfif", "celestine.png",
     "Keeps the tides calm with her from above.",
     "The last tide-witch. Holds the sea together."),
    ("maren.jfif", "ophira.jfif",
     "Her friend from the storm tower. Still writes every month.",
     "The only one who stood up for her when she was expelled."),
    ("maren.jfif", "isolde.jfif",
     "The Tidewatch hires her more often than either admits.",
     "A spellbreaker she relies on for the drowned temples."),
    # Florestas de Sylvaran
    ("thalion.jfif", "faelyn.jfif",
     "His student. Fast, clever, insolent.",
     "Her teacher. She lives to annoy him."),
    ("thalion.jfif", "rosalind.jfif",
     "His student. Delicate in appearance only.",
     "Her teacher. She currently leads in annoying him."),
    ("faelyn.jfif", "rosalind.jfif",
     "Her rival and best friend.",
     "Her rival and best friend."),
    ("thalion.jfif", "rowan.jfif",
     "The grandson of his old friend Aldric. Watches over him in secret.",
     "A legendary elf he has never met."),
    ("elowen.jfif", "sylva.jfif",
     "Her younger sister, the voice of the old grove.",
     "Her elder sister, the healer of the moon flowers."),
    ("elowen.jfif", "verdana.jfif",
     "The baby she found in a nest of flowers.",
     "The woman who raised her."),
    ("sylva.jfif", "verdana.jfif",
     "The child the forest gave them.",
     "The aunt who taught her to hear the roots."),
    ("elowen.jfif", "liesel.jfif",
     "Her apprentice.",
     "Her teacher."),
    ("liesel.jfif", "pyralis.jfif",
     "Her fox Ember came from his burning homeland. They argue about it.",
     "The herbalist with a Cinderpeak fox. Ember likes him."),
    # Ironfang
    ("gorvane.jfif", "brannoc.jfif",
     "His son. Fights to be nothing like him.",
     "His father, who cannot die."),
    ("gorvane.jfif", "garrick.jfif",
     "His old shieldbearer, who walked away.",
     "The chieftain he could no longer recognize."),
    ("gorvane.jfif", "eldric.png",
     "The scholar who promised to find a way for him to rest.",
     "The warlord whose axe bears the Hollow's runes."),
    ("garrick.jfif", "brannoc.jfif",
     "Sends him a coin every season in his father's name.",
     "Thinks the coins come from his father."),
    # Spirehollow
    ("nyra.jfif", "lucan.jfif",
     "Her old partner in crime. She quit; he did not.",
     "Tells everyone he does not miss her."),
    ("nyra.jfif", "jory.jfif",
     "Reminds her of herself. Keeps letting him go.",
     "Caught him four times. Gave him bread every time."),
    ("nyra.jfif", "corvus.jfif",
     "The guild's enforcer. Strangely slow to come for her.",
     "Ordered to bring her down. Keeps finding reasons to wait."),
    ("vesper.jfif", "corvus.jfif",
     "A former student.",
     "The only person he fears."),
    ("vexa.jfif", "jory.jfif",
     "Her lookout.",
     "His employer. He is not sure she is a good influence."),
    ("vexa.jfif", "kael.jfif",
     "Buys his relics. Underpays him.",
     "Sells her his relics. Knows she underpays him."),
    ("vexa.jfif", "lucan.jfif",
     "Has tried to con him for years.",
     "Has tried to con her back for years."),
    # Cogsreach
    ("scarlett.jfif", "brina.jfif",
     "Her cousin and secret gunsmith.",
     "Her cousin. Officially they have never met."),
    ("scarlett.jfif", "dorian.jfif",
     "The guard who has failed to catch her nine times. Not by accident.",
     "The outlaw he has very carefully failed to catch."),
    # Hoshigane
    ("kaito.jfif", "hayato.jfif",
     "His rival and closest friend.",
     "His rival and closest friend."),
    ("kaito.jfif", "kage.jfif",
     "A stranger who saved his life twice.",
     "The boy from the well. He owes him the truth."),
    ("hayato.jfif", "ryuji.jfif",
     "His younger brother. Secretly proud of him.",
     "His famous elder brother. Thinks he is a disappointment to him."),
    # Greenhollow
    ("grizelda.jfif", "wren.jfif",
     "Her slime's runaway bud adopted him. She checks on them weekly.",
     "A strange old lady who is always passing by."),
    ("grizelda.jfif", "silas.jfif",
     "Her best customer for rare mushrooms.",
     "Supplier of his rarest ingredients. Slightly terrifying."),
]


# Rivalidades: quem não pode ver o outro do lado oposto de uma batalha. Cada
# entrada: (a, b, o que a diz ao encontrar b, o que b responde).
RIVALRIES = [
    ("malachar.jfif", "zarathor.jfif",
     "You would open the Box all the way? Then you will have to go through me.",
     "The coward who opened it and then wept. Step aside, old man."),
    ("zarathor.jfif", "morwen.jfif",
     "You came, Morwen. I hoped you would.",
     "For Edric. Whatever you did to him."),
    ("vesper.jfif", "zarathor.jfif",
     "The contract is signed. So is my own name, in your shadow.",
     "My own conscience, come to collect. I have been waiting."),
    ("uriel.jfif", "malachar.jfif",
     "I gave you the key. Let me carry the rest of it.",
     "Keep your pity, angel. It burns worse than the Hollow."),
    ("ignis.jfif", "drakara.jfif",
     "Not like this, little flame. Not against you.",
     "You carry my family's fire, knight. Tell me why, or burn."),
    ("gorvane.jfif", "brannoc.jfif",
     "Show me you can do it, boy. The fifth time will not wait.",
     "Not today, father. I am not ready to keep that promise."),
    ("lyra.png", "faelyn.jfif",
     "I wrote you a sky full of stars, you know.",
     "You left without saying goodbye. Draw your bow."),
    ("nyra.jfif", "corvus.jfif",
     "Slow again tonight, enforcer?",
     "Lower your blade. Please. Just this once."),
    ("aurelius.jfif", "valeria.jfif",
     "Still riding off alone, sister?",
     "Still hiding behind gates, brother?"),
    ("kaito.jfif", "hayato.jfif",
     "Our hundredth duel.",
     "And the first one either of us can lose."),
    ("maren.jfif", "ophira.jfif",
     "You are holding that tower up alone. Let me help or let me win.",
     "You broke it. Do not pretend you came to fix it."),
    ("scarlett.jfif", "dorian.jfif",
     "Tenth try, Dorian?",
     "Ten is a nice round number to finally catch you."),
    ("seraphiel.jfif", "uriel.jfif",
     "You have been searching for this light. It is in me.",
     "I know. I was hoping you would say it first."),
    ("eldric.png", "grizelda.jfif",
     "The serpent told me your name, Warden.",
     "Then it told you why I walked away. Mind your runes, boy."),
    ("vexa.jfif", "lucan.jfif",
     "Fifty gold says you lose.",
     "Make it a hundred. I will pay you in IOUs."),
    ("celestine.png", "odette.jfif",
     "Give her back. She was the goddess of my temple.",
     "She chose to leave. I only listened."),
]

# Ressonância de região: um time com as 3 cartas da mesma região ganha o efeito
# dela no começo da batalha (aplicado em battle.py). Efeitos:
#   ("team_status", status, turnos[, fração da vitalidade máx. para o escudo])
#   ("foe_status", status, turnos)
#   ("stat", atributo, fração extra)
#   ("aether", quantidade)
REGION_RESONANCES = {
    "hrimvald": {
        "name": "Frostgate Howl",
        "description": "The wind-wolves howl: every foe starts Slowed for 2 turns.",
        "effects": [("foe_status", "slow", 2)],
    },
    "zephyrine": {
        "name": "Tailwind",
        "description": "The isles' winds carry the team: +20% celerity.",
        "effects": [("stat", "celerity", 0.2)],
    },
    "nocthaven": {
        "name": "Grave Chill",
        "description": "The cold of the crypts seeps in: every foe starts Weakened for 2 turns.",
        "effects": [("foe_status", "weaken", 2)],
    },
    "skyspire": {
        "name": "Starlit Ward",
        "description": "Starlight wraps the team in a shield worth 15% of max vitality.",
        "effects": [("team_status", "shield", 3, 0.15)],
    },
    "greenhollow": {
        "name": "Hearth and Harvest",
        "description": "A taste of home: the team starts with Regen for 3 turns.",
        "effects": [("team_status", "regen", 3)],
    },
    "sylvaran": {
        "name": "Rootbound",
        "description": "The roots lend their strength: +12% vitality.",
        "effects": [("stat", "vitality", 0.12)],
    },
    "aurelian": {
        "name": "Lion's Oath",
        "description": "Shields locked like the old Order: +12% bulwark and resolve.",
        "effects": [("stat", "bulwark", 0.12), ("stat", "resolve", 0.12)],
    },
    "hoshigane": {
        "name": "First Petal",
        "description": "The first cut decides the duel: the team starts Empowered for 2 turns.",
        "effects": [("team_status", "empower", 2)],
    },
    "spirehollow": {
        "name": "Rooftop Ambush",
        "description": "Strike from the shadows: every foe starts Exposed for 2 turns.",
        "effects": [("foe_status", "expose", 2)],
    },
    "ironfang": {
        "name": "Clan Fury",
        "description": "The war drums of the clans: +15% might.",
        "effects": [("stat", "might", 0.15)],
    },
    "thalassar": {
        "name": "Tide Hymn",
        "description": "The drowned temples sing along: +15% arcana.",
        "effects": [("stat", "arcana", 0.15)],
    },
    "cinderpeak": {
        "name": "Everfire Spark",
        "description": "The mountain's flame burns in the team: +3 starting Aether.",
        "effects": [("aether", 3)],
    },
    "cogsreach": {
        "name": "Overclock",
        "description": "Gears spin up: +2 starting Aether and +10% celerity.",
        "effects": [("aether", 2), ("stat", "celerity", 0.1)],
    },
}

# Elemento e boato ("whisper") de cada região: o que se ouve por lá hoje.
REGION_FLAVOR = {
    "riftheart": (None, "On quiet nights the Box hums a lullaby. Grizelda says she taught it to the Wardens."),
    "hrimvald": ("tide", "The wind-wolves are howling south again. Boreas has started answering."),
    "zephyrine": ("gale", "The isles drift a little closer to the Riftheart every year. The empress says it is the wind."),
    "nocthaven": ("umbra", "A raven of violet fire has been seen perched on Malachar's window, and he has not chased it away."),
    "skyspire": ("lumen", "Elysia has stopped singing. The astrologers say the stars have started singing instead."),
    "greenhollow": ("terra", "A candle burns every night in the window of an empty study, waiting for an astrologer to come home."),
    "sylvaran": ("terra", "The roots beat like a second heart, and the girl the forest gave birth to can feel it."),
    "aurelian": ("lumen", "A golden knight visits the ruins of Ithrel every month, leaves alms at the door and never gives his name."),
    "hoshigane": ("gale", "A fugitive of the shadow clan was seen saving the last dragonfly swordsman. Again."),
    "spirehollow": ("umbra", "The guild's enforcer has been ordered to bring down the rooftop hunter. He keeps losing her trail. On purpose."),
    "ironfang": ("terra", "The warlord who cannot die has died a fourth time. The clans are counting, and so is his son."),
    "thalassar": ("tide", "A puppet in Merrow sings hymns no one has sung since the temples drowned."),
    "cinderpeak": ("ember", "The stones under the volcano are singing a warning: the Everfire is about to change hands."),
    "cogsreach": ("volt", "The storm tower of Voltaris is failing, and only one archivist is holding it together."),
}

for _region_entry in REGIONS:
    _element, _whisper = REGION_FLAVOR[_region_entry["id"]]
    _region_entry["element"] = _element
    _region_entry["whisper"] = _whisper

# Crônica: a linha do tempo de Aethra, da mais antiga à mais recente.
CHRONICLE = [
    {
        "era": "Before memory",
        "title": "The Aetherwell",
        "text": "Aethra is one land, warmed by the spring of living magic. Uriel stands "
        "at the Gate of Dawn, and the dragons drink from the Sunwell.",
    },
    {
        "era": "The Age of Wardens",
        "title": "The forging of the Box",
        "text": "Seven Wardens forge the Mystic Box to lock away the Hollow. One of them "
        "walks out before it is finished, calling it a bad idea. Uriel keeps the key.",
    },
    {
        "era": "A generation ago",
        "title": "The plague of Nocthaven",
        "text": "A plague sweeps through Nocthaven. Malachar, the last Warden, searches "
        "every forbidden book for a cure, and every book points to the Box.",
    },
    {
        "era": "The night of the Sundering",
        "title": "The world breaks",
        "text": "Malachar opens the Box. The Hollow breathes out and Aethra cracks into "
        "the Shattered Realms. Ignis swallows the Everfire, Leoric holds the cathedral "
        "doors, Valeria rides out while Aurelius holds the gate, Vaelora lifts the "
        "western hills into the sky, and a star falls into a cradle in Greenhollow.",
    },
    {
        "era": "The long night",
        "title": "Betrayals and vows",
        "text": "The volcano lords betray the dragon-queen of Cinderpeak, and Draemir "
        "does not fly south. Zarathor gives his shadow away to save his city. The "
        "Tonbo castle burns in Hoshigane.",
    },
    {
        "era": "The rebuilding",
        "title": "What was saved",
        "text": "Cassius rebuilds the temple of Solmarr, Isolde founds the Tidewatch, "
        "Seraphiel opens the shelter of Ithrel and the steam cities of Cogsreach rise "
        "from the ruins.",
    },
    {
        "era": "Now",
        "title": "The calling",
        "text": "The Box begins to call champions from every realm and bind them into "
        "cards for the summoners it chooses. You are one of them.",
    },
]

# Capítulo secreto de cada carta: o título aparece sempre; o texto só depois
# de ascender a carta até SECRET_UNLOCK_ASCENSION.
SECRET_UNLOCK_ASCENSION = 1

# Última fala de cada carta quando cai em batalha. Só aparece depois que o
# dono ascende a carta (SECRET_UNLOCK_ASCENSION), porque ecoa o capítulo secreto.
LAST_WORDS = {
    # Hrimvald
    "boreas.jfif": "Fenric... the wind is yours now. Run with it.",
    "glacius.jfif": "I never asked to see your face, my lady. I never needed to.",
    "fenric.jfif": "The pack... is still sleeping. Someone wake them.",
    # Zephyrine
    "vaelora.jfif": "Keep smiling, Lirien. Do not let them see the isles drift.",
    "draemir.jfif": "Ysmera... I am giving your heartbeat back.",
    "kyrielle.jfif": "Aurvex, not yet. The lid can wait one more dream.",
    # Nocthaven
    "malachar.jfif": "Lira... forgive your father. I could not let you go.",
    "mortis.jfif": "Funny. It finally landed.",
    "zarathor.jfif": "Edric... I almost had your hand.",
    "amethia.jfif": "The torn page... someone must find the torn page.",
    "morwen.jfif": "Edric, you chose to go. Let me choose to follow.",
    "nocturna.jfif": "Tell my sister... I opened one letter. Just one.",
    "ravenna.png": "Lira, fly to your father. It is time he knew.",
    # Skyspire
    "astra.jfif": "The map is almost finished. Do not let the stars go out.",
    "elysia.jfif": "The last verse... I almost remembered it.",
    "uriel.jfif": "I gave him the key. Let this be my share of the price.",
    "lyra.png": "Astra... it was my arrow. Your star was my fault.",
    "stellara.jfif": "Throw the stars back, Lyra. Stitch the sky closed.",
    # Greenhollow
    "grizelda.jfif": "A lock only teaches the Hollow to wait. Remember that.",
    "tobin.jfif": "I did not run, grandpa. I did not run.",
    "maelis.jfif": "I will read the rest of the letter. I promise.",
    "albin.jfif": "Tell my teacher... I kept every report in order too.",
    "silas.jfif": "Worth it. The mushrooms were worth it.",
    "wren.jfif": "Bloop, invite her to dinner. She should not eat alone.",
    # Sylvaran
    "sylva.jfif": "Verdana... the second heart. You have to know.",
    "rosalind.jfif": "Faelyn, she did say goodbye. To me. I am sorry.",
    "thalion.jfif": "Late again... no. Not this time.",
    "elowen.jfif": "The moon flowers... someone water them for me.",
    "faelyn.jfif": "I counted every one of your stars, Lyra.",
    "verdana.jfif": "Puff, plant me somewhere the world can heal.",
    "tavik.jfif": "Go north, Kesh. That is what family does.",
    "rowan.jfif": "Tell the elf... it was not his fault.",
    "liesel.jfif": "Ember, go to him. He is the one you were looking for.",
    # Aurelian
    "seraphiel.jfif": "Take the light back, Uriel. Ithrel will find its own.",
    "leoric.jfif": "The boy is worthy. The old man's fear ends with me.",
    "solara.jfif": "I can hear the hammer... keep hammering, Cassius.",
    "aurelius.jfif": "Annelise... the golden knight was me.",
    "valeria.jfif": "Father, we both only wanted you to be proud.",
    "cassius.png": "Follow the grooves in the floor, Solara. I carved them for you.",
    "annelise.jfif": "Golden knight, wherever you are, I never blamed you.",
    # Hoshigane
    "kaito.jfif": "The child from the well... I only wanted to say thank you.",
    "hayato.jfif": "I let you draw once, Kaito. Only once.",
    "kage.jfif": "Kaito... it was me at the well. It was my father.",
    "ryuji.jfif": "I cut the petal, brother. I just never told you.",
    # Spirehollow
    "vesper.jfif": "Zarathor... your conscience is tired.",
    "nyra.jfif": "Sorry, Jory. Sorry. Sorry.",
    "lucan.jfif": "Grit, you look exhausted. Was it because of me?",
    "corvus.jfif": "Nyra... it is Corin. I am sorry I waited.",
    "jory.jfif": "That voice... it was you on the rooftops.",
    "kael.jfif": "I should have read the last page.",
    "vexa.jfif": "The bridge... tell them about the people who lived on it.",
    # Ironfang
    "gorvane.jfif": "Fifth time... Brannoc, keep your promise.",
    "eldric.png": "The serpent told me her name. Grizelda... I wrote it down.",
    "garrick.jfif": "I did it for the boy. I would do it again.",
    "brannoc.jfif": "I am not ready, father. I am not ready.",
    # Thalassar
    "lunara.jfif": "Isolde, do not let me walk into the water again.",
    "celestine.png": "Colette... tell her I finally understand.",
    "isolde.jfif": "Twenty letters... someone send them to the sky.",
    "maren.jfif": "The tower, Ophira. Let me help with the tower.",
    "odette.jfif": "Colette, I never sent the letter. I am sorry.",
    # Cinderpeak
    "ignis.jfif": "My little flame... your father is still here.",
    "drakara.jfif": "Mother's egg... keep it warm. Keep it warm.",
    "pyralis.jfif": "The scar is burning... is the flame choosing me now?",
    "torvin.jfif": "I said I would be standing beside you, Pyralis.",
    # Cogsreach
    "scarlett.jfif": "Tell the baron his daughter emptied the vault.",
    "dorian.jfif": "Spark, find Ophira. She always asked about you.",
    "ophira.jfif": "Maren was right. I should have asked.",
    "brina.jfif": "The airship is almost done, cousin. Fly it without me.",
}


SECRETS = {
    # 5★
    "malachar.jfif": (
        "Lira",
        "The plague took Malachar's daughter, Lira, first. When he opened the Box, the "
        "Hollow spoke to him in her voice. Hers was the first soul he bound into the "
        "tome, and he cannot free the others because he cannot bear to free her. He "
        "does not know that Lira slipped out of the tome years ago, and now flies at "
        "Ravenna's side as a raven of violet fire.",
    ),
    "boreas.jfif": (
        "The Face Under the Helm",
        "There is no face under the helm anymore, only the amber eyes of Hrimfang. "
        "Boreas is slowly becoming the wolf she saved, and when the change is complete "
        "the wind will need a new leader. She is not searching for Fenric to rescue "
        "him. She is searching for him to give him the wind before she disappears.",
    ),
    "astra.jfif": (
        "The Star in the Cradle",
        "The star that fell into her cradle was a shard of the Mystic Box's lid, "
        "knocked loose on the night of the Sundering. That is why she can pull stars "
        "down. The map she is drawing in the sky is the shape of the missing lid, and "
        "if she ever finishes it, she could close the Box, at the cost of every star "
        "inside her.",
    ),
    "seraphiel.jfif": (
        "A Piece of the Dawn",
        "The lightning that struck Seraphiel was a shard of the shattered Gate of Dawn, "
        "the very thing Uriel has spent a generation searching for. Seraphiel has "
        "known for years. Returning it would put out his light, and with it the "
        "shelter of Ithrel. He has not decided whether that makes him selfish.",
    ),
    "ignis.jfif": (
        "The Name Beneath the Flame",
        "Before the fire, Ignis was Aldren, a human knight who married the dragon-queen "
        "Ysmera. Drakara believes her father died in the betrayal. He did not. He "
        "remembers almost nothing of his old life, only the vow and a little girl's "
        "face in the flames, and he cannot bring himself to tell her what he became.",
    ),
    "leoric.jfif": (
        "The Brother Who Fled",
        "Not every knight of the Lion Order died at Valdremont. One of them ran, "
        "carrying his blade, and hid it in a barn in Greenhollow out of shame. That "
        "knight was Tobin's grandfather. Leoric found out on his second visit, and "
        "now has to decide whether the boy will pay for the old man's fear, or redeem it.",
    ),
    "lunara.jfif": (
        "The Song That Was Not Hers",
        "The tide-witches did not drown. Their song carried them into the Box, and "
        "every full moon they sing to Lunara from inside it, asking her to finish the "
        "song and join them. Some nights she has walked all the way into the water "
        "before Isolde found her and brought her back.",
    ),
    "mortis.jfif": (
        "The Joke That Started It All",
        "Mortis found the tome that pointed Malachar to the Box in the royal vault, and "
        "gave it to him as a joke: a cure for the plague, guaranteed or your money "
        "back. He has never told anyone. Every trick, every laugh since then has been "
        "a way of not hearing the joke land.",
    ),
    "drakara.jfif": (
        "The Egg She Carries",
        "Under her armor, Drakara carries her mother's last egg, still warm after "
        "twenty years. The true heir of Cinderpeak has not hatched yet, and only the "
        "Everfire can wake it. The flame is inside Ignis, and she is beginning to "
        "suspect the knight knows exactly who she is.",
    ),
    "gorvane.jfif": (
        "What Came Back With Him",
        "Each time Gorvane returns from death, a little more of the Hollow returns with "
        "him and a little less of Gorvane. Eldric's notes predict that the fifth "
        "return will be the Hollow wearing his face. Gorvane read them, and asked his "
        "son Brannoc to be the one who stops him.",
    ),
    "elysia.jfif": (
        "The Voice That Sings Back",
        "The voice singing back from the Box is her own, from a time that has not "
        "happened yet. It sings the hymn that closes the Box, and every night it "
        "comes closer to the last verse. Elysia is silent because she is learning it, "
        "and because she suspects whoever sings it will not come back.",
    ),
    "uriel.jfif": (
        "The Keeper of the Key",
        "Uriel was never one of the Seven Wardens; Uriel was the one who held the key. "
        "When Malachar came weeping for his dying daughter, the angel gave it to him. "
        "Uriel's pity for Malachar is the shape of Uriel's own guilt.",
    ),
    "celestine.png": (
        "The Goddess in the Driftwood",
        "The tide-goddess did not fall silent. She left the drowned altar for a piece "
        "of driftwood, now a puppet called Colette in the hands of a puppeteer in "
        "Merrow. She chose an artist who listens over a priestess who stopped "
        "listening, and Celestine cannot forgive herself for understanding why.",
    ),
    "lyra.png": (
        "The First Arrow",
        "Lyra fired her first arrow on the night of the Sundering, straight into the "
        "crack in the sky. It knocked loose a shard of the Box's lid, which fell into a "
        "cradle in Greenhollow. Every joke she plays on Astra is a way of staying close "
        "to the girl she accidentally gave a falling star.",
    ),
    "zarathor.jfif": (
        "Edric",
        "Morwen's betrothed, Edric, was Zarathor's younger brother. When the shadow "
        "grew too hungry to control, Edric walked into it willingly to keep it from "
        "devouring the city. Zarathor has spent every year since trying to pull him "
        "back out, and has never told Morwen: she needs someone to hate, and better "
        "him than Edric.",
    ),
    "vaelora.jfif": (
        "The Drift",
        "The Zephyrine Isles are drifting toward the Riftheart, and Vaelora can no "
        "longer steer them away. Each year she holds the winds a little longer and "
        "smiles a little wider so her people will not notice. Only Lirien knows how "
        "tired she is.",
    ),
    "draemir.jfif": (
        "The Sunwell's Price",
        "The Sunwell keeps Draemir alive by burning a dragon's lifetime every century. "
        "Ysmera gave him hers, years before the betrayal. When she needed him, he had "
        "no strength left that was not already hers. Drakara's mother is still alive, "
        "in a way: in every beat of her uncle's heart.",
    ),
    "kyrielle.jfif": (
        "Aurvex's Dream",
        "Every night Aurvex dreams of the Box, and Kyrielle shares the dream: a silver "
        "dragon diving into the Riftheart and the lid closing behind it. She has told "
        "no one, not even the empress, afraid that saying it aloud will make it true.",
    ),
    # 4★
    "kaito.jfif": (
        "The Child in the Shadows",
        "Kaito saw someone else that night: a Kurokage child who found him in the "
        "well, looked straight at him and walked away without a word. Kaito has been "
        "searching for that child all these years, not for revenge, but to say thank you.",
    ),
    "solara.jfif": (
        "The Price of Noon",
        "Every spell burns a little of Solara's sight. She is almost blind now, and "
        "hides it behind the brightness of her staff. She walks the temple by the "
        "sound of Cassius's hammer, and he has been hammering a little louder every year.",
    ),
    "aurelius.jfif": (
        "The Child at the Gate",
        "Among the refugees Aurelius refused to let in was a little girl who looked "
        "him in the eyes as the gate closed. Years later he recognized her: Annelise, "
        "the novice of Ithrel. The golden knight who leaves alms at Ithrel's door every "
        "month and never gives his name is Aurelius.",
    ),
    "scarlett.jfif": (
        "The Baron's Daughter",
        "The baron Scarlett keeps robbing is her father. Her mother was a foundry "
        "worker he never acknowledged. Scarlett does not want his money or his name. "
        "She wants him to know, every time the vault is empty, exactly who emptied it.",
    ),
    "sylva.jfif": (
        "The Second Heart",
        "The second heart Sylva hears in the roots is Verdana's. Her niece's heartbeat "
        "is in time with the Riftheart, because the forest made Verdana from the last "
        "seed of the Aetherwell. Sylva has not told her. She is afraid of what Verdana "
        "would choose.",
    ),
    "rosalind.jfif": (
        "Lyra's Secret",
        "The night Lyra left for the sky, she said goodbye to one person: Rosalind. She "
        "made her promise not to tell Faelyn. Rosalind has kept that promise for twenty "
        "years and has hated it for every one of them.",
    ),
    "thalion.jfif": (
        "Aldric's Last Arrow",
        "Aldric died because Thalion hesitated, one breath too long, before firing. "
        "Thalion has never fired late since, and has never forgiven himself. Watching "
        "over Rowan is not a favor to an old friend. It is a debt.",
    ),
    "vesper.jfif": (
        "The Shadow's Conscience",
        "Vesper was born from Zarathor's shadow: the small part of it that remembered "
        "being a man and was horrified by what it had become. It tore itself free and "
        "put on a mask. Every tyrant Vesper kills is a message to Zarathor, and when "
        "Vesper accepted Morwen's contract, for the first time, Zarathor did not try "
        "to stop it.",
    ),
    "pyralis.jfif": (
        "The Burn Scar",
        "The burn on Pyralis's chest has the shape of a flame, and it glows when Ignis "
        "is near. The Everfire marked him the night the knight carried him out of the "
        "fire. The flame has already chosen its heir. It is waiting for Pyralis to be "
        "ready, and for Ignis to let go.",
    ),
    "glacius.jfif": (
        "What He Saw Under the Ice",
        "Under the frozen lake, Glacius saw Hrimfang's old pack sleeping in the ice, "
        "waiting for a leader with the wolf's blood. He knows the leader is Fenric, and "
        "he knows what Boreas will lose when that boy comes home.",
    ),
    "isolde.jfif": (
        "The Unsent Letters",
        "In the highest room of the Tidewatch tower, Isolde keeps twenty letters to "
        "Celestine, one for each year, all asking her to come home. She has never sent "
        "one. She is afraid her sister would say no.",
    ),
    "elowen.jfif": (
        "The Dying Flowers",
        "The moon flowers began to wilt the night of the Sundering. Elowen keeps them "
        "blooming with her own life, one night at a time. She is much older than she "
        "looks, and much more tired than she smiles.",
    ),
    "hayato.jfif": (
        "The Draw",
        "Hayato's first duel with Kaito ended in a draw because Hayato let it. He saw "
        "the grief in the boy's eyes and could not bring himself to win. He has fought "
        "at his very best in every duel since, so the lie would only ever be told once.",
    ),
    "maren.jfif": (
        "The Spell She Broke",
        "The spell Maren unraveled was the one holding the storms of Voltaris together. "
        "She was expelled to hide the truth: the tower is failing. Ophira holds it up "
        "alone, and Maren is the only person who knows how to rebuild it.",
    ),
    "fenric.jfif": (
        "Born the Same Night",
        "Fenric was born the night Hrimfang died. The wolf's last breath was split in "
        "two: one half went to a shepherd girl in the snow, the other to a newborn "
        "half-wolf. He is not an outcast. He is the pack's true leader.",
    ),
    "faelyn.jfif": (
        "Counting Stars",
        "Every night Faelyn climbs the tallest tree in the Wilds and counts Lyra's new "
        "stars. She knows every one by heart. She tells everyone she has not forgiven "
        "Lyra. The stars know better.",
    ),
    "amethia.jfif": (
        "The Torn Page",
        "In the Warden Archive Amethia found the page Malachar tore from his tome: "
        "instructions for closing the Box. It requires the willing hand of a Warden. "
        "Only two are left: Malachar, and a swamp witch who swears she quit. Amethia "
        "has told no one.",
    ),
    "valeria.jfif": (
        "The Father's Order",
        "The order to keep the capital's gates shut came from the twins' own father. "
        "Valeria has never forgiven him. Aurelius obeyed because he loved him. She has "
        "only recently understood that both of them were trying to make him proud.",
    ),
    "stellara.jfif": (
        "The Star That Spoke",
        "One of the stars Stellara caught spoke with Lyra's voice: help me stitch it "
        "closed. Since that night, the huntress has been quietly throwing some of the "
        "fallen stars back into the sky.",
    ),
    "morwen.jfif": (
        "He Chose to Go",
        "Ravenna showed Morwen the truth: Edric was not taken. He walked into the "
        "shadow willingly. Morwen no longer knows whether she wants revenge on "
        "Zarathor, or on Edric for leaving her.",
    ),
    "kage.jfif": (
        "The Lord Who Gave the Order",
        "The rival lord who ordered the Kurokage to burn the Tonbo castle was Kage's "
        "own father. Kage was the child who found Kaito in the well and walked away. "
        "He is the one Kaito has been searching for.",
    ),
    "odette.jfif": (
        "Colette's Request",
        "Last winter Colette spoke a full sentence for the first time. She asked for "
        "Celestine by name. Odette is still trying to find the courage to send a "
        "letter to the sky.",
    ),
    "nocturna.jfif": (
        "Why She Never Reads Them",
        "Nocturna does not open her sister's letters because she knows what they say: "
        "that Amethia forgives her. Reading it would mean deciding whether she deserves it.",
    ),
    "eldric.png": (
        "The Serpent's Name",
        "The serpent of runes is a fragment of one of the Seven Wardens, trapped in "
        "the mountains since the Box was forged. Each night it tells Eldric one secret. "
        "Last night it told him the name of the Warden who walked away.",
    ),
    "ravenna.png": (
        "The Raven",
        "Ravenna's raven of violet fire is Lira, Malachar's daughter, who slipped out of "
        "his tome and found her way to the guide of souls. Lira is proof that a soul "
        "can be freed without being devoured. She has asked Ravenna not to tell her "
        "father yet.",
    ),
    "cassius.png": (
        "The Path of Stones",
        "Cassius knows Solara is going blind. Every night he carves small grooves into "
        "the temple floor so she can find her way by touch, and he hammers loudly so "
        "she can follow the sound. He has never told her he knows.",
    ),
    "nyra.jfif": (
        "The Job That Went Wrong",
        "The child who got hurt on Nyra and Lucan's last job was Jory. He does not "
        "remember her face, only a voice saying sorry. Every loaf of bread she gives "
        "him is part of the same apology.",
    ),
    "dorian.jfif": (
        "Spark's Heart",
        "Spark's heart is a shard of captured lightning that a young archivist gave a "
        "lonely boy outside the storm tower. The archivist was Ophira. She still asks "
        "after the little dragon.",
    ),
    "grizelda.jfif": (
        "The Warden Who Walked Away",
        "Grizelda was one of the Seven Wardens. She walked out before the Box was "
        "finished, saying a lock would only teach the Hollow to wait. She has been "
        "waiting too, in the swamp, for the day someone would need a Warden who did "
        "not make that mistake.",
    ),
    "ophira.jfif": (
        "Holding the Tower",
        "The storm tower of Voltaris is failing. Ophira holds it together alone every "
        "night, releasing storms by hand. She has not slept a full night in years, and "
        "she has not asked Maren for help, because asking would mean admitting Maren "
        "was right.",
    ),
    "verdana.jfif": (
        "The Last Seed",
        "Verdana knows what she is: the last seed of the Aetherwell. Planted in the "
        "Riftheart, she could heal the world, but she would no longer be Verdana. She "
        "has not decided yet, and Puff has not left her side since she found out.",
    ),
    "tavik.jfif": (
        "Kesh's Return",
        "Kesh is Hrimfang's own pup. When Fenric claims the pack, Kesh will go with "
        "him. Tavik has known it from the start, and he leads them north anyway, "
        "because that is what you do for family.",
    ),
    "lucan.jfif": (
        "Grit's Real Job",
        "Mortis did not lose Grit by accident. Lucan is his grandson, the child of a "
        "daughter who left Nocthaven before the plague, and Grit was sent to keep him "
        "alive. Lucan has no idea. Grit is exhausted.",
    ),
    # 3★
    "rowan.jfif": (
        "What the Bow Remembers",
        "Some nights the antler bow whispers in his grandfather's voice. It always "
        "says the same thing: tell the elf it was not his fault.",
    ),
    "corvus.jfif": (
        "His Real Name",
        "His real name is Corin. He is Nyra's younger brother, the one she believes died "
        "in the Sundering. The guild took him in, and he has never found the courage to "
        "lower his collar and let her see his face.",
    ),
    "tobin.jfif": (
        "Grandpa's Sword",
        "The sword in the barn belonged to his grandfather, a knight who ran from "
        "Valdremont and never spoke of it. Before he died, the old man told Tobin one "
        "thing: if a knight with a lion on his shield comes, do not run. Tobin is "
        "trying very hard not to.",
    ),
    "garrick.jfif": (
        "The Fourth Death",
        "Garrick caused Gorvane's fourth death. In the middle of a battle the warlord "
        "turned on his own son, and Garrick struck him down to save Brannoc. Nobody "
        "else saw it. Garrick left the next day.",
    ),
    "maelis.jfif": (
        "The Patient Who Lived",
        "Her first patient did not die. He woke the next morning and asked for the "
        "girl who saved him. Annelise has written it in every letter, but Maelis never "
        "gets past the first line before she has to stop.",
    ),
    "jory.jfif": (
        "The Voice",
        "Jory has a scar from the night a job went wrong in front of him. He does not "
        "remember the thieves, only a woman's voice saying sorry, over and over. He "
        "has heard that voice again, on the rooftops.",
    ),
    "albin.jfif": (
        "The Reports",
        "Astra reads every report Albin sends and keeps them all in her observatory, "
        "in order. She stays away because the star inside her hurts the people close "
        "to it, and she would rather be a bad teacher than a dangerous one.",
    ),
    "brina.jfif": (
        "The Airship",
        "In the back of her workshop Brina is building an airship, big enough for two, "
        "to fly her cousin out of Cogsreach to the Zephyrine Isles before the barons "
        "finally catch her.",
    ),
    "silas.jfif": (
        "Where the Mushrooms Grow",
        "His glowing mushrooms only grow where the Hollow leaks into the world. The "
        "Mirewood is one of those leaks, and Grizelda has been guarding it for centuries. "
        "Silas worked it out last month. He has not stopped picking mushrooms.",
    ),
    "kael.jfif": (
        "The Warden's Journal",
        "In a ruin Kael found the journal of a Warden, with a map to the Mystic Box "
        "and a last page he has never dared to read. He has the feeling it is "
        "addressed to him.",
    ),
    "vexa.jfif": (
        "The Bridge",
        "The bridge Vexa keeps selling belonged to her family before the Sundering "
        "swallowed their village. Every time she sells it, she tells the buyer the "
        "story of the people who lived on it. Nobody has ever asked for a refund.",
    ),
    "torvin.jfif": (
        "The Stones' Warning",
        "The stones under Cinderpeak sing that the mountain will wake when the Everfire "
        "changes hands. Torvin has not told Pyralis, because his friend would go anyway, "
        "and Torvin intends to be standing beside him when he does.",
    ),
    "annelise.jfif": (
        "The Golden Knight",
        "Annelise remembers a golden knight at a closing gate, crying behind his helm. "
        "She has never blamed him. She would like to tell him so, if she ever finds out "
        "who he is.",
    ),
    "brannoc.jfif": (
        "The Promise",
        "His father made him promise: if he ever comes back a fifth time, Brannoc must "
        "be the one to end it. Every fight in the arena is practice for the only fight "
        "he does not want to win.",
    ),
    "ryuji.jfif": (
        "The Petal",
        "Ryuji once cut a falling cherry petal in half with the wind of his punch. "
        "Nobody saw. He has never told anyone, because if they knew, they might ask him "
        "to pick up the sword again.",
    ),
    "liesel.jfif": (
        "Ember's Errand",
        "Ember is a spirit of the Everfire, sent out of Cinderpeak to find the flame's "
        "next guardian. It stayed with Liesel because she healed it, but it always "
        "turns its head when Pyralis walks by.",
    ),
    "wren.jfif": (
        "What Bloop Says",
        "Bloop can talk, but only to Wren. It says Grizelda is very lonely, and that she "
        "was once very important. Wren has started inviting the old witch to dinner.",
    ),
}


def public_lore(character, ascension=0, owned=None):
    """Região, título, história, laços e capítulo secreto da carta.

    `ascension`: ascensão do jogador nessa carta (libera o capítulo secreto).
    `owned`: file_names que o jogador tem; marca os laços com quem ele já tem.
    Devolve None se a carta não tiver história.
    """
    if not character:
        return None
    file_name = character.get("file_name")
    lore = STORIES.get(file_name)
    if not lore:
        return None

    region = _region(lore["region"])
    secret_title, secret_text = SECRETS[file_name]
    unlocked = ascension >= SECRET_UNLOCK_ASCENSION
    return {
        "title": lore["title"],
        "story": list(lore["story"]),
        "region": {"id": region["id"], "name": region["name"], "element": region["element"],
                   "resonance": public_resonance(region["id"])},
        "bonds": _bonds_of(file_name, owned),
        "rivals": _rivals_of(file_name),
        "secret": {
            "title": secret_title,
            "unlockAscension": SECRET_UNLOCK_ASCENSION,
            "unlocked": unlocked,
            # O texto só sai do servidor depois de liberado.
            "text": secret_text if unlocked else None,
        },
    }


def unlocked_secret_title(character, before, after):
    """Título do capítulo secreto se ir de `before` para `after` o liberou."""
    secret = SECRETS.get((character or {}).get("file_name"))
    if secret and before < SECRET_UNLOCK_ASCENSION <= after:
        return secret[0]
    return None


def public_world():
    """Mapa-múndi: o mundo, a crônica, as regiões e quem vem de cada uma."""
    residents = {region["id"]: [] for region in REGIONS}
    for character in CHARACTERS:
        lore = STORIES.get(character["file_name"])
        if lore:
            residents[lore["region"]].append(
                {
                    "name": character["name"],
                    "rarity": character["rarity"],
                    "file_name": character["file_name"],
                    "title": lore["title"],
                }
            )

    return {
        "world": copy.deepcopy(WORLD),
        "chronicle": copy.deepcopy(CHRONICLE),
        "regions": [
            {
                **copy.deepcopy(region),
                "resonance": public_resonance(region["id"]),
                "characters": sorted(
                    residents[region["id"]],
                    key=lambda c: (-c["rarity"], c["name"]),
                ),
            }
            for region in REGIONS
        ],
    }


def _region(region_id):
    return next(region for region in REGIONS if region["id"] == region_id)


def bond_between(a, b):
    """O que `a` pensa de `b` e o que `b` pensa de `a`, ou None se não há laço."""
    for x, y, x_about_y, y_about_x in BONDS:
        if (x, y) == (a, b):
            return x_about_y, y_about_x
        if (x, y) == (b, a):
            return y_about_x, x_about_y
    return None


def region_of(file_name):
    """Id da região de origem da carta, ou None."""
    lore = STORIES.get(file_name)
    return lore["region"] if lore else None


def public_resonance(region_id):
    """Nome e descrição da ressonância da região (None se não houver)."""
    resonance = REGION_RESONANCES.get(region_id)
    if not resonance:
        return None
    return {"region": region_id, "regionName": _region(region_id)["name"],
            "name": resonance["name"], "description": resonance["description"]}


def rivalry_between(a, b):
    """O que `a` diz a `b` e o que `b` responde numa rivalidade, ou None."""
    for x, y, x_line, y_line in RIVALRIES:
        if (x, y) == (a, b):
            return x_line, y_line
        if (x, y) == (b, a):
            return y_line, x_line
    return None


def _rivals_of(file_name):
    rivals = []
    for a, b, a_line, b_line in RIVALRIES:
        if file_name not in (a, b):
            continue
        other, line = (b, a_line) if a == file_name else (a, b_line)
        character = get_character(other)
        rivals.append({"name": character["name"], "file_name": other,
                       "rarity": character["rarity"], "line": line})
    return rivals


def _bonds_of(file_name, owned=None):
    bonds = []
    for a, b, a_about_b, b_about_a in BONDS:
        if a == file_name:
            other, relation = b, a_about_b
        elif b == file_name:
            other, relation = a, b_about_a
        else:
            continue
        character = get_character(other)
        bond = {
            "name": character["name"],
            "file_name": other,
            "rarity": character["rarity"],
            "relation": relation,
        }
        if owned is not None:
            bond["owned"] = other in owned
        bonds.append(bond)
    return bonds
