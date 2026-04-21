import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useWizardStore } from "../../stores/wizardStore";
import { useRepoStore } from "../../stores/repoStore";
import { EntryTabs } from "./EntryTabs";
import type { EntryTab } from "../../types/wizard";

export function RailWizard() {
  const navigate = useNavigate();
  const setEntryParams = useWizardStore((s) => s.setEntryParams);
  const reset = useWizardStore((s) => s.reset);
  const repos = useRepoStore((s) => s.repos);

  const [tab, setTab] = useState<EntryTab>("prototype");
  const [name, setName] = useState("");
  const [target, setTarget] = useState<"create-new" | "use-existing">("create-new");
  const [existingRepo, setExistingRepo] = useState<string>("");

  const onContinue = () => {
    if (!name.trim()) {
      alert("Please give the prototype a name.");
      return;
    }
    if (target === "use-existing" && !existingRepo) {
      alert("Pick an existing repo or switch to 'Create new repo'.");
      return;
    }
    reset();
    setEntryParams({
      entryTab: tab,
      projectName: name.trim(),
      targetMode: target,
      targetRepoFullName: target === "use-existing" ? existingRepo : null,
      attachments: [],
    });
    navigate("/new/idea");
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="text-sm font-semibold text-white">New prototype</div>
      <EntryTabs value={tab} onChange={setTab} />

      <label className="mt-1 text-[11px] font-semibold text-gray-300">
        Project name
      </label>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g. Travel Expense Tracker"
        className="rounded-md border border-white/10 bg-black/40 px-3 py-2 text-xs text-white placeholder-gray-500"
      />

      <label className="mt-1 text-[11px] font-semibold text-gray-300">
        Where should it go?
      </label>
      <div className="flex flex-col gap-1">
        <label
          className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs cursor-pointer ${
            target === "create-new"
              ? "border-[#c2662d] bg-[#c2662d]/10 text-white"
              : "border-white/10 text-gray-300"
          }`}
        >
          <input
            type="radio"
            name="target"
            checked={target === "create-new"}
            onChange={() => setTarget("create-new")}
            className="accent-[#c2662d]"
          />
          Create new repo
        </label>
        <label
          className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs cursor-pointer ${
            target === "use-existing"
              ? "border-[#c2662d] bg-[#c2662d]/10 text-white"
              : "border-white/10 text-gray-300"
          }`}
        >
          <input
            type="radio"
            name="target"
            checked={target === "use-existing"}
            onChange={() => setTarget("use-existing")}
            className="accent-[#c2662d]"
          />
          Use an existing repo
        </label>
        {target === "use-existing" && (
          <select
            value={existingRepo}
            onChange={(e) => setExistingRepo(e.target.value)}
            className="mt-1 rounded-md border border-white/10 bg-black/40 px-3 py-2 text-xs text-white"
          >
            <option value="">Select…</option>
            {repos.map((r) => (
              <option key={r.full_name} value={r.full_name}>
                {r.full_name}
              </option>
            ))}
          </select>
        )}
      </div>

      <button
        type="button"
        onClick={onContinue}
        className="mt-2 rounded-md bg-[#c2662d] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#a8551c]"
      >
        Continue →
      </button>
      <div className="text-center text-[10px] text-gray-500">
        Next: pick depth (Light / Mid / Heavy / Dev)
      </div>
    </div>
  );
}
