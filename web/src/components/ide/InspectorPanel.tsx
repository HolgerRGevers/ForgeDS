import { useCallback } from "react";
import { useIdeStore } from "../../stores/ideStore";
import type { InspectedElementType, RelationshipLink } from "../../types/ide";

// --- Type badge colors ---

const typeBadgeColors: Record<InspectedElementType, string> = {
  field: "bg-blue-600 text-blue-100",
  function: "bg-yellow-600 text-yellow-100",
  form: "bg-green-600 text-green-100",
  variable: "bg-purple-600 text-purple-100",
  none: "bg-gray-600 text-gray-300",
};

function TypeBadge({ type }: { type: string }) {
  const colors =
    typeBadgeColors[type as InspectedElementType] ?? "bg-gray-600 text-gray-300";
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium uppercase ${colors}`}
    >
      {type}
    </span>
  );
}

// --- Relationship item ---

interface RelationshipItemProps {
  link: RelationshipLink;
  onNavigate: (targetId: string) => void;
}

function RelationshipItem({ link, onNavigate }: RelationshipItemProps) {
  const handleClick = useCallback(() => {
    onNavigate(link.targetId);
  }, [link.targetId, onNavigate]);

  return (
    <button
      onClick={handleClick}
      className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-gray-800"
    >
      <span className="flex-shrink-0 text-gray-500">{link.relationship}</span>
      <span className="text-gray-400">&rarr;</span>
      <span className="truncate text-gray-200">{link.targetLabel}</span>
      <TypeBadge type={link.targetType} />
    </button>
  );
}

// --- Usage item ---

interface UsageItemProps {
  file: string;
  line: number;
  context: string;
}

function UsageItem({ file, line, context }: UsageItemProps) {
  return (
    <div className="rounded px-2 py-1 text-sm hover:bg-gray-800">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-indigo-400">{file}</span>
        <span className="text-gray-500">:{line}</span>
      </div>
      <div className="mt-0.5 truncate font-mono text-xs text-gray-500">
        {context}
      </div>
    </div>
  );
}

// --- Section wrapper ---

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-gray-700/50 px-3 py-2">
      <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-gray-400">
        {title}
      </h3>
      {children}
    </div>
  );
}

// --- Main component ---

export function InspectorPanel() {
  const inspectorData = useIdeStore((s) => s.inspectorData);
  const selectNode = useIdeStore((s) => s.selectNode);

  // Empty state
  if (!inspectorData || inspectorData.type === "none") {
    return (
      <div className="flex h-full flex-col bg-gray-900">
        <div className="flex items-center border-b border-gray-700 px-3 py-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
            Inspector
          </span>
        </div>
        <div className="flex flex-1 items-center justify-center px-4">
          <div className="text-center">
            <p className="text-sm text-gray-500">
              Select an element to inspect
            </p>
            <p className="mt-2 text-xs text-gray-600">
              Click a node in the .ds Tree explorer or place your cursor on a
              symbol in the editor.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const {
    type,
    name,
    signature,
    description,
    properties,
    relationships,
    usages,
  } = inspectorData;

  return (
    <div className="flex h-full flex-col bg-gray-900">
      {/* Header */}
      <div className="flex items-center border-b border-gray-700 px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          Inspector
        </span>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        {/* Element header */}
        <div className="border-b border-gray-700/50 px-3 py-3">
          <div className="mb-1 flex items-center gap-2">
            <TypeBadge type={type} />
          </div>
          <h2 className="text-lg font-bold text-gray-100">{name}</h2>
          {signature && (
            <p className="mt-1 font-mono text-xs text-gray-400">{signature}</p>
          )}
        </div>

        {/* Description */}
        {description && (
          <Section title="Description">
            <p className="text-sm leading-relaxed text-gray-300">
              {description}
            </p>
          </Section>
        )}

        {/* Properties */}
        {properties.length > 0 && (
          <Section title="Properties">
            <div className="space-y-0">
              {properties.map((prop, i) => (
                <div
                  key={prop.label}
                  className={`flex items-baseline gap-3 rounded px-2 py-1 text-sm ${
                    i % 2 === 0 ? "bg-gray-800/40" : ""
                  }`}
                >
                  <span className="flex-shrink-0 text-gray-500">
                    {prop.label}
                  </span>
                  <span className="truncate text-gray-200">{prop.value}</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Relationships */}
        {relationships.length > 0 && (
          <Section title="Relationships">
            <div className="space-y-0.5">
              {relationships.map((link) => (
                <RelationshipItem
                  key={`${link.relationship}-${link.targetId}`}
                  link={link}
                  onNavigate={selectNode}
                />
              ))}
            </div>
          </Section>
        )}

        {/* Usages */}
        {usages.length > 0 && (
          <Section title="Usages">
            <div className="space-y-0.5">
              {usages.map((u) => (
                <UsageItem
                  key={`${u.file}:${u.line}`}
                  file={u.file}
                  line={u.line}
                  context={u.context}
                />
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}
