"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { initials } from "@/lib/user";
import { planLabel, roleLabel } from "@/lib/uiLabels";
import { isAdmin, useUser } from "@/hooks/useUser";

export function UserMenu() {
  const { user, signOut } = useUser();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div className="top-menu" ref={root}>
      <button
        type="button"
        className={`user-chip user-chip--btn ${open ? "is-open" : ""}`}
        aria-expanded={open}
        aria-label="قائمة المستخدم"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="user-chip__text">
          <strong>{user.name}</strong>
          <span>
            {planLabel(user.plan)} · {user.tokensRemaining} توكن
          </span>
        </div>
        {user.avatarUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={user.avatarUrl} alt="" className="avatar avatar--img" />
        ) : (
          <div className="avatar" aria-hidden>
            {initials(user.name)}
          </div>
        )}
      </button>

      {open && (
        <div className="top-popover top-popover--user" role="menu">
          <div className="user-card">
            {user.avatarUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={user.avatarUrl} alt="" className="avatar avatar--lg avatar--img" />
            ) : (
              <div className="avatar avatar--lg" aria-hidden>
                {initials(user.name)}
              </div>
            )}
            <div>
              <strong>{user.name}</strong>
              <span>{user.email || "—"}</span>
              <em>{roleLabel(user.role)}</em>
            </div>
          </div>
          <ul className="top-popover__list">
            <li>
              <Link href="/console" className="top-popover__item" onClick={() => setOpen(false)}>
                <strong>الحساب · الاستخدام والفوترة</strong>
                <span>توكنز، خطط، وإعدادات الويب</span>
              </Link>
            </li>
            <li>
              <Link href="/pricing" className="top-popover__item" onClick={() => setOpen(false)}>
                <strong>الخطط</strong>
                <span>عرض الحصص والترقية</span>
              </Link>
            </li>
            {isAdmin(user) ? (
              <li>
                <Link href="/admin" className="top-popover__item" onClick={() => setOpen(false)}>
                  <strong>وحدة التحكم العليا</strong>
                  <span>تدريب وملكية وصيانة</span>
                </Link>
              </li>
            ) : null}
            <li>
              <Link href="/help" className="top-popover__item" onClick={() => setOpen(false)}>
                <strong>المساعدة</strong>
                <span>دليل سريع للمنصة</span>
              </Link>
            </li>
            <li>
              <button
                type="button"
                className="top-popover__item"
                onClick={() => {
                  setOpen(false);
                  signOut();
                  router.push("/login");
                }}
              >
                <strong>تسجيل الخروج</strong>
                <span>إنهاء الجلسة على هذا الجهاز</span>
              </button>
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
