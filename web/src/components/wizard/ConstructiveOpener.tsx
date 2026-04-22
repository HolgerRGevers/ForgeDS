interface ConstructiveOpenerProps {
  shell: string; // e.g. "Nice — {gist}. How deep do you want to go on this?"
  gist: string; // AI-generated gist
}

export function ConstructiveOpener({ shell, gist }: ConstructiveOpenerProps) {
  const text = shell.replace("{gist}", gist || "this is a solid starting point");
  return (
    <div className="max-w-2xl rounded-md border border-[#c2662d]/30 bg-[#c2662d]/5 p-4 text-sm text-gray-200">
      {text}
    </div>
  );
}
