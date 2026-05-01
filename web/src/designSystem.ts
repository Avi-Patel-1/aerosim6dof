export const mercuryTokens = {
  colors: {
    mercuryBlue: "#5266eb",
    ghostBlue: "#cdddff",
    deepSpace: "#171721",
    midnightSlate: "#1e1e2a",
    graphite: "#272735",
    lead: "#70707d",
    starlight: "#ededf3",
    silver: "#c3c3cc",
    pureWhite: "#ffffff"
  },
  radii: {
    card: "0px",
    container: "4px",
    input: "32px",
    button: "32px",
    headerPill: "40px"
  },
  spacing: {
    xs: "4px",
    sm: "8px",
    md: "16px",
    lg: "24px",
    xl: "32px",
    section: "80px"
  },
  typography: {
    display: "var(--font-arcadiadisplay)",
    body: "var(--font-arcadia)",
    displayWeight: 360,
    uiWeight: 480
  }
} as const;

export const mercuryClasses = {
  primaryButton: "primary-action",
  secondaryButton: "secondary-action",
  iconButton: "icon-action",
  panel: "mercury-panel",
  badge: "mercury-badge",
  segmented: "mini-segment"
} as const;
