import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useWizardStore } from "../stores/wizardStore";
import { useAuthStore } from "../stores/authStore";
import { ConstructiveOpener } from "../components/wizard/ConstructiveOpener";
import { DepthPicker } from "../components/wizard/DepthPicker";
import { generateOpener } from "../services/brainstorming";
import type { WizardDepth } from "../types/wizard";

const SHELL = "Nice — {gist}. How deep do you want to go on this?";

export default function DepthPickerPage() {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const coreIdea = useWizardStore((s) => s.coreIdea);
  const dataAnalysis = useWizardStore((s) => s.dataAnalysis);
  const opener = useWizardStore((s) => s.opener);
  const setOpener = useWizardStore((s) => s.setOpener);
  const setDepth = useWizardStore((s) => s.setDepth);
  const setStep = useWizardStore((s) => s.setStep);

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setStep("depth");
    if (opener || !coreIdea || !token) return;
    setLoading(true);
    generateOpener(token, coreIdea, dataAnalysis)
      .then(({ gist }) => setOpener({ gist, shell: SHELL }))
      .catch(() => setOpener({ gist: "this is a solid starting point", shell: SHELL }))
      .finally(() => setLoading(false));
  }, [coreIdea, dataAnalysis, opener, setOpener, setStep, token]);

  const onPick = (d: WizardDepth) => {
    setDepth(d);
    navigate("/new/q/1");
  };

  return (
    <div className="mx-auto flex h-full max-w-4xl flex-col items-center justify-center gap-6 p-6">
      {loading ? (
        <div className="text-sm text-gray-500">Reading your idea…</div>
      ) : (
        opener && <ConstructiveOpener shell={opener.shell} gist={opener.gist} />
      )}
      <DepthPicker onPick={onPick} />
    </div>
  );
}
