import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Conditional class composition with last-wins conflict resolution.
 *
 * Components in this layer expose a `className` prop so callers can adjust
 * layout without forking the component; `twMerge` makes that override
 * predictable instead of depending on stylesheet order.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
