export function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="#4338CA" />
      <path d="M9 12h11M9 17h8M9 22h5" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M21 19l2.5 2.5L28 16" stroke="#C7D2FE" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}