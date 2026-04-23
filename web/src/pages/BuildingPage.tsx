import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useWizardStore } from "../stores/wizardStore";
import { useAuthStore } from "../stores/authStore";
import { useRepoStore } from "../stores/repoStore";
import { useIdeStore } from "../stores/ideStore";
import { useToastStore } from "../stores/toastStore";
import { useDashboardStore } from "../stores/dashboardStore";
import { BuildProgress } from "../components/BuildProgress";
import { buildProject } from "../services/claude-api";
import { dropManifest } from "../services/github-repos";
import { fanoutSpec, personaRoundTable } from "../services/multi-agent";
import type { PairedQuestion } from "../types/wizard";

export default function BuildingPage() {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const setStep = useWizardStore((s) => s.setStep);
  const depth = useWizardStore((s) => s.depth);
  const coreIdea = useWizardStore((s) => s.coreIdea);
  const projectName = useWizardStore((s) => s.projectName);
  const targetMode = useWizardStore((s) => s.targetMode);
  const targetRepoFullName = useWizardStore((s) => s.targetRepoFullName);
  const createdRepoFullName = useWizardStore((s) => s.createdRepoFullName);
  const repoCreationPromise = useWizardStore((s) => s.repoCreationPromise);
  const buildMessages = useWizardStore((s) => s.buildMessages);
  const addBuildMessage = useWizardStore((s) => s.addBuildMessage);
  const setBuildMessages = useWizardStore((s) => s.setBuildMessages);
  const setGeneratedFiles = useWizardStore((s) => s.setGeneratedFiles);
  const entryTab = useWizardStore((s) => s.entryTab);
  const attachments = useWizardStore((s) => s.attachments);
  const questions = useWizardStore((s) => s.questions);
  const answers = useWizardStore((s) => s.answers);
  const midSeedAnswers = useWizardStore((s) => s.midSeedAnswers);
  const dataAnalysis = useWizardStore((s) => s.dataAnalysis);
  const reset = useWizardStore((s) => s.reset);
  const setFanoutDrafts = useWizardStore((s) => s.setFanoutDrafts);
  const setPersonaCritiques = useWizardStore((s) => s.setPersonaCritiques);

  const startedRef = useRef(false);

  useEffect(() => {
    setStep("building");
    if (startedRef.current) return;
    startedRef.current = true;
    void run();

    async function run() {
      if (!token || !depth) return;
      setBuildMessages([]);

      const log = (
        text: string,
        type: "info" | "success" | "error" | "warning" = "info",
      ) => {
        addBuildMessage({
          timestamp: new Date().toLocaleTimeString(),
          text,
          type,
        });
      };

      log("Starting build…");

      // Resolve the target repo full name
      let repoFullName =
        targetMode === "use-existing" ? targetRepoFullName : createdRepoFullName;

      if (targetMode === "create-new" && !repoFullName && repoCreationPromise) {
        log("Waiting for new repo to finish provisioning…");
        try {
          repoFullName = await repoCreationPromise;
        } catch (err) {
          log(
            err instanceof Error
              ? `Repo creation failed: ${err.message}`
              : "Repo creation failed",
            "error",
          );
          return;
        }
      }

      if (!repoFullName) {
        log("No target repo — cannot commit.", "error");
        return;
      }

      // Build the final spec — for Heavy/Dev, run fanout (and optionally round-table) first.
      let finalSpec = JSON.stringify({
        coreIdea,
        depth,
        entryTab,
        midSeedAnswers,
        questions,
        answers,
        dataAnalysis,
      });

      if (depth === "heavy" || depth === "dev") {
        log("Heavy mode: dispatching parallel-agent fanout…");
        try {
          const pairedOnly = questions.filter(
            (q): q is PairedQuestion => q.kind === "paired",
          );
          const fanout = await fanoutSpec({
            token,
            coreIdea,
            depth,
            midSeedAnswers,
            questions: pairedOnly,
            answers,
            dataAnalysis,
            onProgress: (msg) =>
              log(
                `[${msg.agent}] ${msg.phase}${msg.preview ? `: ${msg.preview}` : ""}`,
              ),
          });
          setFanoutDrafts(fanout.drafts);
          finalSpec = fanout.synthesised;
          if (fanout.divergences.length > 0) {
            log(
              `Synthesis flagged ${fanout.divergences.length} divergence(s).`,
              "warning",
            );
          }
        } catch (err) {
          log(
            err instanceof Error ? `Fanout failed: ${err.message}` : "Fanout failed",
            "error",
          );
          return;
        }
      }

      if (depth === "dev") {
        log("Dev mode: persona round-table critique…");
        try {
          const rt = await personaRoundTable({
            token,
            spec: finalSpec,
            onProgress: (msg) =>
              log(
                `[${msg.persona}] ${msg.phase}${msg.critique ? `: ${msg.critique}` : ""}`,
              ),
          });
          setPersonaCritiques(rt.critiques);
          finalSpec = rt.revisedSpec;
        } catch (err) {
          log(
            err instanceof Error
              ? `Round-table partial: ${err.message}`
              : "Round-table failed",
            "warning",
          );
          // Don't return — fall through with whatever spec we have.
        }
      }

      try {
        // buildProject(token, BuildRequest, onChunk) — SSE streaming
        const result = await buildProject(
          token,
          {
            sections: [
              {
                id: "spec",
                title: "Wizard Spec",
                icon: "🛠",
                content: finalSpec,
                items: [],
                isEditable: false,
              },
            ],
            prompt: coreIdea,
          },
          (chunk) => {
            if (chunk.message) log(chunk.message, chunk.type ?? "info");
          },
        );

        const files = result.files ?? [];
        setGeneratedFiles(files);

        if (files.length > 0) {
          // Create a timestamped feature branch (forgeds/<ts>)
          const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
          const branch = `forgeds/${ts}`;

          // Ensure the correct repo is selected before uploading
          await useRepoStore.getState().setSelectedRepoByFullName(repoFullName);

          log(`Committing ${files.length} file(s) to branch ${branch}…`);
          await useRepoStore.getState().batchUploadToBranch(
            branch,
            files.map((f) => ({ path: f.path, content: f.content, isBinary: false })),
            `ForgeDS: build ${projectName} (${depth})`,
          );
          log(`Committed to ${branch}`, "success");

          // Drop the manifest only for newly-created repos
          if (targetMode === "create-new") {
            try {
              await dropManifest(repoFullName, {
                displayName: projectName,
                createdVia: "forgeds-wizard",
                createdAt: new Date().toISOString(),
                depthUsed: depth,
                dataSourceKind: entryTab,
                attachmentNames: attachments.map((f) => f.name),
              });
            } catch (err) {
              const msg =
                err instanceof Error ? err.message : "Manifest drop failed";
              log(`Manifest drop failed: ${msg}`, "warning");
              // Post a toast that survives navigation so the user sees it in the IDE.
              useToastStore
                .getState()
                .error(
                  "Manifest drop failed",
                  `${msg}. The repo won't auto-surface on the dashboard.`,
                );
            }
          }

          // Load files into IDE, show toast, reset wizard, navigate to IDE
          useIdeStore.getState().setAppLoadSource("wizard");
          useIdeStore.getState().loadGeneratedFiles(files);
          useToastStore
            .getState()
            .success(
              "Build complete",
              `${files.length} file(s) committed to ${branch}`,
            );
          // I3: Fire-and-forget refresh so the newly-provisioned repo surfaces on
          // the dashboard next time the user returns, without waiting for the TTL.
          void useDashboardStore.getState().refresh(true);
          reset();
          navigate("/ide");
        } else {
          log("Build returned no files.", "warning");
        }
      } catch (err) {
        log(err instanceof Error ? err.message : "Build failed", "error");
      }
    }
  }, [
    addBuildMessage,
    answers,
    attachments,
    coreIdea,
    createdRepoFullName,
    dataAnalysis,
    depth,
    entryTab,
    midSeedAnswers,
    navigate,
    projectName,
    questions,
    repoCreationPromise,
    reset,
    setBuildMessages,
    setFanoutDrafts,
    setGeneratedFiles,
    setPersonaCritiques,
    setStep,
    targetMode,
    targetRepoFullName,
    token,
  ]);

  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="w-full max-w-3xl">
        <BuildProgress
          messages={buildMessages}
          isBuilding={true}
          isComplete={false}
          onOpenIDE={() => navigate("/ide")}
        />
      </div>
    </div>
  );
}
