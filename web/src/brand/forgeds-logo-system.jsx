/**
 * ForgeDS Logo System — source of truth
 *
 * Six React + SVG components for the ForgeDS brand identity.
 * See DESIGN-LANGUAGE.md for usage rules, colour variants, and construction notes.
 *
 * No hooks, no refs, no useEffect — SSR and PNG-export safe.
 * Inline styles + SVG fill attributes only (framework-agnostic, copy-portable).
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const PALETTE = {
  anvilBlack:   "#2b2d30",
  forgeFloor:   "#363839",
  anvilSteel:   "#4a4d52",
  coolTongs:    "#6b7280",
  wornMetal:    "#9ca3af",
  forgeEmber:   "#c2662d",
  heatedEdge:   "#e8956a",
  coolingMetal: "#f5c4a1",
  deepForge:    "#7a3d1e",
  coolLinen:    "#f0f0ec",
  offWhite:     "#f5f5f2",
};

export const FONT_STACK =
  '"Geist", ui-sans-serif, system-ui, sans-serif';

const LOGOMARK_VIEWBOX = 64;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Resolve fill colours for a given variant.
 * @param {"color" | "mono-dark" | "mono-light"} variant
 * @returns {{ body: string, spark: string, text: string }}
 */
export function resolveColors(variant = "color") {
  switch (variant) {
    case "mono-dark":
      return {
        body:  PALETTE.anvilBlack,
        spark: PALETTE.anvilBlack,
        text:  PALETTE.anvilBlack,
      };
    case "mono-light":
      return {
        body:  PALETTE.coolLinen,
        spark: PALETTE.coolLinen,
        text:  PALETTE.coolLinen,
      };
    case "color":
    default:
      return {
        body:  PALETTE.anvilSteel,
        spark: PALETTE.forgeEmber,
        text:  PALETTE.coolLinen,
      };
  }
}

// ---------------------------------------------------------------------------
// Logomark — anvil + spark, no text
// ---------------------------------------------------------------------------

/**
 * @param {object} props
 * @param {number} [props.size=64] - Rendered width/height in px
 * @param {"color"|"mono-dark"|"mono-light"} [props.variant="color"]
 * @param {string} [props.className]
 */
