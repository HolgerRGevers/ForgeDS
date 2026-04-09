import { create } from "zustand";
import { SKILLS, type Skill } from "../data/skills";

const ACTIVE_SKILLS_KEY = "forgeds-active-skills";

function loadActiveSkills(): string[] {
  try {
    const raw = localStorage.getItem(ACTIVE_SKILLS_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

interface SkillState {
  availableSkills: Skill[];
  activeSkillIds: string[];

  toggleSkill: (id: string) => void;
  activateSkill: (id: string) => void;
  deactivateSkill: (id: string) => void;
  clearAllSkills: () => void;
  getActiveSystemPrompt: () => string;
}

export const useSkillStore = create<SkillState>((set, get) => ({
  availableSkills: SKILLS,
  activeSkillIds: loadActiveSkills(),

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
    const { availableSkills, activeSkillIds } = get();
    if (activeSkillIds.length === 0) return "";
    const active = availableSkills.filter((s) => activeSkillIds.includes(s.id));
    return active.map((s) => `[${s.name}] ${s.systemPrompt}`).join("\n\n");
  },
}));
