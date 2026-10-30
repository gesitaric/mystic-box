
function Particles({ particles }) {
  return (
    <div className="particles">
      {particles.map((particle) => (
        <span
          key={particle.id}
          className="particle"
          style={{
            "--x": `${particle.x}px`,
            "--y": `${particle.y}px`,
            animationDelay: `${particle.delay}s`,
          }}
        >
          ✦
        </span>
      ))}
    </div>
  );
}

export default Particles;
