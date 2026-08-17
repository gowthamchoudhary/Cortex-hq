/** Format a Unix timestamp or ISO string as a compact relative time. */
export function timeAgo(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  let ms: number;
  if (typeof value === "number") {
    ms = value * 1000;
  } else {
    const parsed = Date.parse(
      typeof value === "string" && value.endsWith("Z") ? value : String(value).replace("Z", "+00:00")
    );
    if (Number.isNaN(parsed)) return "—";
    ms = parsed;
  }
  const seconds = Math.floor((Date.now() - ms) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks}w ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "0";
  return new Intl.NumberFormat("en-US").format(value);
}

export function greetingForHour(hour: number): string {
  if (hour < 5) return "Good night";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
