import type { ResolvedTheme } from "./theme";

export const STATUS_THEME_COLORS = {
  DARK: {
    HIGH: { text: "#FDA29B", border: "#7A363B", background: "#2C1B1E" },
    MEDIUM: { text: "#FDB022", border: "#745515", background: "#2A2418" },
    LOW: { text: "#6CE9A6", border: "#316A4C", background: "#17261E" },
    UNSCORED: { text: "#98A2B3", border: "#46505B", background: "#22272E" },
  },
  LIGHT: {
    HIGH: { text: "#B42318", border: "#FDA29B", background: "#FEF3F2" },
    MEDIUM: { text: "#B54708", border: "#FEC84B", background: "#FFFAEB" },
    LOW: { text: "#067647", border: "#6CE9A6", background: "#ECFDF3" },
    UNSCORED: { text: "#475467", border: "#D0D5DD", background: "#F2F4F7" },
  },
} as const satisfies Record<ResolvedTheme, Record<"HIGH" | "MEDIUM" | "LOW" | "UNSCORED", { text: string; border: string; background: string }>>;

export const DATA_VISUALIZATION_COLORS = {
  DARK: { blue: "#60A5FA", teal: "#2DD4BF", violet: "#A78BFA", orange: "#F59E0B", rose: "#FB7185", green: "#4ADE80" },
  LIGHT: { blue: "#2563EB", teal: "#0F766E", violet: "#6D5BD0", orange: "#C76A00", rose: "#BE315E", green: "#16803C" },
} as const satisfies Record<ResolvedTheme, Record<"blue" | "teal" | "violet" | "orange" | "rose" | "green", string>>;
