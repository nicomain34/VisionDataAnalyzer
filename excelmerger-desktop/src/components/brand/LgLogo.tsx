/**
 * LG heritage face mark (vector).
 * Proportions follow the classic circular L+G+eye symbol.
 */
export function LgLogo({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 1000 1000"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="LG"
    >
      <title>LG</title>
      <circle cx="500" cy="500" r="500" fill="#A50034" />
      {/* L */}
      <path fill="#FFFFFF" d="M291 291v418h209v-84H375V291H291z" />
      {/* G */}
      <path
        fill="#FFFFFF"
        d="M709 291c93 0 168 75 168 168s-75 168-168 168H500V291h209zm0 252c46.5 0 84-37.5 84-84s-37.5-84-84-84H584v168h125z"
      />
      {/* Eye */}
      <circle cx="709" cy="727" r="50" fill="#FFFFFF" />
    </svg>
  );
}
