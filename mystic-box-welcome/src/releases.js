// Notas de lançamento exibidas na landing ("Patch Notes").
//
// Texto de apresentação, para o jogador: diz o que mudou, sem números de regra
// (preços, chances, tempos). Esses números estão no Grimório do jogo e na API.
//
// Como atualizar: todo PR que muda algo que o jogador vê ganha uma nota aqui.
// Notas novas entram no lançamento mais recente se for do mesmo dia; senão,
// crie um lançamento novo NO TOPO, com a próxima versão. `prs` são os números
// dos PRs no GitHub. O teste releases.test.js confere a ordem e os campos.
//
// Tipos: "new" (novidade), "improved" (melhoria), "fixed" (correção).

export const NOTE_TYPES = {
  new: "New",
  improved: "Improved",
  fixed: "Fixed",
};

export const releases = [
  {
    version: "0.12",
    date: "2026-11-17",
    name: "Spellfire",
    tagline: "Every strike, spell and blessing now lights up the arena.",
    notes: [
      {
        type: "improved",
        title: "Battle effects",
        text: "Spells fly across the arena and burst in the colors of their element: flames rise, tides crash, winds swirl, stone shatters, lightning flickers, light flares and shadow implodes. Physical blows slash, critical hits shake the arena, healing rises in pillars of light and fallen champions break apart. Prefer something lighter on your battery? Switch Effects to Lite in the battle menu.",
        prs: [109],
      },
      {
        type: "improved",
        title: "Whose turn is it?",
        text: "A banner announces your turn with the champion who acts, a tag marks who is acting on both sides, and the action bar shows the champion's portrait. The chosen skill glows, its targets are marked with a reticle and everything it cannot reach steps back.",
        prs: [109],
      },
    ],
  },
  {
    version: "0.11",
    date: "2026-11-15",
    name: "Relics of Aethra",
    tagline: "Every land guards a treasure. Claim it, and choose who carries it.",
    notes: [
      {
        type: "new",
        title: "Relics",
        text: "Defeat a land's champion in the campaign to claim its relic, then equip it on a champion from your collection. The campaign shows which relic each champion guards. Each relic has its own illustration, shown in your collection, in battle and in the Grimoire. Every relic trades one strength for another, and in the hands of a champion from its own land it grows stronger and awakens at the start of battle. Forge more copies with Arcane Shards, and read all about them in the new Relics chapter of the Grimoire.",
        prs: [87],
      },
      {
        type: "fixed",
        title: "One summon per portal",
        text: "Opening the portal now starts its recovery right away, and opening it again before your cards are kept shows the same summon instead of a new one. A summon you opened on another device is kept when you come back.",
        prs: [95],
      },
      {
        type: "fixed",
        title: "Relic forging",
        text: "Forging a relic with Arcane Shards no longer fails with an error. Once you've defeated a land's champion, you can forge more copies of its relic.",
        prs: [96],
      },
      {
        type: "new",
        title: "Requests in the shop",
        text: "Can't find the card you want? Request it in the new Requests tab for the price you're willing to pay. Your shards are set aside, and any player who owns the card can sell it to you in one tap. Cancel whenever you like to get your shards back.",
        prs: [107],
      },
      {
        type: "new",
        title: "Price history",
        text: "When you sell or request a card, the shop shows its recent sales with the latest, average and range of prices, so you know what it's really worth.",
        prs: [107],
      },
      {
        type: "improved",
        title: "Market fee",
        text: "A small fee is now taken from the seller on every sale in the shop, so shards don't pile up endlessly. The buyer still pays the listed price, and the shop shows how much you receive before you sell.",
        prs: [107],
      },
    ],
  },
  {
    version: "0.10",
    date: "2026-11-14",
    name: "A Lighter Spell",
    tagline: "The same night sky, with a cooler touch.",
    notes: [
      {
        type: "improved",
        title: "Smoother and cooler on phones",
        text: "The starry sky, the aurora and the gilded titles look exactly the same but take far less work to draw, and the sky rests while a window or the summoning portal is open. Your phone stays cooler and the battery lasts longer.",
        prs: [89],
      },
    ],
  },
  {
    version: "0.9",
    date: "2026-11-11",
    name: "The Celestial Grimoire",
    tagline: "Every page of the game, bound in gold.",
    notes: [
      {
        type: "new",
        title: "A new look for every screen",
        text: "Gold filigree on every window, parchment grain, gilded titles and a single family of fonts from the home screen to the battlefield.",
        prs: [79],
      },
      {
        type: "improved",
        title: "Sign in to summon",
        text: "The Box now opens only for signed-in summoners, and the realm keeps a steady pace for everyone when traffic spikes.",
        prs: [81],
      },
      {
        type: "fixed",
        title: "Home screen art is back",
        text: "The Summon and Battle cards on the home screen show their illustrations again.",
        prs: [75],
      },
    ],
  },
  {
    version: "0.8",
    date: "2026-11-10",
    name: "Tides of Aether",
    tagline: "No battle lasts forever.",
    notes: [
      {
        type: "new",
        title: "Emoji reactions in duels",
        text: "Players and spectators can cheer, gasp and taunt during online duels. Reactions float over the battlefield for everyone watching.",
        prs: [72],
      },
      {
        type: "new",
        title: "The Aether Surge",
        text: "Late in a battle the Aether rises: every hit lands harder and healing fades round after round, so even the sturdiest teams have to finish the fight.",
        prs: [71],
      },
    ],
  },
  {
    version: "0.7",
    date: "2026-11-09",
    name: "The Watchers",
    tagline: "The arena has an audience now.",
    notes: [
      {
        type: "new",
        title: "Who's online",
        text: "See which summoners are in the duel lobby right now, with their level and title, and challenge them in one click.",
        prs: [68],
      },
      {
        type: "new",
        title: "Watch live duels",
        text: "Take a seat in the stands of any duel in progress and follow every skill, bond and last word as it happens.",
        prs: [68],
      },
      {
        type: "improved",
        title: "A cleaner battlefield",
        text: "The battle screen was rebuilt to be easier to read and to fit any screen, from phones to wide monitors.",
        prs: [67],
      },
      {
        type: "improved",
        title: "The Back button works",
        text: "Every screen and panel has its own address. The browser's Back button closes what you opened, and links open exactly where you left.",
        prs: [66],
      },
    ],
  },
  {
    version: "0.6",
    date: "2026-11-08",
    name: "The Shattered Realms",
    tagline: "Aethra gets a map, a history and a past for every champion.",
    notes: [
      {
        type: "new",
        title: "The world map of Aethra",
        text: "An illustrated map of the Shattered Realms, with the rumor of each realm, its element and the champions who come from it.",
        prs: [61],
      },
      {
        type: "new",
        title: "A story for every champion",
        text: "Open any card in your collection to read who they were before the Box called them. Ascend them to unlock a secret chapter, and hear their last words when they fall.",
        prs: [61],
      },
      {
        type: "new",
        title: "Bonds, rivalries and duo techniques",
        text: "Champions who share a story fight stronger side by side and learn techniques together. Rivals on opposite sides hit each other harder.",
        prs: [61],
      },
      {
        type: "new",
        title: "Campaign across the map",
        text: "Fight through every realm stage by stage, face its boss and read the epilogue of its story.",
        prs: [61],
      },
      {
        type: "new",
        title: "Region resonance and collections",
        text: "A team of three champions from the same realm awakens its resonance. Collect every champion of a realm to claim its reward.",
        prs: [61],
      },
      {
        type: "new",
        title: "The weekly omen and titles",
        text: "Each week a rumor spreads from one realm, making its champions easier to summon and stronger in battle. Earn titles to show on your profile.",
        prs: [61],
      },
    ],
  },
  {
    version: "0.5",
    date: "2026-11-07",
    name: "Ascension",
    tagline: "Duplicates are never wasted.",
    notes: [
      {
        type: "new",
        title: "Online duels",
        text: "Challenge another summoner by name and fight a turn-based duel with the same rules as the arena.",
        prs: [50],
      },
      {
        type: "new",
        title: "Card ascension",
        text: "Spend duplicate copies to ascend a champion: stronger stats and, at higher ranks, an extra archetype skill.",
        prs: [58],
      },
      {
        type: "new",
        title: "More champions",
        text: "A new wave of champions answered the call of the Box.",
        prs: [58],
      },
      {
        type: "improved",
        title: "Calmer player search",
        text: "Searching for players is faster and only runs when you ask for it.",
        prs: [59],
      },
      {
        type: "fixed",
        title: "Your name stays put",
        text: "Your profile name no longer disappears when you come back from a battle.",
        prs: [56],
      },
    ],
  },
  {
    version: "0.4",
    date: "2026-11-06",
    name: "The Summoners' Market",
    tagline: "Every card in the market was summoned by someone.",
    notes: [
      {
        type: "new",
        title: "A market between players",
        text: "The shop became a market. Every card for sale was listed by another summoner at the price they chose, and the seller gets every shard.",
        prs: [48],
      },
      {
        type: "new",
        title: "Usernames and player search",
        text: "Pick a name and find other summoners by theirs.",
        prs: [47],
      },
    ],
  },
  {
    version: "0.3",
    date: "2026-11-04",
    name: "The Grimoire",
    tagline: "Every rule of the game, in one book.",
    notes: [
      {
        type: "new",
        title: "The Grimoire",
        text: "A book with every rule of the game: summon chances, elements, archetypes, skills, statuses and difficulties, always up to date with the game itself.",
        prs: [44],
      },
      {
        type: "new",
        title: "Forgot your password?",
        text: "Recover your account straight from the sign-in screen.",
        prs: [43],
      },
    ],
  },
  {
    version: "0.2",
    date: "2026-11-03",
    name: "First Blood",
    tagline: "The champions finally fight.",
    notes: [
      {
        type: "new",
        title: "Battles against the computer",
        text: "Pick three champions and fight turn by turn with Aether, elements, archetypes and status effects. Harder difficulties unlock as you level up.",
        prs: [39],
      },
      {
        type: "new",
        title: "Levels and experience",
        text: "Every battle earns experience. Each new level rewards Arcane Shards.",
        prs: [39],
      },
      {
        type: "improved",
        title: "Faster everywhere",
        text: "The game is now served from a global network, so it loads quickly wherever you are.",
        prs: [38],
      },
    ],
  },
  {
    version: "0.1",
    date: "2026-11-02",
    name: "The Box Opens",
    tagline: "The first summoners answer the call.",
    notes: [
      {
        type: "new",
        title: "Summon three at a time",
        text: "Every summon draws three champions, and the last card of the draw is the most likely to be rare.",
        prs: [7],
      },
      {
        type: "new",
        title: "Your collection",
        text: "Duplicates are grouped together, and you can sort your champions however you like.",
        prs: [5, 15, 24],
      },
      {
        type: "new",
        title: "Arcane Shards",
        text: "The currency of Aethra, earned by playing and spent in the shop.",
        prs: [16, 19],
      },
      {
        type: "new",
        title: "Thirty new champions",
        text: "The roster grows with thirty new champions to summon.",
        prs: [26],
      },
      {
        type: "new",
        title: "A home for summoners",
        text: "A home screen for signed-in players, with the game fully in English.",
        prs: [25, 28],
      },
    ],
  },
];
