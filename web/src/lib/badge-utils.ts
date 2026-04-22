const PALETTE = [
  "#c2662d",
  "#7c3aed",
  "#22c55e",
  "#0ea5e9",
  "#ec4899",
  "#f59e0b",
];

/**
 * Derive a 3-character badge initials string from a repo/app name.
 *
 * Rules:
 *   - Split on whitespace, hyphens, or underscores.
 *   - 3+ words  → first letter of each of the first 3 words.
 *   - 2 words   → first 2 letters of word 1, then first letter of word 2.
 *   - 1 word    → first 3 letters of that word.
 *   - Always uppercased, always at most 3 characters.
 */
export function deriveBadgeInitials(name: string): string {
  const words = name.split(/[\s\-_]+/).filter((w) => w.length > 0);
  if (words.length === 0) return "";

  let initials: string;
  if (words.length >= 3) {
    initials = words
      .slice(0, 3)
      .map((w) => w[0])
      .join("");
  } else if (words.length === 2) {
    const [w1, w2] = words;
    initials = w1.slice(0, 2) + w2[0];
  } else {
    initials = words[0].slice(0, 3);
  }

  return initials.toUpperCase().slice(0, 3);
}

/**
 * Map an arbitrary string to one of the badge palette colors deterministically.
 * Same input always returns the same color; different inputs spread across the palette.
 */
export function hashToBadgeColor(input: string): string {
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    hash = (hash * 31 + input.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % PALETTE.length;
  return PALETTE[idx];
}
