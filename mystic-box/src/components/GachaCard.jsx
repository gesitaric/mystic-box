
const characterImages = import.meta.glob("../assets/characters/*", {
  eager: true,
  import: "default",
});

function getCharacterImage(fileName) {
  if (!fileName) return null;
  return characterImages[`../assets/characters/${fileName}`] ?? null;
}

function GachaCard({ card }) {
  const image = getCharacterImage(card?.file_name);
  const rarity = card?.rarity ?? 0;

  return (
    <div className="card">
      <div className={`card-content ${image ? "has-image" : ""}`}>
        {image ? (
          <img className="character-image" src={image} alt={card.name} />
        ) : (
          <div className="character">🧚</div>
        )}
        <div className="rarity">{"✦ ".repeat(rarity).trim()}</div>
        <div className="name">{(card?.name ?? "???").toUpperCase()}</div>
      </div>
    </div>
  );
}

export default GachaCard;
