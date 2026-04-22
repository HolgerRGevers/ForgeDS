import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useWizardStore } from "../stores/wizardStore";
import { useAuthStore } from "../stores/authStore";
import { useRepoStore } from "../stores/repoStore";
import { useIdeStore } from "../stores/ideStore";
import { useToastStore } from "../stores/toastStore";
import { BuildProgress } from "../components/BuildProgress";
import { buildProject } from "../services/claude-api";
import { dropManifest } from "../services/github-repos";

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

      // Build the spec payload from wizard state
      const spec = JSON.stringify({
        coreIdea,
        depth,
        entryTab,
        midSeedAnswers,
        questions,
        answers,
        dataAnalysis,
      });

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
                content: spec,
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
              log(
                err instanceof Error
                  ? `Manifest drop failed: ${err.message}`
                  : "Manifest drop failed",
                "warning",
              );
            }
          }

          // Load files into IDE, show toast, reset wizard, navigate to IDE
          useIdeStore.getState().loadGeneratedFiles(files);
          useToastStore
            .getState()
            .success(
              "Build complete",
              `${files.length} file(s) committed to ${branch}`,
            );
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
    setGeneratedFiles,
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
