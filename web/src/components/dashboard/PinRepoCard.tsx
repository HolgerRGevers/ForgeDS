interface PinRepoCardProps {
  onClick: () => void;
}

export function PinRepoCard({ onClick }: PinRepoCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-[110px] items-center justify-center rounded-lg border border-dashed border-[#c2662d]/50 bg-[#c2662d]/5 text-sm font-semibold text-[#c2662d] transition-colors hover:border-[#c2662d] hover:bg-[#c2662d]/10"
    >
      + Pin a repo
    </button>
  );
}
