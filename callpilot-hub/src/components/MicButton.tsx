import { Mic, Loader2 } from "lucide-react";

interface MicButtonProps {
  isActive: boolean;
  isConnecting: boolean;
  onClick: () => void;
}

const MicButton = ({ isActive, isConnecting, onClick }: MicButtonProps) => {
  return (
    <div className="flex flex-col items-center gap-6">
      {/* Grid container — single cell, everything stacks at center */}
      <div className="grid place-items-center w-48 h-48 md:w-56 md:h-56">

        {/* Layer 1: Single breathing glow (active) */}
        {isActive && (
          <span className="[grid-column:1/-1] [grid-row:1/-1] w-[10.5rem] h-[10.5rem] md:w-[12.5rem] md:h-[12.5rem] rounded-full bg-destructive/20 animate-pulse-red" />
        )}

        {/* Orbiting dot (idle) */}
        {!isActive && !isConnecting && (
          <div className="[grid-column:1/-1] [grid-row:1/-1] w-40 h-40 md:w-48 md:h-48 animate-spin [animation-duration:4s] relative">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-primary/60" />
          </div>
        )}

        {/* Layer 2: Button */}
        <button
          onClick={onClick}
          disabled={isConnecting}
          className={`[grid-column:1/-1] [grid-row:1/-1] z-10 flex items-center justify-center w-32 h-32 md:w-40 md:h-40 rounded-full border-2 transition-all duration-500 cursor-pointer focus:outline-none group ${
            isConnecting
              ? "border-primary/40 bg-primary/5 opacity-70 cursor-wait"
              : isActive
              ? "border-destructive bg-destructive/10 glow-active"
              : "border-primary/40 bg-primary/5 glow-idle hover:border-primary/70 hover:bg-primary/10"
          }`}
          aria-label={isActive ? "Stop agent" : "Start scheduling agent"}
        >
          {isConnecting ? (
            <Loader2 className="text-primary w-10 h-10 md:w-14 md:h-14 animate-spin" />
          ) : (
            <Mic
              className={`relative z-10 transition-all duration-500 ${
                isActive
                  ? "text-destructive w-12 h-12 md:w-16 md:h-16 animate-mic-glow"
                  : "text-primary w-10 h-10 md:w-14 md:h-14 group-hover:scale-110 transition-transform"
              }`}
            />
          )}
        </button>
      </div>

      <p
        className={`text-sm font-medium transition-colors duration-500 ${
          isConnecting
            ? "text-muted-foreground"
            : isActive
            ? "text-destructive"
            : "text-muted-foreground"
        }`}
      >
        {isConnecting
          ? "Connecting to voice agent..."
          : isActive
          ? "Agent Active — Speak naturally"
          : "Click to start scheduling agent"}
      </p>
    </div>
  );
};

export default MicButton;
