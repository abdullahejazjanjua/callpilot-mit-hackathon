

## Animate the Active State Glow

Replace the current `animate-breathe` animation on the glow layer with a new custom `pulse-red` keyframe that creates a rhythmic "heartbeat" effect.

### Changes

**1. `src/index.css`** -- Add a new `@keyframes pulse-red` definition:
- 0%: `opacity: 0.5; transform: scale(1)`
- 50%: `opacity: 1; transform: scale(1.1)`
- 100%: `opacity: 0.5; transform: scale(1)`

This is safe because the glow is centered via CSS Grid (`grid-column/grid-row`), not via `transform: translate`, so `transform: scale()` won't cause any drift.

**2. `tailwind.config.ts`** -- Register the new keyframe and animation:
- Add `pulse-red` keyframe to the `keyframes` section
- Add `"pulse-red": "pulse-red 2s ease-in-out infinite"` to the `animation` section

**3. `src/components/MicButton.tsx`** -- Swap the class on the glow span:
- Change `animate-breathe` to `animate-pulse-red` on Line 16

### Result
A smooth, 2-second infinite breathing pulse on the red glow -- slightly scaling and brightening rhythmically like a heartbeat, with no alignment drift.

