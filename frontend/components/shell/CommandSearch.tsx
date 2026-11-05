"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { IconSearch } from "@/components/icons";
import { fetchProjects } from "@/lib/api";
import type { Project } from "@/lib/types";

const staticLinks = [
  { href: "/", label: "لوحة التحكم", hint: "home" },
  { href: "/ide", label: "مساحة العمل IDE", hint: "ide editor files" },
  { href: "/download", label: "تنزيل سطح المكتب", hint: "download desktop" },
  { href: "/brain", label: "عقل الوكيل", hint: "brain" },
  { href: "/copilot", label: "مساعد الطيار", hint: "copilot autopilot" },
  { href: "/projects", label: "المشاريع", hint: "projects" },
  { href: "/console", label: "الحساب", hint: "console billing" },
  { href: "/proposals", label: "المقترحات", hint: "proposals" },
  { href: "/execution", label: "التنفيذ", hint: "execution" },
  { href: "/knowledge", label: "المعرفة", hint: "knowledge" },
  { href: "/control-plane", label: "لوحة الأسطول", hint: "fleet" },
  { href: "/settings", label: "الإعدادات", hint: "settings" },
];

export function CommandSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchProjects().then(setProjects);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
        inputRef.current?.focus();
        inputRef.current?.select();
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pages = staticLinks.filter(
      (l) => !q || l.label.includes(q) || l.hint.includes(q) || l.href.includes(q),
    );
    const proj = projects
      .filter((p) => !q || p.name.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q))
      .slice(0, 6)
      .map((p) => ({ href: `/projects/${p.id}`, label: p.name, hint: p.slug }));
    return [...pages, ...proj].slice(0, 10);
  }, [query, projects]);

  function go(href: string) {
    setOpen(false);
    setQuery("");
    router.push(href);
  }

  return (
    <div className={`search-field-wrap ${open ? "is-open" : ""}`} ref={root}>
      <label className="search-field">
        <IconSearch size={18} />
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder="ابحث عن المشاريع والمهام..."
          aria-label="بحث"
        />
        <kbd>Ctrl K</kbd>
      </label>
      {open && (
        <div className="search-results" role="listbox">
          {results.length === 0 && <div className="top-popover__empty">لا نتائج</div>}
          {results.map((r) => (
            <button key={r.href + r.label} type="button" className="search-results__item" onClick={() => go(r.href)}>
              <strong>{r.label}</strong>
              <span>{r.hint}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