export function Logomark({ size = 64, variant = "color", className } = {}) {
  const c = resolveColors(variant);
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${LOGOMARK_VIEWBOX} ${LOGOMARK_VIEWBOX}`}
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
      style={{ display: "block" }}
    >
      {/* Trapezoidal base */}
      <polygon points="18,56 46,56 42,44 22,44" fill={c.body} />
      {/* Waist */}
      <rect x="24" y="32" width="16" height="12" fill={c.body} />
      {/* Striking face */}
      <rect x="10" y="24" width="44" height="8" fill={c.body} />
      {/* Horn (tapered left) */}
      <polygon points="4,28 10,24 10,32 4,30" fill={c.body} />
      {/* Heel (right nub) */}
      <rect x="54" y="26" width="4" height="6" fill={c.body} />
      {/* Primary spark (rotated 45-deg diamond) */}
      <rect
        x="30"
        y="18"
        width="4"
        height="4"
        transform="rotate(45 32 20)"
        fill={c.spark}
      />
      {/* Trailing spark 1 */}
      <rect
        x="36.75"
        y="12.75"
        width="2.5"
        height="2.5"
        transform="rotate(45 38 14)"
        fill={c.spark}
      />
      {/* Trailing spark 2 */}
      <rect
        x="41.25"
        y="9.25"
        width="1.5"
        height="1.5"
        transform="rotate(45 42 10)"
        fill={c.spark}
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Wordmark — "ForgeDS" typeset text only
// ---------------------------------------------------------------------------

/**
 * @param {object} props
 * @param {number} [props.fontSize=16] - Font size in px
 * @param {"color"|"mono-dark"|"mono-light"} [props.variant="color"]
 * @param {string} [props.className]
 */
export function Wordmark({ fontSize = 16, variant = "color", className } = {}) {
  const c = resolveColors(variant);
  return (
    <span
      className={className}
      style={{
        fontFamily: FONT_STACK,
        fontWeight: 500,
        fontSize: `${fontSize}px`,
        lineHeight: 1,
        color: c.text,
        whiteSpace: "nowrap",
        display: "inline-block",
      }}
    >
      <span style={{ letterSpacing: "0.02em" }}>Forge</span>
      <span style={{ letterSpacing: "0.04em", color: c.spark }}>DS</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Logo — Logomark + Wordmark combined
// ---------------------------------------------------------------------------

/**
 * @param {object} props
 * @param {number} [props.size=32] - Logomark height in px; wordmark scales proportionally
 * @param {"horizontal"|"vertical"} [props.layout="horizontal"]
 * @param {"color"|"mono-dark"|"mono-light"} [props.variant="color"]
 * @param {string} [props.className]
 */
export function Logo({
  size = 32,
  layout = "horizontal",
  variant = "color",
  className,
} = {}) {
  const isVertical = layout === "vertical";
  const gap = isVertical ? size * 0.15 : size * 0.25;
  const wordmarkSize = isVertical ? size * 0.4 : size * 0.5;

  return (
    <span
      className={className}
      style={{
        display: "inline-flex",
        flexDirection: isVertical ? "column" : "row",
        alignItems: "center",
        gap: `${gap}px`,
      }}
    >
      <Logomark size={size} variant={variant} />
      <Wordmark fontSize={wordmarkSize} variant={variant} />
    </span>
  );
}

// ---------------------------------------------------------------------------
// ProfilePic — square with rounded corners, dark bg, centred mark
// ---------------------------------------------------------------------------

/**
 * @param {object} props
 * @param {number} [props.size=256] - Outer dimension in px
 * @param {string} [props.background] - Override background colour
 * @param {"color"|"mono-dark"|"mono-light"} [props.variant="color"]
 * @param {string} [props.className]
 */
export function ProfilePic({
  size = 256,
  background,
  variant = "color",
  className,
} = {}) {
  const bg = background || PALETTE.anvilBlack;
  const markSize = size * 0.62;

  return (
    <span
      className={className}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: `${size}px`,
        height: `${size}px`,
        borderRadius: "18%",
        backgroundColor: bg,
      }}
    >
      <Logomark size={markSize} variant={variant} />
    </span>
  );
}

// ---------------------------------------------------------------------------
// SocialCard — 1200 x 630 Open Graph image
// ---------------------------------------------------------------------------

/**
 * @param {object} props
 * @param {"color"|"mono-dark"|"mono-light"} [props.variant="color"]
 * @param {string} [props.className]
 */
export function SocialCard({ variant = "color", className } = {}) {
  return (
    <div
      className={className}
      style={{
        width: "1200px",
        height: "630px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: PALETTE.anvilBlack,
        backgroundImage:
          "radial-gradient(circle at 30% 50%, rgba(194,102,45,0.35) 0%, rgba(194,102,45,0) 55%)",
        position: "relative",
      }}
    >
      <Logo size={120} layout="horizontal" variant={variant} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// GitHubBanner — 1280 x 640 repository social preview
// ---------------------------------------------------------------------------

/**
 * @param {object} props
 * @param {"color"|"mono-dark"|"mono-light"} [props.variant="color"]
 * @param {string} [props.className]
 */
export function GitHubBanner({ variant = "color", className } = {}) {
  return (
    <div
      className={className}
      style={{
        width: "1280px",
        height: "640px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: PALETTE.anvilBlack,
        backgroundImage:
          "radial-gradient(circle at 30% 50%, rgba(194,102,45,0.35) 0%, rgba(194,102,45,0) 55%)",
        position: "relative",
      }}
    >
      <Logo size={140} layout="horizontal" variant={variant} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Default export — namespace object
// ---------------------------------------------------------------------------

export default {
  Logomark,
  Wordmark,
  Logo,
  ProfilePic,
  SocialCard,
  GitHubBanner,
  PALETTE,
  FONT_STACK,
  resolveColors,
};
