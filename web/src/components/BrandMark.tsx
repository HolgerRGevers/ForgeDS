interface BrandMarkProps {
  size?: number;
  className?: string;
}

export function BrandMark({ size = 28, className = "" }: BrandMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 96 96"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M48 8 C 52 20, 60 32, 66 46 C 72 60, 74 70, 72 78 L 62 72 C 59 70, 55 70, 52 73 L 48 78 L 44 73 C 41 70, 37 70, 34 72 L 24 78 C 22 70, 24 60, 30 46 C 36 32, 44 20, 48 8 Z"
        fill="#c2662d"
      />
      <path
        d="M48 32 C 50 40, 54 48, 56 56 C 57 62, 56 66, 54 68 L 50 64 C 49 63, 47 63, 46 64 L 42 68 C 40 66, 39 62, 40 56 C 42 48, 46 40, 48 32 Z"
        fill="#e08a4f"
      />
    </svg>
  );
}
