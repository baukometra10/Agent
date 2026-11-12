"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_URL } from "@/lib/api";
import { COMPANY, PRODUCT, PRODUCT_TAGLINE } from "@/lib/brand";

type Platform = {
  id: string;
  label: string;
  arch?: string;
  format?: string;
  download_path?: string;
  notes?: string;
};

export default function DownloadPage() {
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [note, setNote] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/system/desktop/releases`)
      .then((r) => r.json())
      .then((d) => {
        setPlatforms(d.platforms || []);
        setNote((d.requires || []).join(" · "));
      })
      .catch(() => undefined);
  }, []);

  return (
    <div className="download-page">
      <header className="download-hero">
        <p className="web-console__brand">
          {PRODUCT} <span>by {COMPANY}</span>
        </p>
        <h1>نزّل Spixa لسطح المكتب</h1>
        <p>
          {PRODUCT_TAGLINE}. التطبيق على الويب هو المنتج الكامل — وسطح المكتب نافذة أصلية لنفس مساحة
          العمل، مع فتح الملفات والعمل كما في بيئة التطوير.
        </p>
        <div className="download-hero__actions">
          <Link href="/ide" className="btn btn-primary">
            افتح مساحة العمل في المتصفح
          </Link>
          <Link href="/pricing" className="btn btn-ghost">
            الخطط
          </Link>
        </div>
      </header>

      <section className="download-grid">
        {(platforms.length ? platforms : [
          { id: "windows", label: "Windows", download_path: "/system/desktop/download/windows" },
          { id: "macos", label: "macOS", download_path: "/system/desktop/download/macos" },
          { id: "linux", label: "Linux", download_path: "/system/desktop/download/linux" },
        ]).map((p) => (
          <article key={p.id} className="download-card">
            <h2>{p.label}</h2>
            <p>{p.notes || "حزمة سطح المكتب"}</p>
            <a
              className="btn btn-primary"
              href={`${API_URL}${p.download_path || `/system/desktop/download/${p.id}`}`}
            >
              تنزيل الحزمة
            </a>
          </article>
        ))}
      </section>

      <ol className="download-steps">
        <li>نزّل الحزمة وفك الضغط.</li>
        <li>
          داخل المجلد ثبّت الحزم ثم شغّل التطبيق: <code dir="ltr">npm install</code> ثم{" "}
          <code dir="ltr">npm start</code>
        </li>
        <li>
          تأكد أن Spixa (الويب والواجهة البرمجية) يعمل — أو عيّن عنوان الخادم عبر{" "}
          <code dir="ltr">SPIXA_URL</code>.
        </li>
        <li>
          من القائمة: <strong>فتح مجلد…</strong> (Ctrl+O) — نفس مسار مساحة العمل على الويب.
        </li>
        <li>
          لبناء مثبت سطح المكتب: نفّذ{" "}
          <code dir="ltr">.\scripts\build-desktop.ps1</code> ثم أعد التنزيل من هنا.
        </li>
      </ol>
      {note ? <p className="settings-hint">{note}</p> : null}
    </div>
  );
}
