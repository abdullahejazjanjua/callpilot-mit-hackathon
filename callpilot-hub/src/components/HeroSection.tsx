import MicButton from "./MicButton";

interface HeroSectionProps {
  isActive: boolean;
  isConnecting: boolean;
  onToggle: () => void;
}

const HeroSection = ({ isActive, isConnecting, onToggle }: HeroSectionProps) => {
  return (
    <section className="relative w-full py-16 md:py-24 overflow-hidden flex-1 flex items-center">
      {/* Subtle grid background */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(hsl(var(--primary) / 0.5) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--primary) / 0.5) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      <div className="container relative z-10 flex flex-col items-center justify-center text-center gap-6">
        <div className="flex flex-col items-center">
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-foreground">
            Call<span className="text-primary">Pilot</span>
          </h1>
          <p className="mt-3 text-lg text-muted-foreground">
            Your Autonomous Appointment Booking Agent
          </p>
        </div>

        <MicButton isActive={isActive} isConnecting={isConnecting} onClick={onToggle} />
      </div>
    </section>
  );
};

export default HeroSection;
