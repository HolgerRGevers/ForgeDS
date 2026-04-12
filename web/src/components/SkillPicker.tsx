import { useState, useMemo } from "react";
import { useSkillStore } from "../stores/skillStore";
import { SKILL_CATEGORIES, type SkillCategory } from "../data/skills";
import { SkillMarketplace } from "./SkillMarketplace";

interface SkillPickerProps {
  onClose: () => void;
}

/**
 * Modal grid of available skills with category tabs.
 * Users toggle skills on/off to shape the AI's behavior.
 */
export function SkillPicker({ onClose }: SkillPickerProps) {
  const { availableSkills, githubSkills, activeSkillIds, toggleSkill, clearAllSkills } =
    useSkillStore();

  const [activeCategory, setActiveCategory] = useState<SkillCategory | "all">(
    "all",
  );
  const [search, setSearch] = useState("");
  const [showMarketplace, setShowMarketplace] = useState(false);

  // Combine built-in and imported skills
  const allSkills = useMemo(
    () => [...availableSkills, ...githubSkills],
    [availableSkills, githubSkills],
  );

  const filtered = useMemo(() => {
    let skills = allSkills;
    if (activeCategory !== "all") {
      skills = skills.filter((s) => s.category === activeCategory);
    }
    if (search) {
      const lower = search.toLowerCase();
      skills = skills.filter(
        (s) =>
          s.name.toLowerCase().includes(lower) ||
          s.description.toLowerCase().includes(lower) ||
          s.tags.some((t) => t.includes(lower)),
      );
    }
    return skills;
  }, [availableSkills, activeCategory, search]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-xl border border-gray-700 bg-gray-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Skills Library</h2>
            <p className="text-xs text-gray-500">
              {activeSkillIds.length} active &middot;{" "}
              {availableSkills.length} built-in &middot;{" "}
              {githubSkills.length} imported
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowMarketplace(true)}
              className="rounded border border-blue-700 bg-blue-600/10 px-2.5 py-1 text-[11px] font-medium text-blue-400 transition-colors hover:bg-blue-600/20"
            >
              Marketplace
            </button>
            {activeSkillIds.length > 0 && (
              <button
                type="button"
                onClick={clearAllSkills}
                className="text-xs text-gray-500 hover:text-gray-300"
              >
                Clear all
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="text-gray-500 hover:text-white"
            >
              &times;
            </button>
          </div>
        </div>

        {/* Search + Category tabs */}
        <div className="space-y-2 border-b border-gray-800 px-5 py-3">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search skills..."
            className="w-full rounded-md bg-gray-800 px-3 py-1.5 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <div className="flex flex-wrap gap-1">
            <CategoryTab
              label="All"
              icon=""
              active={activeCategory === "all"}
              onClick={() => setActiveCategory("all")}
            />
            {SKILL_CATEGORIES.map((cat) => (
              <CategoryTab
                key={cat.id}
                label={cat.label}
                icon={cat.icon}
                active={activeCategory === cat.id}
                onClick={() => setActiveCategory(cat.id)}
              />
            ))}
          </div>
        </div>

        {/* Skills grid */}
        <div className="flex-1 overflow-y-auto p-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {filtered.map((skill) => {
              const isActive = activeSkillIds.includes(skill.id);
              const categoryInfo = SKILL_CATEGORIES.find(
                (c) => c.id === skill.category,
              );
              return (
                <button
                  key={skill.id}
                  type="button"
                  onClick={() => toggleSkill(skill.id)}
                  className={`rounded-lg border p-3 text-left transition-all ${
                    isActive
                      ? "border-blue-500/50 bg-blue-500/10"
                      : "border-gray-800 bg-gray-800/50 hover:border-gray-700 hover:bg-gray-800"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs">
                          {categoryInfo?.icon}
                        </span>
                        <h3 className="text-xs font-semibold text-white">
                          {skill.name}
                        </h3>
                      </div>
                      <p className="mt-1 text-[11px] leading-relaxed text-gray-400">
                        {skill.description}
                      </p>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {skill.tags.slice(0, 3).map((tag) => (
                          <span
                            key={tag}
                            className="rounded bg-gray-700/60 px-1.5 py-0.5 text-[10px] text-gray-500"
                          >
                            {tag}
                          </span>
                        ))}
                        <span className="rounded bg-gray-700/40 px-1.5 py-0.5 text-[10px] text-gray-600">
                          {skill.source}
                        </span>
                      </div>
                    </div>

                    {/* Toggle indicator */}
                    <div
                      className={`ml-2 mt-0.5 flex h-4 w-8 shrink-0 items-center rounded-full p-0.5 transition-colors ${
                        isActive ? "bg-blue-600" : "bg-gray-700"
                      }`}
                    >
                      <div
                        className={`h-3 w-3 rounded-full bg-white transition-transform ${
                          isActive ? "translate-x-4" : ""
                        }`}
                      />
                    </div>
                  </div>
                </button>
              );
            })}
          </div>

          {filtered.length === 0 && (
            <p className="py-8 text-center text-xs text-gray-500">
              No skills match your search
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-gray-800 px-5 py-3">
          <p className="text-xs text-gray-500">
            Active skills shape how the AI approaches your prompts
          </p>
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-blue-600 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-500"
          >
            Done
          </button>
        </div>
      {/* Marketplace modal */}
      {showMarketplace && (
        <SkillMarketplace onClose={() => setShowMarketplace(false)} />
      )}
      </div>
    </div>
  );
}

function CategoryTab({
  label,
  icon,
  active,
  onClick,
}: {
  label: string;
  icon: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors ${
        active
          ? "bg-blue-600/20 text-blue-400"
          : "text-gray-500 hover:bg-gray-800 hover:text-gray-300"
      }`}
    >
      {icon && <span className="mr-1">{icon}</span>}
      {label}
    </button>
  );
}
