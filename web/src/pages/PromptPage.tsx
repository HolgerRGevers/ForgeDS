import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  PromptInput,
  RefinedPrompt,
  BuildProgress,
  CodePreview,
  ProjectHistory,
} from "../components";
import { useAuthStore } from "../stores/authStore";
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
  BuildMessage,
  CodeFile,
  ProjectHistoryItem,
  RepoFile,
} from "../types/prompt";
import type { PromptMode } from "../components/ModeToggle";

type WorkflowStage = "input" | "planning" | "refined" | "building" | "complete";

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

  // Workflow state
  const [stage, setStage] = useState<WorkflowStage>("input");
  const [isLoading, setIsLoading] = useState(false);
  const [promptText, setPromptText] = useState("");
  const [mode, setMode] = useState<PromptMode>("plan");
  const [sections, setSections] = useState<RefinedSection[]>([]);
  const [buildMessages, setBuildMessages] = useState<BuildMessage[]>([]);
  const [generatedFiles, setGeneratedFiles] = useState<CodeFile[]>([]);
  const [activeFileIndex, setActiveFileIndex] = useState(0);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [planSteps, setPlanSteps] = useState<string[]>([]);

  // Project history
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

      setPromptText(prompt);
      setIsLoading(true);

      // Build context from repo files
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
          setPlanSteps(steps);
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
          setSections(refined);
          setStage("planning");
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
          setSections(refined);
          setStage("refined");
        }
      } catch (err) {
        handleError(err);
        // Still show the prompt as a fallback section so user can retry
        setSections([
          {
            id: "fallback",
            title: "Your Prompt",
            icon: "\u{1F4CB}",
            content: prompt,
            items: [],
            isEditable: true,
          },
        ]);
        setStage(mode === "plan" ? "planning" : "refined");
      } finally {
        setIsLoading(false);
      }
    },
    [token, handleTokenExpired, handleError, mode],
  );

  const handleSectionUpdate = useCallback(
    (sectionId: string, updates: Partial<RefinedSection>) => {
      setSections((prev) =>
        prev.map((s) => (s.id === sectionId ? { ...s, ...updates } : s)),
      );
    },
    [],
  );

  const handleBuild = useCallback(async () => {
    if (!token) {
      handleTokenExpired();
      return;
    }

    setStage("building");
    setBuildMessages([]);
    setGeneratedFiles([]);
    setActiveFileIndex(0);

    const addMessage = (msg: BuildMessage) => {
      setBuildMessages((prev) => [...prev, msg]);
    };

    addMessage({
      timestamp: new Date().toLocaleTimeString(),
      text: "Starting build...",
      type: "info",
    });

    try {
      if (!isConfigured()) {
        throw new ClaudeApiNotConfiguredError();
      }

      const result = await buildProject(
        token,
        { sections, prompt: promptText },
        (chunk) => {
          if (chunk.message) {
            addMessage({
              timestamp: new Date().toLocaleTimeString(),
              text: chunk.message,
              type: chunk.type ?? "info",
            });
          }
        },
      );

      const files = result.files ?? [];
      setGeneratedFiles(files);

      addMessage({
        timestamp: new Date().toLocaleTimeString(),
        text: `Build complete! Generated ${files.length} file(s).`,
        type: "success",
      });

      setStage("complete");

      // Save to history
      const entry: ProjectHistoryItem = {
        id: crypto.randomUUID(),
        prompt: promptText,
        timestamp: Date.now(),
        fileCount: files.length,
      };
      setHistory((prev) => [entry, ...prev]);

      toast.getState().success(
        "Build complete",
        `Generated ${files.length} file${files.length !== 1 ? "s" : ""}`,
      );
    } catch (err) {
      handleError(err);
      addMessage({
        timestamp: new Date().toLocaleTimeString(),
        text: err instanceof Error ? err.message : "Build failed. Please try again.",
        type: "error",
      });
    }
  }, [token, handleTokenExpired, handleError, sections, promptText, toast]);

  const handleStartOver = useCallback(() => {
    setStage("input");
    setPromptText("");
    setSections([]);
    setBuildMessages([]);
    setGeneratedFiles([]);
    setActiveFileIndex(0);
    setPlanSteps([]);
  }, []);

  const handleOpenIDE = useCallback(() => {
    navigate("/ide");
  }, [navigate]);

  const handleHistorySelect = useCallback((id: string) => {
    const item = loadHistory().find((h) => h.id === id);
    if (item) {
      setPromptText(item.prompt);
      setStage("input");
    }
  }, []);

  const handleHistoryDelete = useCallback((id: string) => {
    setHistory((prev) => prev.filter((h) => h.id !== id));
  }, []);

  const handleHistoryClearAll = useCallback(() => {
    setHistory([]);
  }, []);

  // --- Render center area based on stage ---

  /** Approve the plan and move to code generation. */
  const handleApprovePlan = useCallback(() => {
    setMode("code");
    setStage("refined");
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
                onModeChange={setMode}
              />
            </div>
          </div>
        );
      case "planning":
        return (
          <div className="h-full overflow-y-auto p-6">
            <div className="mx-auto max-w-2xl space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-white">
                  Plan
                </h2>
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
      {/* Left sidebar */}
      <aside className="w-64 shrink-0 overflow-y-auto border-r border-gray-800 bg-gray-900">
        <ProjectHistory
          items={history}
          onSelect={handleHistorySelect}
          onDelete={handleHistoryDelete}
          onClearAll={handleHistoryClearAll}
        />
      </aside>

      {/* Center */}
      <div className="flex-1 overflow-hidden">{renderCenter()}</div>

      {/* Right panel toggle */}
      <button
        type="button"
        onClick={() => setRightPanelOpen((v) => !v)}
        className="flex w-6 shrink-0 items-center justify-center border-l border-gray-800 bg-gray-900 text-gray-500 transition-colors hover:text-white"
        title={rightPanelOpen ? "Collapse preview" : "Expand preview"}
      >
        {rightPanelOpen ? "\u203A" : "\u2039"}
      </button>

      {/* Right panel */}
      {rightPanelOpen && (
        <aside className="w-96 shrink-0 overflow-hidden border-l border-gray-800 bg-gray-900">
          <CodePreview
            files={generatedFiles}
            activeFileIndex={activeFileIndex}
            onFileSelect={setActiveFileIndex}
          />
        </aside>
      )}
    </div>
  );
}
