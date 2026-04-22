import type { WizardDepth } from "../types/wizard";
import { sanitizeRepoName } from "../lib/sanitize-repo-name";
import { useRepoStore } from "../stores/repoStore";
import { useAuthStore } from "../stores/authStore";

export interface ProjectMeta {
  displayName: string;
  createdVia: "forgeds-wizard";
  createdAt: string;
  depthUsed: WizardDepth;
  dataSourceKind: "prototype" | "from-data";
  attachmentNames: string[];
}

export async function checkScopes(): Promise<{
  hasRepoScope: boolean;
  scopes: string[];
}> {
  const token = useAuthStore.getState().token;
  if (!token) return { hasRepoScope: false, scopes: [] };
  const res = await fetch("https://api.github.com/user", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const scopes = (res.headers.get("x-oauth-scopes") ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return { hasRepoScope: scopes.includes("repo"), scopes };
}

export async function eagerCreateRepo(params: {
  projectName: string;
  description: string;
  isPrivate?: boolean;
}): Promise<string> {
  const baseName = sanitizeRepoName(params.projectName);
  const token = useAuthStore.getState().token;
  if (!token) throw new Error("Not authenticated");

  const candidate = await findFreeName(token, baseName);

  // createNewRepo signature: (name, description, isPrivate, autoInit) — positional args.
  // After creation it internally calls selectRepo(), which sets selectedRepo and
  // selectedBranch to the repo's default_branch ("main" for auto-init repos).
  await useRepoStore
    .getState()
    .createNewRepo(candidate, params.description, params.isPrivate ?? true, true);

  const created = useRepoStore.getState().selectedRepo;
  if (!created || created.name !== candidate) {
    throw new Error("Repo creation completed but selectedRepo not set");
  }
  return created.full_name;
}

async function findFreeName(token: string, base: string): Promise<string> {
  for (let i = 0; i < 6; i++) {
    const candidate = i === 0 ? base : `${base}-${i + 1}`;
    const exists = await repoExists(token, candidate);
    if (!exists) return candidate;
  }
  throw new Error("Could not find a free repo name after 6 attempts");
}

async function repoExists(token: string, name: string): Promise<boolean> {
  const userRes = await fetch("https://api.github.com/user", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!userRes.ok) return false;
  const user = (await userRes.json()) as { login: string };
  const res = await fetch(
    `https://api.github.com/repos/${user.login}/${name}`,
    { method: "HEAD", headers: { Authorization: `Bearer ${token}` } },
  );
  return res.status === 200;
}

export async function dropManifest(
  fullName: string,
  meta: ProjectMeta,
): Promise<void> {
  // Adaptation note: batchUploadToBranch always creates a NEW branch from the
  // current HEAD — it cannot target an existing branch (e.g. "main").
  // batchUploadFiles, by contrast, writes to selectedRepo + selectedBranch as-is.
  // Since eagerCreateRepo calls createNewRepo → selectRepo, selectedBranch is already
  // set to the repo's default_branch ("main"). We use option (a): call
  // setSelectedRepoByFullName to guarantee the correct repo is active, then use
  // batchUploadFiles (which writes to selectedBranch = "main").
  await useRepoStore.getState().setSelectedRepoByFullName(fullName);

  const yaml = `project:
  name: ${meta.displayName}
  created_via: ${meta.createdVia}
  created_at: ${meta.createdAt}
  depth_used: ${meta.depthUsed}
data_source:
  kind: ${meta.dataSourceKind}
  attachments: [${meta.attachmentNames.map((n) => `"${n}"`).join(", ")}]
`;

  await useRepoStore.getState().batchUploadFiles(
    [{ path: "forgeds.yaml", content: yaml, isBinary: false }],
    "ForgeDS: drop project manifest",
  );
}
