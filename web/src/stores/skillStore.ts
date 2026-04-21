import { create } from "zustand";
import { SKILLS, type Skill, type SkillCategory } from "../data/skills";
import * as gh from "../services/github-api";
import { useAuthStore } from "./authStore";

const ACTIVE_SKILLS_KEY = "forgeds-active-skills";
const GITHUB_SKILLS_KEY = "forgeds-github-skills";
const INSTALLED_REPOS_KEY = "forgeds-installed-repos";

function loadActiveSkills(): string[] {
  try {
    const raw = localStorage.getItem(ACTIVE_SKILLS_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function loadGithubSkills(): Skill[] {
  try {
    const raw = localStorage.getItem(GITHUB_SKILLS_KEY);
    return raw ? (JSON.parse(raw) as Skill[]) : [];
  } catch {
    return [];
  }
}

function loadInstalledRepos(): string[] {
  try {
    const raw = localStorage.getItem(INSTALLED_REPOS_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

export interface SkillState {
  availableSkills: Skill[];
  githubSkills: Skill[];
  activeSkillIds: string[];
  installedRepos: string[];
  importLoading: boolean;
  importError: string | null;

  toggleSkill: (id: string) => void;
  activateSkill: (id: string) => void;
  deactivateSkill: (id: string) => void;
  clearAllSkills: () => void;
  getActiveSystemPrompt: () => string;
  loadSkillsFromRepo: (owner: string, repo: string, path?: string) => Promise<number>;
  removeImportedRepo: (fullName: string) => void;
}

export const useSkillStore = create<SkillState>((set, get) => ({
  availableSkills: SKILLS,
  githubSkills: loadGithubSkills(),
  activeSkillIds: loadActiveSkills(),
  installedRepos: loadInstalledRepos(),
  importLoading: false,
  importError: null,

  toggleSkill: (id: string) => {
    const { activeSkillIds } = get();
    const next = activeSkillIds.includes(id)
      ? activeSkillIds.filter((s) => s !== id)
      : [...activeSkillIds, id];
    localStorage.setItem(ACTIVE_SKILLS_KEY, JSON.stringify(next));
    set({ activeSkillIds: next });
  },

  activateSkill: (id: string) => {
    const { activeSkillIds } = get();
    if (!activeSkillIds.includes(id)) {
      const next = [...activeSkillIds, id];
      localStorage.setItem(ACTIVE_SKILLS_KEY, JSON.stringify(next));
      set({ activeSkillIds: next });
    }
  },

  deactivateSkill: (id: string) => {
    const next = get().activeSkillIds.filter((s) => s !== id);
    localStorage.setItem(ACTIVE_SKILLS_KEY, JSON.stringify(next));
    set({ activeSkillIds: next });
  },

  clearAllSkills: () => {
    localStorage.removeItem(ACTIVE_SKILLS_KEY);
    set({ activeSkillIds: [] });
  },

  getActiveSystemPrompt: () => {
    const { availableSkills, githubSkills, activeSkillIds } = get();
    if (activeSkillIds.length === 0) return "";
    const all = [...availableSkills, ...githubSkills];
    const active = all.filter((s) => activeSkillIds.includes(s.id));
    return active.map((s) => `[${s.name}] ${s.systemPrompt}`).join("\n\n");
  },

  loadSkillsFromRepo: async (owner, repo, path = "skills") => {
    const token = useAuthStore.getState().token;
    if (!token) throw new Error("Not authenticated");

    set({ importLoading: true, importError: null });
    try {
      // Get the directory listing
      const tree = await gh.getTree(token, owner, repo, "HEAD", true);
      const skillFiles = tree.tree.filter(
        (entry) =>
          entry.type === "blob" &&
          entry.path.startsWith(path) &&
          (entry.path.endsWith(".json")),
      );

      if (skillFiles.length === 0) {
        set({ importError: `No skill files found in ${owner}/${repo}/${path}` });
        return 0;
      }

      const imported: Skill[] = [];
      for (const file of skillFiles) {
        try {
          const content = await gh.getFileContent(token, owner, repo, file.path);
          const decoded = decodeURIComponent(
            escape(atob(content.content.replace(/\n/g, ""))),
          );
          const data = JSON.parse(decoded);

          // Validate minimum fields
          if (data.id && data.name && data.systemPrompt) {
            imported.push({
              id: `${owner}/${repo}/${data.id}`,
              name: data.name,
              category: (data.category as SkillCategory) ?? "general",
              description: data.description ?? "",
              systemPrompt: data.systemPrompt,
              examplePrompts: data.examplePrompts ?? [],
              tags: data.tags ?? [],
              source: "github",
            });
          }
        } catch {
          // Skip invalid files
        }
      }

      const fullName = `${owner}/${repo}`;
      const { githubSkills, installedRepos } = get();

      // Remove any previously imported skills from this repo
      const filtered = githubSkills.filter(
        (s) => !s.id.startsWith(`${fullName}/`),
      );
      const nextSkills = [...filtered, ...imported];
      const nextRepos = installedRepos.includes(fullName)
        ? installedRepos
        : [...installedRepos, fullName];

      localStorage.setItem(GITHUB_SKILLS_KEY, JSON.stringify(nextSkills));
      localStorage.setItem(INSTALLED_REPOS_KEY, JSON.stringify(nextRepos));
      set({ githubSkills: nextSkills, installedRepos: nextRepos });

      return imported.length;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Import failed";
      set({ importError: message });
      return 0;
    } finally {
      set({ importLoading: false });
    }
  },

  removeImportedRepo: (fullName) => {
    const { githubSkills, installedRepos, activeSkillIds } = get();
    const nextSkills = githubSkills.filter(
      (s) => !s.id.startsWith(`${fullName}/`),
    );
    const nextRepos = installedRepos.filter((r) => r !== fullName);
    // Deactivate removed skills
    const removedIds = new Set(
      githubSkills
        .filter((s) => s.id.startsWith(`${fullName}/`))
        .map((s) => s.id),
    );
    const nextActive = activeSkillIds.filter((id) => !removedIds.has(id));

    localStorage.setItem(GITHUB_SKILLS_KEY, JSON.stringify(nextSkills));
    localStorage.setItem(INSTALLED_REPOS_KEY, JSON.stringify(nextRepos));
    localStorage.setItem(ACTIVE_SKILLS_KEY, JSON.stringify(nextActive));
    set({
      githubSkills: nextSkills,
      installedRepos: nextRepos,
      activeSkillIds: nextActive,
    });
  },
}));
