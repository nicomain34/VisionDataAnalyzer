export function Progress({
  value,
  max = 100,
  indeterminate = false,
}: {
  value: number;
  max?: number;
  indeterminate?: boolean;
}) {
  const pct = max <= 0 ? 0 : Math.min(100, Math.round((value / max) * 100));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-elevated">
      {indeterminate ? (
        <div className="h-full w-1/3 animate-[em-progress_1.1s_ease-in-out_infinite] rounded-full bg-primary" />
      ) : (
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      )}
    </div>
  );
}
