"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import {
  IconAnalysis,
  IconClose,
  IconDashboard,
  IconExecution,
  IconGear,
  IconHelp,
  IconKnowledge,
  IconLog,
  IconProjects,
  IconProposals,
  IconRoadmap,
  IconSettings,
  IconUnderstanding,
} from "@/components/icons";
import { BrandMark } from "./BrandMark";
import { isAdmin, useUserSafe } from "@/hooks/useUser";
import { hasFeature } from "@/lib/user";

const userWorkspace = [
  { href: "/ide", label: "مساحة العمل IDE", icon: IconExecution, feature: "projects" },
  { href: "/brain", label: "عقل الوكيل", icon: IconUnderstanding, feature: "chat" },
  { href: "/projects", label: "المشاريع والملفات", icon: IconProjects, feature: "projects" },
  { href: "/copilot", label: "مساعد الطيار", icon: IconUnderstanding, feature: "copilot" },
];

const userIntel = [
  { href: "/understanding", label: "فهم المشروع", icon: IconUnderstanding, feature: "understanding" },
  { href: "/analysis", label: "التحليل الذكي", icon: IconAnalysis, feature: "analysis" },
  { href: "/knowledge", label: "المعرفة والذاكرة", icon: IconKnowledge, feature: "knowledge" },
  { href: "/agents", label: "فريق الوكلاء", icon: IconProjects, feature: "agents_view" },
  { href: "/roadmap", label: "خارطة الطريق", icon: IconRoadmap, feature: "roadmap" },
];

const userDelivery = [
  { href: "/proposals", label: "المقترحات", icon: IconProposals, feature: "proposals" },
  { href: "/execution", label: "التنفيذ", icon: IconExecution, feature: "execution" },
  { href: "/log", label: "سجل التطوير", icon: IconLog },
];

const userSystem = [
  { href: "/", label: "لوحة التحكم", icon: IconDashboard, exact: true },
  { href: "/console", label: "الحساب والويب", icon: IconSettings },
  { href: "/download", label: "تنزيل سطح المكتب", icon: IconExecution },
  { href: "/pricing", label: "الخطط", icon: IconSettings },
  { href: "/help", label: "المساعدة", icon: IconHelp },
];

const adminNav = [
  { href: "/admin", label: "وحدة التحكم العليا", icon: IconDashboard, exact: true },
  { href: "/control-plane", label: "لوحة الأسطول", icon: IconDashboard },
  { href: "/maintain", label: "صيانة ذاتية", icon: IconGear },
  { href: "/settings", label: "ملكية النماذج والتدريب", icon: IconSettings },
];

type Props = {
  open: boolean;
  onClose: () => void;
  onToggle: () => void;
};

