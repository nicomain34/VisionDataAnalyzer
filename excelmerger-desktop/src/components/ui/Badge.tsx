import { cn } from "@/lib/utils";

export function Badge({
  children,
  tone = "primary",
  className,
}: {
  children: React.ReactNode;
  tone?: "primary" | "muted" | "success" | "warning" | "error";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold",
        tone === "primary" && "bg-primary/20 text-primary",
        tone === "muted" && "bg-elevated text-secondary",
        tone === "success" && "bg-success/15 text-success",
        tone === "warning" && "bg-warning/15 text-warning",
        tone === "error" && "bg-error/15 text-error",
        className,
      )}
    >
      {children}
    </span>
  );
}
