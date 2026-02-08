const ThemeLotus = ({ className = "" }: { className?: string }) => {
  return (
    <div className={`relative ${className}`}>
      <svg
        viewBox="0 0 300 300"
        xmlns="http://www.w3.org/2000/svg"
        className="relative z-10 w-full h-full animate-spin [animation-duration:90s]"
        style={{
          filter:
            "drop-shadow(0 0 6px hsl(var(--primary) / 0.7)) drop-shadow(0 0 20px hsl(var(--primary) / 0.3))",
        }}
      >
        {/* Outer ring — 8 large petals */}
        {[0, 45, 90, 135, 180, 225, 270, 315].map((angle) => (
          <ellipse
            key={`o-${angle}`}
            cx="150"
            cy="78"
            rx="38"
            ry="72"
            fill="none"
            stroke="hsl(var(--primary))"
            strokeWidth="1.5"
            transform={`rotate(${angle} 150 150)`}
          />
        ))}

        {/* Inner ring — 8 petals offset 22.5° */}
        {[22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5].map((angle) => (
          <ellipse
            key={`i-${angle}`}
            cx="150"
            cy="100"
            rx="18"
            ry="50"
            fill="none"
            stroke="hsl(var(--primary))"
            strokeWidth="1.2"
            transform={`rotate(${angle} 150 150)`}
          />
        ))}

        {/* Center dot */}
        <circle cx="150" cy="150" r="4" fill="none" stroke="hsl(var(--primary))" strokeWidth="1.5" />
      </svg>
    </div>
  );
};

export default ThemeLotus;
