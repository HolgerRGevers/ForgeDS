/**
 * Curated list of known skill repositories for the marketplace.
 */

export interface MarketplaceRepo {
  owner: string;
  repo: string;
  name: string;
  description: string;
  skillCount: string;
  category: string;
  featured: boolean;
}

export const MARKETPLACE_REPOS: MarketplaceRepo[] = [
  {
    owner: "VoltAgent",
    repo: "awesome-agent-skills",
    name: "VoltAgent Agent Skills",
    description:
      "1000+ community skills cross-compatible with Claude Code, Codex, and Gemini CLI",
    skillCount: "1000+",
    category: "General",
    featured: true,
  },
  {
    owner: "daymade",
    repo: "claude-code-skills",
    name: "Claude Code Skills",
    description: "43 production-ready professional skills for Claude Code",
    skillCount: "43",
    category: "Development",
    featured: true,
  },
  {
    owner: "VoltAgent",
    repo: "awesome-claude-code-subagents",
    name: "Claude Code Subagents",
    description:
      "100+ specialized subagents in 10 categories including business, data, and API design",
    skillCount: "100+",
    category: "AI Agents",
    featured: true,
  },
  {
    owner: "NirDiamant",
    repo: "Prompt_Engineering",
    name: "Prompt Engineering Tutorials",
    description:
      "22 hands-on tutorials with executable code for CoT, few-shot, self-consistency",
    skillCount: "22",
    category: "Prompt Engineering",
    featured: false,
  },
  {
    owner: "promptslab",
    repo: "Awesome-Prompt-Engineering",
    name: "Awesome Prompt Engineering",
    description:
      "Curated prompt engineering resources for GPT, Claude, and PaLM",
    skillCount: "50+",
    category: "Prompt Engineering",
    featured: false,
  },
];
