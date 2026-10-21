import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  ...props
}: Props) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition disabled:cursor-not-allowed disabled:opacity-40",
        size === "sm" && "h-8 px-3 text-[13px]",
        size === "md" && "h-10 px-4 text-[13px]",
        size === "lg" && "h-11 px-5 text-sm",
        variant === "primary" &&
          "bg-primary text-white shadow-sm shadow-primary/20 hover:bg-primary-hover",
        variant === "secondary" &&
          "border border-border bg-elevated text-text hover:bg-border/40",
        variant === "ghost" &&
          "bg-transparent text-secondary hover:bg-elevated hover:text-text",
        variant === "danger" && "bg-error text-white hover:opacity-90",
        className,
      )}
      {...props}
    />
  );
}
