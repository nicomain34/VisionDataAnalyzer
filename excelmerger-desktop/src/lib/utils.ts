import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number | undefined | null, digits = 3) {
  if (n == null || Number.isNaN(n)) return "—";
  if (Math.abs(n) >= 1000) return n.toLocaleString();
  return Number(n).toPrecision(digits).replace(/\.?0+$/, "");
}
