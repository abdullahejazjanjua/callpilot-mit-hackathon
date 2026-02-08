import { useEffect, useState } from "react";
import ThemeLotus from "./ThemeLotus";

interface LoadingScreenProps {
  onLoaded: () => void;
}

const LoadingScreen = ({ onLoaded }: LoadingScreenProps) => {
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setFadeOut(true), 2500);
    const removeTimer = setTimeout(() => onLoaded(), 3100);
    return () => {
      clearTimeout(timer);
      clearTimeout(removeTimer);
    };
  }, [onLoaded]);

  return (
    <div
      className={`fixed inset-0 z-50 flex flex-col items-center justify-center bg-background transition-opacity duration-600 ${
        fadeOut ? "opacity-0" : "opacity-100"
      }`}
    >
      <ThemeLotus className="w-48 h-48 md:w-64 md:h-64" />

      <p className="mt-8 text-sm text-muted-foreground tracking-widest uppercase">
        Initializing CallPilot
        <span className="animate-terminal-blink">...</span>
      </p>
    </div>
  );
};

export default LoadingScreen;
