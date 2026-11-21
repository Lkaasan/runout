/** 134000 -> "2:14", 3723000 -> "1:02:03" */
export function formatMs(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

export type Mode = "listen" | "study";

export function parseMode(value: string | string[] | undefined): Mode {
  return value === "study" ? "study" : "listen";
}
