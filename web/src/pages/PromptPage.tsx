import { useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  PromptInput,
  RefinedPrompt,
  BuildProgress,
  CodePreview,
  ProjectHistory,
} from "../components";
import { useAuthStore } from "../stores/authStore";
import { useRepoStore } from "../stores/repoStore";
import { useIdeStore } from "../stores/ideStore";
import { usePromptStore } from "../stores/promptStore";
import { useToastStore } from "../stores/toastStore";
import {
  refinePrompt,
  buildProject,
  isConfigured,
  ClaudeApiNotConfiguredError,
} from "../services/claude-api";
import { TokenExpiredError } from "../services/github-api";
import type {
  RefinedSection,
  ProjectHistoryItem,
  RepoFile,
} from "../types/prompt";
import { useState } from "react";

const HISTORY_KEY = "forgeds-project-history";

function loadHistory(): ProjectHistoryItem[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? (JSON.parse(raw) as ProjectHistoryItem[]) : [];
  } catch {
    return [];
  }
}

function saveHistory(items: ProjectHistoryItem[]) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(items));
}

export default function PromptPage() {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const handleTokenExpired = useAuthStore((s) => s.handleTokenExpired);
  const toast = useToastStore;

  // Prompt workflow state from store (persists across navigation)
  const stage = usePromptStore((s) => s.stage);
  const isLoading = usePromptStore((s) => s.isLoading);
  const mode = usePromptStore((s) => s.mode);
  const sections = usePromptStore((s) => s.sections);
  const buildMessages = usePromptStore((s) => s.buildMessages);
  const generatedFiles = usePromptStore((s) => s.generatedFiles);
  const activeFileIndex = usePromptStore((s) => s.activeFileIndex);
  const planSteps = usePromptStore((s) => s.planSteps);
  const rightPanelOpen = usePromptStore((s) => s.rightPanelOpen);

  const ps = usePromptStore.getState;

  // Project history (localStorage)
  const [history, setHistory] = useState<ProjectHistoryItem[]>(() =>
    loadHistory(),
  );

  useEffect(() => {
    saveHistory(history);
  }, [history]);

  // --- Error handler ---
  const handleError = useCallback(
    (err: unknown) => {
      if (err instanceof TokenExpiredError) {
        handleTokenExpired();
        return;
      }
      if (err instanceof ClaudeApiNotConfiguredError) {
        toast.getState().error(
          "AI not configured",
          "The Claude API proxy is not set up. Set the VITE_CLAUDE_API_PROXY environment variable and redeploy.",
        );
        return;
      }
      const message = err instanceof Error ? err.message : "Unknown error";
      if (message.includes("429")) {
        toast.getState().error("Rate limited", "Too many requests. Please wait a moment and try again.");
      } else {
        toast.getState().error("Error", message);
      }
    },
    [handleTokenExpired, toast],
  );

  // --- Handlers ---

  const handlePromptSubmit = useCallback(
    async (prompt: string, files: File[], repoFiles: RepoFile[] = []) => {
      if (!token) {
        handleTokenExpired();
        return;
      }

      const store = usePromptStore.getState();
      store.setPromptText(prompt);
      store.setIsLoading(true);

      const repoContext = repoFiles.map((rf) => ({
        path: rf.path,
        content: rf.content,
        source: rf.repoName,
      }));

      try {
        if (!isConfigured()) {
          throw new ClaudeApiNotConfiguredError();
        }

        const fileNames = files.map((f) => f.name);
        const response = await refinePrompt(token, {
          prompt,
          files: fileNames,
          repoContext,
          mode,
        });

        if (mode === "plan") {
          const steps = response.planSteps ?? [
            "Analyze requirements",
            "Identify forms and fields",
            "Design workflows",
            "Generate code",
          ];
          store.setPlanSteps(steps);
          const refined = response.sections ?? [
            {
              id: "1",
              title: "Project Overview",
              icon: "\u{1F4CB}",
              content: prompt,
              items: steps,
              isEditable: true,
            },
          ];
          store.setSections(refined);
          store.setStage("planning");
        } else {
          const refined = response.sections ?? [
            {
              id: "1",
              title: "Project Overview",
              icon: "\u{1F4CB}",
              content: prompt,
              items: [],
              isEditable: true,
            },
          ];
          store.setSections(refined);
          store.setStage("refined");
        }
      } catch (err) {
        handleError(err);
        store.setSections([
          {
            id: "fallback",
            title: "Your Prompt",
            icon: "\u{1F4CB}",
            content: prompt,
            items: [],
            isEditable: true,
          },
        ]);
        store.setStage(mode === "plan" ? "planning" : "refined");
      } finally {
        store.setIsLoading(false);
      }
    },
    [token, handleTokenExpired, handleError, mode],
  );

  const handleSectionUpdate = useCallback(
    (sectionId: string, updates: Partial<RefinedSection>) => {
      usePromptStore.getState().updateSection(sectionId, updates);
    },
    [],
  );

  const handleBuild = useCallback(async () => {
    if (!token) {
      handleTokenExpired();
      return;
    }

    const store = usePromptStore.getState();
    store.setStage("building");
    store.setBuildMessages([]);
    store.setGeneratedFiles([]);
    store.setActiveFileIndex(0);

    const addMessage = (msg: { text: string; type: "info" | "success" | "error" | "warning" }) => {
      usePromptStore.getState().addBuildMessage({
        timestamp: new Date().toLocaleTimeString(),
        ...msg,
      });
    };

    addMessage({ text: "Starting build...", type: "info" });

    try {
      if (!isConfigured()) {
        throw new ClaudeApiNotConfiguredError();
      }

      const currentSections = usePromptStore.getState().sections;
      const currentPrompt = usePromptStore.getState().promptText;

      const result = await buildProject(
        token,
        { sections: currentSections, prompt: currentPrompt },
        (chunk) => {
          if (chunk.message) {
            addMessage({ text: chunk.message, type: chunk.type ?? "info" });
          }
        },
      );

      const files = result.files ?? [];
      usePromptStore.getState().setGeneratedFiles(files);

      addMessage({
        text: `Build complete! Generated ${files.length} file(s).`,
        type: "success",
      });

      // Auto-commit to a feature branch if a repo is selected
      const repo = useRepoStore.getState().selectedRepo;
      if (repo && files.length > 0) {
        const now = new Date();
        const ts = now.toISOString().replace(/[:.]/g, "-").slice(0, 19);
        const branchName = `forgeds/${ts}`;

        addMessage({ text: `Committing to branch ${branchName}...`, type: "info" });

        try {
          const uploadFiles = files.map((f) => ({
            path: f.path,
            content: f.content,
            isBinary: false,
          }));
          await useRepoStore.getState().batchUploadToBranch(
            branchName,
            uploadFiles,
            `ForgeDS: generate ${files.length} file(s) from prompt`,
          );

          addMessage({
            text: `Committed to ${repo.full_name} on branch ${branchName}`,
            type: "success",
          });

          toast.getState().success(
            "Code committed",
            `${files.length} file${files.length !== 1 ? "s" : ""} pushed to ${branchName}`,
          );
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Commit failed";
          addMessage({ text: `Auto-commit failed: ${msg}`, type: "warning" });
          toast.getState().error("Auto-commit failed", msg);
        }
      }

      usePromptStore.getState().setStage("complete");

      // Save to history
      const entry: ProjectHistoryItem = {
        id: crypto.randomUUID(),
        prompt: currentPrompt,
        timestamp: Date.now(),
        fileCount: files.length,
      };
      setHistory((prev) => [entry, ...prev]);

      if (!repo) {
        toast.getState().success(
          "Build complete",
          `Generated ${files.length} file${files.length !== 1 ? "s" : ""}. Select a repo to auto-commit.`,
        );
      }
    } catch (err) {
      handleError(err);
      addMessage({
        text: err instanceof Error ? err.message : "Build failed. Please try again.",
        type: "error",
      });
    }
  }, [token, handleTokenExpired, handleError, toast]);

  const handleStartOver = useCallback(() => {
    usePromptStore.getState().reset();
  }, []);

  const handleOpenIDE = useCallback(() => {
    const files = usePromptStore.getState().generatedFiles;
    if (files.length > 0) {
      useIdeStore.getState().loadGeneratedFiles(files);
    }
    navigate("/ide");
  }, [navigate]);

  const handleHistorySelect = useCallback((id: string) => {
    const item = loadHistory().find((h) => h.id === id);
    if (item) {
      const store = usePromptStore.getState();
      store.reset();
      store.setPromptText(item.prompt);
    }
  }, []);

  const handleHistoryDelete = useCallback((id: string) => {
    setHistory((prev) => prev.filter((h) => h.id !== id));
  }, []);

  const handleHistoryClearAll = useCallback(() => {
    setHistory([]);
  }, []);

  const handleApprovePlan = useCallback(() => {
    const store = usePromptStore.getState();
    store.setMode("code");
    store.setStage("refined");
  }, []);

  function renderCenter() {
    switch (stage) {
      case "input":
        return (
          <div className="flex h-full items-center justify-center p-6">
            <div className="w-full max-w-2xl">
              <PromptInput
                onSubmit={handlePromptSubmit}
                isLoading={isLoading}
                mode={mode}
                onModeChange={(m) => usePromptStore.getState().setMode(m)}
              />
            </div>
          </div>
        );
      case "planning":
        return (
          <div className="h-full overflow-y-auto p-6">
            <div className="mx-auto max-w-2xl space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-white">Plan</h2>
                <span className="rounded-full bg-blue-600/20 px-3 py-1 text-xs font-medium text-blue-400">
                  Plan Mode
                </span>
              </div>
              <div className="space-y-2">
                {planSteps.map((step, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 rounded-lg border border-gray-800 bg-gray-900 px-4 py-3"
                  >
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gray-700 text-xs font-medium text-gray-300">
                      {i + 1}
                    </span>
                    <span className="text-sm text-gray-300">{step}</span>
                  </div>
                ))}
              </div>
              <RefinedPrompt
                sections={sections}
                onSectionUpdate={handleSectionUpdate}
                onConfirm={handleApprovePlan}
                onStartOver={handleStartOver}
              />
            </div>
          </div>
        );
      case "refined":
        return (
          <div className="h-full overflow-y-auto p-6">
            <RefinedPrompt
              sections={sections}
              onSectionUpdate={handleSectionUpdate}
              onConfirm={handleBuild}
              onStartOver={handleStartOver}
            />
          </div>
        );
      case "building":
        return (
          <div className="h-full overflow-y-auto p-6">
            <BuildProgress
              messages={buildMessages}
              isBuilding={true}
              isComplete={false}
              onOpenIDE={handleOpenIDE}
            />
          </div>
        );
      case "complete":
        return (
          <div className="h-full overflow-y-auto p-6">
            <BuildProgress
              messages={buildMessages}
              isBuilding={false}
              isComplete={true}
              onOpenIDE={handleOpenIDE}
            />
            <div className="mt-4 flex justify-center">
              <button
                type="button"
                onClick={handleStartOver}
                className="rounded border border-gray-600 px-4 py-2 text-sm text-gray-300 transition-colors hover:border-gray-400 hover:text-white"
              >
                Start Over
              </button>
            </div>
          </div>
        );
    }
  }

  return (
    <div className="flex h-full">
      <aside className="w-64 shrink-0 overflow-y-auto border-r border-gray-800 bg-gray-900">
        <ProjectHistory
          items={history}
          onSelect={handleHistorySelect}
          onDelete={handleHistoryDelete}
          onClearAll={handleHistoryClearAll}
        />
      </aside>

      <div className="flex-1 overflow-hidden">{renderCenter()}</div>

      <button
        type="button"
        onClick={() => ps().setRightPanelOpen(!rightPanelOpen)}
        className="flex w-6 shrink-0 items-center justify-center border-l border-gray-800 bg-gray-900 text-gray-500 transition-colors hover:text-white"
        title={rightPanelOpen ? "Collapse preview" : "Expand preview"}
      >
        {rightPanelOpen ? "\u203A" : "\u2039"}
      </button>

      {rightPanelOpen && (
        <aside className="w-96 shrink-0 overflow-hidden border-l border-gray-800 bg-gray-900">
          <CodePreview
            files={generatedFiles}
            activeFileIndex={activeFileIndex}
            onFileSelect={(i) => ps().setActiveFileIndex(i)}
          />
        </aside>
      )}
    </div>
  );
}
