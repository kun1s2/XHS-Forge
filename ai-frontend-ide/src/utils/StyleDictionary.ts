// ai-frontend-ide/src/utils/StyleDictionary.ts

export const MATERIAL_MAP: Record<string, string> = {
  glassmorphism: "bg-white/40 backdrop-blur-xl border border-white/50 shadow-xl",
  claymorphism: "bg-white shadow-[inset_0_-8px_12px_rgba(0,0,0,0.1),0_20px_40px_rgba(0,0,0,0.15)] rounded-[40px] border-4 border-white/20",
  neon: "bg-black border border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.5)] text-cyan-400",
  "paper-cut": "bg-white shadow-[0_4px_10px_rgba(0,0,0,0.1),0_1px_2px_rgba(0,0,0,0.06)] border-b-4 border-gray-200 transition-transform active:translate-y-1",
  holographic: "bg-gradient-to-br from-fuchsia-500/20 via-cyan-500/20 to-lime-500/20 backdrop-blur-md border border-white/30",
  "flat-dark": "bg-gray-900 text-gray-100 border border-gray-800 shadow-2xl",
  "paper-cut": "bg-[#FFFDF9] shadow-[2px_4px_12px_rgba(0,0,0,0.08)] border border-stone-200/50",
  "washi-tape": "relative before:absolute before:-top-3 before:left-1/2 before:-translate-x-1/2 before:w-16 before:h-6 before:bg-rose-200/50 before:-rotate-2 before:backdrop-blur-sm before:content-[''] before:z-20",
};

export const PRIORITY_MAP: Record<string, string> = {
  high: "z-10 scale-[1.02] shadow-2xl ring-4 ring-offset-2 ring-primary/30",
  medium: "z-0 scale-100 shadow-md",
  low: "z-[-1] scale-95 opacity-70 grayscale-[30%] blur-[0.5px]",
};

export const ANIMATION_MAP: Record<string, string> = {
  "fade-up": "animate-fade-up",
  "bouncy-pop": "hover:scale-105 active:scale-95 transition-all duration-300",
  "cyber-glitch": "hover:skew-x-1 hover:brightness-110 transition-all",
  none: "",
};

/**
 * 样式翻译官：将 UINode 的语义 Props 转化为物理类名
 */
export const resolveNodeStyles = (props: any): string => {
  const classes: string[] = [];

  if (props.variant && MATERIAL_MAP[props.variant]) {
    classes.push(MATERIAL_MAP[props.variant]);
  }

  if (props.visual_priority && PRIORITY_MAP[props.visual_priority]) {
    classes.push(PRIORITY_MAP[props.visual_priority]);
  }

  if (props.animation && ANIMATION_MAP[props.animation]) {
    classes.push(ANIMATION_MAP[props.animation]);
  }

  // 间距注入
  if (props.padding === "spacious") classes.push("p-8");
  if (props.padding === "compact") classes.push("p-2");

  return classes.join(" ");
};
