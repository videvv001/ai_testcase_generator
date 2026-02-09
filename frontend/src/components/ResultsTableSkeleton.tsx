import { useState, useEffect } from "react";

const INITIAL_MESSAGES = [
  "Generating comprehensive test cases…",
  "Analyzing feature…",
  "Designing scenarios…",
  "Optimizing coverage…",
];

const REASSURING_MESSAGES = [
  "Creating positive and negative scenarios",
  "Adding edge cases",
  "Structuring automation-ready steps",
  "Validating preconditions and expected results",
];

const ROW_COUNT = 8;

export function ResultsTableSkeleton() {
  const [elapsed, setElapsed] = useState(0);
  const [msgIndex, setMsgIndex] = useState(0);
  const useReassuring = elapsed >= 4;
  const messages = useReassuring ? REASSURING_MESSAGES : INITIAL_MESSAGES;

  useEffect(() => {
    const start = Date.now();
    const tick = () => setElapsed((Date.now() - start) / 1000);
    const id = setInterval(tick, 500);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!useReassuring) return;
    const id = setInterval(() => {
      setMsgIndex((i) => (i + 1) % messages.length);
    }, 3000);
    return () => clearInterval(id);
  }, [useReassuring, messages.length]);

  return (
    <div className="flex flex-col gap-4">
      <div className="space-y-2">
        {useReassuring ? (
          <div className="flex items-center gap-2 text-sm text-neutral-600 dark:text-neutral-400">
            <span className="text-emerald-500">✓</span>
            <span>{messages[msgIndex]}</span>
          </div>
        ) : (
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            {INITIAL_MESSAGES[Math.min(Math.floor(elapsed), INITIAL_MESSAGES.length - 1)]}
          </p>
        )}
      </div>
      <div className="overflow-hidden rounded-xl border border-neutral-200 dark:border-neutral-700">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[800px] table-fixed border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-neutral-200 bg-neutral-50/80 dark:border-neutral-700 dark:bg-neutral-800/80">
                <th className="w-8 shrink-0 p-2" />
                <th className="w-[16%] p-2.5 font-medium text-neutral-600 dark:text-neutral-400">Scenario</th>
                <th className="w-[20%] p-2.5 font-medium text-neutral-600 dark:text-neutral-400">Description</th>
                <th className="w-[16%] p-2.5 font-medium text-neutral-600 dark:text-neutral-400">Preconditions</th>
                <th className="w-[22%] p-2.5 font-medium text-neutral-600 dark:text-neutral-400">Test Steps</th>
                <th className="w-[14%] p-2.5 font-medium text-neutral-600 dark:text-neutral-400">Expected Result</th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: ROW_COUNT }).map((_, i) => (
                <tr
                  key={i}
                  className="border-b border-neutral-100 dark:border-neutral-700/50"
                >
                  <td className="p-2">
                    <div className="h-4 w-4 rounded animate-shimmer" />
                  </td>
                  <td className="p-2.5">
                    <div className="h-4 w-[120px] max-w-full rounded animate-shimmer" />
                    <div className="mt-1.5 h-3 w-[80px] max-w-full rounded animate-shimmer" />
                  </td>
                  <td className="p-2.5">
                    <div className="h-3 w-[140px] max-w-full rounded animate-shimmer" />
                    <div className="mt-1.5 h-3 w-[100px] max-w-full rounded animate-shimmer" />
                  </td>
                  <td className="p-2.5">
                    <div className="h-3 w-[100px] max-w-full rounded animate-shimmer" />
                  </td>
                  <td className="p-2.5">
                    <div className="space-y-1">
                      <div className="h-3 w-[160px] max-w-full rounded animate-shimmer" />
                      <div className="h-3 w-[120px] max-w-full rounded animate-shimmer" />
                      <div className="h-3 w-[80px] max-w-full rounded animate-shimmer" />
                    </div>
                  </td>
                  <td className="p-2.5">
                    <div className="h-3 w-[100px] max-w-full rounded animate-shimmer" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