function isActive(pathname: string, href: string, exact?: boolean) {
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavGroup({
  label,
  items,
  pathname,
  pendingHref,
  onNavigate,
  onPrefetch,
  onClose,
  locked,
}: {
  label: string;
  items: { href: string; label: string; icon: typeof IconGear; exact?: boolean; feature?: string }[];
  pathname: string;
  pendingHref: string | null;
  onNavigate: (href: string) => void;
  onPrefetch: (href: string) => void;
  onClose: () => void;
  locked?: (feature?: string) => boolean;
}) {
  return (
    <div className="sidebar__group">
      <div className="sidebar__toolbar">
        <span>{label}</span>
      </div>
      <nav className="sidebar__nav">
        {items.map((item) => {
          const isLocked = locked?.(item.feature) ?? false;
          const target = isLocked
            ? `/pricing?need=${encodeURIComponent(item.feature || "")}`
            : item.href;
          const active =
            pendingHref != null
              ? pendingHref === target || (!isLocked && isActive(pendingHref, item.href, item.exact))
              : isActive(pathname, item.href, item.exact);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={target}
              prefetch
              className={`nav-link ${active ? "is-active" : ""} ${isLocked ? "is-locked" : ""} ${
                pendingHref === target ? "is-pending" : ""
              }`}
              title={isLocked ? "متاح بعد ترقية الخطة" : undefined}
              onPointerEnter={() => onPrefetch(target)}
              onClick={(e) => {
                if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
                e.preventDefault();
                onNavigate(target);
                if (typeof window !== "undefined" && window.matchMedia("(max-width: 980px)").matches) {
                  onClose();
                }
              }}
            >
              <Icon size={18} />
              <span>{item.label}</span>
              {isLocked ? <em className="nav-lock">قفل</em> : null}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

export function Sidebar({ open, onClose, onToggle }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useUserSafe();
  const admin = isAdmin(user);
  const [pendingHref, setPendingHref] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  useEffect(() => {
    setPendingHref(null);
  }, [pathname]);

  function onPrefetch(href: string) {
    try {
      router.prefetch(href);
    } catch {
      /* ignore */
    }
  }

  function onNavigate(href: string) {
    if (href === pathname) {
      setPendingHref(null);
      return;
    }
    setPendingHref(href);
    startTransition(() => {
      router.push(href);
    });
  }

  return (
    <>
      <div
        className={`sidebar-backdrop ${open ? "is-open" : ""}`}
        onClick={onClose}
        aria-hidden={!open}
      />
      <aside
        className={`sidebar ${open ? "is-open" : ""}`}
        aria-label="القائمة الرئيسية"
        aria-hidden={!open}
      >
        <div className="sidebar__brand">
          <BrandMark compact gradientId="brainGlowSide" />
          <button
            type="button"
            className="sidebar__close"
            onClick={onClose}
            aria-label="إغلاق القائمة"
          >
            <IconClose size={18} />
          </button>
        </div>

        <div className="sidebar__toolbar">
          <span>مساحة العمل</span>
          <button
            type="button"
            className="icon-btn sidebar__collapse"
            onClick={onToggle}
            aria-label="طي القائمة"
            title="طي القائمة"
          >
            <IconGear size={18} />
          </button>
        </div>

        <div className="sidebar__scroll">
          <NavGroup
            label="العمل"
            items={userWorkspace}
            pathname={pathname}
            pendingHref={pendingHref}
            onNavigate={onNavigate}
            onPrefetch={onPrefetch}
            onClose={onClose}
            locked={(f) => !!f && !hasFeature(user, f)}
          />
          <NavGroup
            label="الذكاء"
            items={userIntel}
            pathname={pathname}
            pendingHref={pendingHref}
            onNavigate={onNavigate}
            onPrefetch={onPrefetch}
            onClose={onClose}
            locked={(f) => !!f && !hasFeature(user, f)}
          />
          <NavGroup
            label="التسليم"
            items={userDelivery}
            pathname={pathname}
            pendingHref={pendingHref}
            onNavigate={onNavigate}
            onPrefetch={onPrefetch}
            onClose={onClose}
            locked={(f) => !!f && !hasFeature(user, f)}
          />
          <NavGroup
            label="حسابك"
            items={userSystem}
            pathname={pathname}
            pendingHref={pendingHref}
            onNavigate={onNavigate}
            onPrefetch={onPrefetch}
            onClose={onClose}
          />
          {admin ? (
            <NavGroup
              label="المسؤول الأعلى"
              items={adminNav}
              pathname={pathname}
              pendingHref={pendingHref}
              onNavigate={onNavigate}
              onPrefetch={onPrefetch}
              onClose={onClose}
            />
          ) : null}
        </div>

        <div className="sidebar__footer">
          <div className="system-status">
            <span className="system-status__pulse" aria-hidden />
            <div>
              <strong>{admin ? "صلاحيات عليا" : "مساحة العضو"}</strong>
              <span>
                {user.signedIn
                  ? `${user.tokensRemaining} توكن · ${user.plan}`
                  : "يلزم تسجيل الدخول"}
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
