export function sanitizeRepoName(input: string): string {
  let s = input.toLowerCase();
  s = s.replace(/[^a-z0-9._-]+/g, "-");
  s = s.replace(/-+/g, "-");
  s = s.replace(/^-+|-+$/g, "");
  s = s.slice(0, 100);
  return s || "untitled";
}
