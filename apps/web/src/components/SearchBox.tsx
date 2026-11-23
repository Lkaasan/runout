"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { api } from "@/api/client";
import { moveHighlight, type Suggestion, suggestions } from "@/lib/search";

/** Search the library for artists and albums. Suggestions appear as you type; Enter opens all results. */
export function SearchBox({
  initial = "",
  autoFocus = false,
}: {
  initial?: string;
  autoFocus?: boolean;
}) {
  const router = useRouter();
  const listId = useId();
  const [text, setText] = useState(initial);
  const [found, setItems] = useState<Suggestion[]>([]);
  // Clearing the box hides suggestions without waiting for a request.
  const items = text.trim() ? found : [];
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const q = text.trim();
    if (!q) return;
    let stale = false;
    const timer = setTimeout(async () => {
      const { data } = await api
        .GET("/search", { params: { query: { q, limit: 5 } } })
        .catch(() => ({ data: undefined }));
      if (stale || !data) return;
      setItems(suggestions(data));
      setActive(-1);
    }, 200);
    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [text]);

  function submit() {
    if (active >= 0 && items[active]) router.push(items[active].href);
    else if (text.trim()) router.push(`/search?q=${encodeURIComponent(text.trim())}`);
    setOpen(false);
  }

  return (
    <div className="relative">
      <input
        type="search"
        role="combobox"
        aria-expanded={open && items.length > 0}
        aria-controls={listId}
        aria-label="Search artists and albums"
        placeholder="Search artists and albums"
        autoFocus={autoFocus}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
            setActive((a) => moveHighlight(a, e.key === "ArrowDown" ? 1 : -1, items.length));
          } else if (e.key === "Enter") {
            e.preventDefault();
            submit();
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        className="w-full rounded-xl border border-neutral-800 bg-neutral-900 px-4 py-3 text-lg outline-none focus:border-neutral-600"
      />
      {open && items.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-10 mt-2 w-full overflow-hidden rounded-xl border border-neutral-800 bg-neutral-950 shadow-lg"
        >
          {items.map((s, i) => (
            <li key={s.href} role="option" aria-selected={i === active}>
              <a
                href={s.href}
                onMouseDown={(e) => {
                  e.preventDefault();
                  router.push(s.href);
                }}
                className={`flex items-baseline justify-between gap-4 px-4 py-2 ${
                  i === active ? "bg-neutral-800" : "hover:bg-neutral-900"
                }`}
              >
                <span>{s.label}</span>
                <span className="text-sm text-neutral-500">
                  {s.kind === "artist" ? "Artist · " : "Album · "}
                  {s.hint}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
