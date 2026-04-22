import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useWizardStore } from "../stores/wizardStore";
import { useAuthStore } from "../stores/authStore";
import { IdeaInput } from "../components/IdeaInput";
import { DataAnalysisPanel } from "../components/wizard/DataAnalysisPanel";
import { parseAttachments, analyzeData } from "../services/data-ingestion";

export default function IdeaPage() {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const entryTab = useWizardStore((s) => s.entryTab);
  const setCoreIdea = useWizardStore((s) => s.setCoreIdea);
  const setEntryParams = useWizardStore((s) => s.setEntryParams);
  const setStep = useWizardStore((s) => s.setStep);
  const setDataAnalysis = useWizardStore((s) => s.setDataAnalysis);
  const setDataIngestionStatus = useWizardStore((s) => s.setDataIngestionStatus);
  const repoCreationStatus = useWizardStore((s) => s.repoCreationStatus);
  const repoCreationError = useWizardStore((s) => s.repoCreationError);
  const dataAnalysis = useWizardStore((s) => s.dataAnalysis);

  useEffect(() => {
    setStep("idea");
  }, [setStep]);

  const isFromData = entryTab === "from-data";
  const placeholder = isFromData
    ? "We've parsed your data. Now tell us what pain point this app should solve and who uses it."
    : "Describe your core idea — what does this app do, and for whom?";

  const onSubmit = (text: string, files: File[]) => {
    setCoreIdea(text);
    if (files.length > 0) {
      setEntryParams({ attachments: files });
    }

    if (isFromData && files.length > 0 && token) {
      setDataIngestionStatus("parsing");
      void parseAttachments(files)
        .then((parsed) => {
          setDataIngestionStatus("analyzing");
          return analyzeData(token, parsed);
        })
        .then((analysis) => {
          setDataAnalysis(analysis);
          setDataIngestionStatus("ready");
        })
        .catch(() => {
          setDataIngestionStatus("failed");
        });
    }

    navigate("/new/depth");
  };

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col items-center justify-center gap-6 p-6">
      <h1 className="text-xl font-semibold text-white">
        {isFromData ? "Tell us why" : "What do you want to build?"}
      </h1>

      {repoCreationStatus === "failed" && (
        <div className="w-full max-w-2xl rounded-md border border-red-500/40 bg-red-950/30 px-4 py-3 text-sm text-red-200">
          Background repo creation failed: {repoCreationError ?? "unknown error"}.
          You can edit the project name in the dashboard rail and try again, or switch to "Use existing repo".
        </div>
      )}

      <IdeaInput
        placeholder={placeholder}
        acceptAttachments={isFromData}
        onSubmit={onSubmit}
      />

      {isFromData && dataAnalysis && (
        <DataAnalysisPanel analysis={dataAnalysis} />
      )}
    </div>
  );
}
