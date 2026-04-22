import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useWizardStore } from "../stores/wizardStore";
import { useAuthStore } from "../stores/authStore";
import { PairedQuestion } from "../components/wizard/PairedQuestion";
import { FreeTextQuestion } from "../components/wizard/FreeTextQuestion";
import { generateQuestionBatch } from "../services/brainstorming";
import type { WizardDepth } from "../types/wizard";

function totalDotsFor(depth: WizardDepth | null): number {
  switch (depth) {
    case "light": return 3;
    case "mid": return 7;
    case "heavy": return 10;
    case "dev": return 10;
    default: return 5;
  }
}

export default function QuestionPage() {
  const navigate = useNavigate();
  const { n: nParam } = useParams<{ n: string }>();
  const n = Math.max(1, parseInt(nParam ?? "1", 10));

  const token = useAuthStore((s) => s.token);
  const depth = useWizardStore((s) => s.depth);
  const coreIdea = useWizardStore((s) => s.coreIdea);
  const midSeedAnswers = useWizardStore((s) => s.midSeedAnswers);
  const setMidSeedAnswers = useWizardStore((s) => s.setMidSeedAnswers);
  const dataAnalysis = useWizardStore((s) => s.dataAnalysis);
  const questions = useWizardStore((s) => s.questions);
  const appendQuestions = useWizardStore((s) => s.appendQuestions);
  const answers = useWizardStore((s) => s.answers);
  const recordAnswer = useWizardStore((s) => s.recordAnswer);
  const setStep = useWizardStore((s) => s.setStep);
  const setCurrentQuestionIdx = useWizardStore((s) => s.setCurrentQuestionIdx);
  const questionsComplete = useWizardStore((s) => s.questionsComplete);
  const setQuestionsComplete = useWizardStore((s) => s.setQuestionsComplete);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // I2: Guard against StrictMode double-fire — track which question indices we
  // have already initiated a fetch for so the effect never fires twice.
  const fetchedRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    setStep("questions");
    setCurrentQuestionIdx(n - 1);
  }, [n, setCurrentQuestionIdx, setStep]);

  // Lazy-load the next batch when needed.
  useEffect(() => {
    if (questions[n - 1] || !depth || !token) return;

    // I2: Skip if we already fired a fetch for this index.
    if (fetchedRef.current.has(n)) return;
    fetchedRef.current.add(n);

    setLoading(true);
    setError(null);
    generateQuestionBatch({
      token,
      coreIdea,
      depth,
      midSeedAnswers,
      priorQuestions: questions,
      priorAnswers: answers,
      dataAnalysis,
      needsFreeTextSeed: depth === "mid" && questions.length === 0,
    })
      .then((batch) => {
        // C2: If the server returns an empty batch and says done, the wizard is
        // finished — navigate immediately rather than trying to render a missing
        // question which would spin on "Generating question…" forever.
        if (batch.questions.length === 0 && batch.done) {
          navigate("/new/building");
          return;
        }
        appendQuestions(batch.questions);
        if (batch.done) {
          setQuestionsComplete(true);
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load questions"))
      .finally(() => setLoading(false));
  }, [
    appendQuestions,
    answers,
    coreIdea,
    dataAnalysis,
    depth,
    midSeedAnswers,
    n,
    navigate,
    questions,
    setQuestionsComplete,
    token,
  ]);

  const q = questions[n - 1];
  const totalDots = totalDotsFor(depth);
  const progressLabel = `${(depth ?? "").charAt(0).toUpperCase()}${(depth ?? "").slice(1)} · Question ${n}`;

  const advance = () => {
    // C2: Terminal condition — the user just answered the last stored question
    // AND the most recent fetch told us there are no more batches.
    const isLastInBatch = n === questions.length;
    if (questionsComplete && isLastInBatch) {
      navigate("/new/building");
    } else {
      navigate(`/new/q/${n + 1}`);
    }
  };

  const goBack = () => {
    if (n === 1) navigate("/new/depth");
    else navigate(`/new/q/${n - 1}`);
  };

  if (error) {
    return (
      <div className="mx-auto flex h-full max-w-2xl items-center justify-center p-6">
        <div className="rounded-md border border-red-500/40 bg-red-950/30 p-4 text-sm text-red-200">
          {error}
        </div>
      </div>
    );
  }

  if (loading || !q) {
    return (
      <div className="mx-auto flex h-full max-w-2xl items-center justify-center p-6 text-sm text-gray-500">
        Generating question…
      </div>
    );
  }

  if (q.kind === "free-text") {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <FreeTextQuestion
          question={q}
          initialValue={(answers[q.id] as string) ?? ""}
          onAnswer={(text) => {
            recordAnswer(q.id, text);
            // I1: Replace by index rather than blindly appending, so that
            // navigating Back and re-answering a seed question doesn't grow the
            // array with duplicate entries.
            if (depth === "mid") {
              const seedQuestions = questions.filter((sq) => sq.kind === "free-text");
              const seedIdx = seedQuestions.findIndex((sq) => sq.id === q.id);
              if (seedIdx >= 0) {
                const next = [...midSeedAnswers];
                while (next.length <= seedIdx) next.push("");
                next[seedIdx] = text;
                setMidSeedAnswers(next);
              }
            }
            advance();
          }}
          onBack={goBack}
          progressLabel={progressLabel}
          totalDots={totalDots}
          currentDot={n - 1}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full items-center justify-center p-6">
      <PairedQuestion
        question={q}
        onAnswer={(choice) => {
          recordAnswer(q.id, choice);
          advance();
        }}
        onSkip={() => {
          recordAnswer(q.id, q.aiPreference);
          advance();
        }}
        onBack={goBack}
        progressLabel={progressLabel}
        totalDots={totalDots}
        currentDot={n - 1}
      />
    </div>
  );
}
