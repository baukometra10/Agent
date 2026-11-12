"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { API_URL } from "@/lib/api";
import { FEATURE_LABELS_AR } from "@/lib/billing";
import { COMPANY, PRODUCT } from "@/lib/brand";
import { useUser } from "@/hooks/useUser";
import { saveUser, type UserProfile } from "@/lib/user";

type Tab = "overview" | "usage" | "billing" | "settings";

type UsageReport = {
  tokens_monthly?: number;
  tokens_remaining?: number;
  tokens_used?: number;
  usage_percent?: number;
  daily?: { day?: string; amount?: number }[];
  by_reason?: { reason?: string; amount?: number }[];
  events?: { at?: string; amount?: number; reason?: string; id?: string }[];
};

const TAB_IDS: Tab[] = ["overview", "usage", "billing", "settings"];

export default function ConsolePage() {
  const { user, update, signOut } = useUser();
  const router = useRouter();
  const search = useSearchParams();
  const initialTab = (search.get("tab") as Tab) || "overview";
  const [tab, setTab] = useState<Tab>(TAB_IDS.includes(initialTab) ? initialTab : "overview");
  const [catalog, setCatalog] = useState<Record<string, unknown> | null>(null);
  const [usage, setUsage] = useState<UsageReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    const t = search.get("tab") as Tab;
    if (t && TAB_IDS.includes(t)) setTab(t);
  }, [search]);

  const syncFromServer = useCallback(
    async (serverUser: Record<string, unknown>) => {
      const next: UserProfile = {
        ...user,
        name: String(serverUser.name || user.name),
        email: String(serverUser.email || user.email),
        role: String(serverUser.role_label || user.role),
        access: serverUser.access === "admin" ? "admin" : "user",
        plan: (serverUser.plan as UserProfile["plan"]) || user.plan,
        tokensRemaining: Number(serverUser.tokens_remaining ?? user.tokensRemaining),
        tokensMonthly: Number(serverUser.tokens_monthly ?? user.tokensMonthly),
        entitlements: (serverUser.entitlements as string[]) || user.entitlements,
        sessionToken: String(serverUser.session_token || user.sessionToken),
        signedIn: true,
      };
      saveUser(next);
      update(next);
    },
    [user, update],
  );

  const reload = useCallback(async () => {
    if (!user.email) return;
    try {
      const [cRes, uRes] = await Promise.all([
        fetch(`${API_URL}/system/billing/catalog`, { cache: "no-store" }),
        fetch(
          `${API_URL}/system/billing/usage?email=${encodeURIComponent(user.email)}`,
          { cache: "no-store" },
        ),
      ]);
      if (cRes.ok) setCatalog(await cRes.json());
      if (uRes.ok) setUsage(await uRes.json());
    } catch {
      /* ignore */
    }
  }, [user.email]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    const sessionId = search.get("session_id");
    const paid = search.get("paid");
    if (!sessionId || paid !== "1" || !user.email) return;
    let cancelled = false;
    (async () => {
      setBusy(true);
      try {
        const res = await fetch(`${API_URL}/system/billing/finalize`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId }),
        });
        const data = await res.json();
        if (!cancelled && res.ok && data.ok && data.user) {
          await syncFromServer(data.user);
          setMsg("تم الدفع بنجاح — فُتحت المميزات فوراً.");
          await reload();
          setTab("overview");
        }
      } catch {
        /* ignore */
      }
      if (!cancelled) setBusy(false);
      router.replace("/console?tab=billing");
    })();
    return () => {
      cancelled = true;
    };
  }, [search, user.email, syncFromServer, reload, router]);

  async function confirmPay(plan: string) {
    if (!user.email) return;
    setBusy(true);
    setMsg("");
    try {
      const res = await fetch(`${API_URL}/system/billing/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: user.email, plan }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setMsg("تعذّر بدء الدفع.");
        setBusy(false);
        return;
      }
      if (data.mode === "stripe" && data.checkout_url) {
        window.location.href = data.checkout_url;
        return;
      }
      if (data.user) {
        await syncFromServer(data.user);
        setMsg(
          data.mode === "dev_simulate"
            ? "وضع التطوير: فُتحت الخطة محلياً (أضف مفتاح الدفع الحقيقي لاحقاً)."
            : "تم تأكيد الدفع — فُتحت مميزات الخطة فوراً.",
        );
        await reload();
        setTab("overview");
        router.replace("/console?tab=overview");
      }
    } catch {
      setMsg("تعذّر الاتصال بخدمة الدفع.");
    }
    setBusy(false);
  }

  const plans = (catalog?.plans || {}) as Record<
    string,
    {
      tokens_monthly?: number;
      price_note?: string;
      label?: { ar?: string };
      features?: string[];
    }
  >;
  const used = usage?.tokens_used ?? Math.max(0, user.tokensMonthly - user.tokensRemaining);
  const pct = usage?.usage_percent ?? (user.tokensMonthly ? (used / user.tokensMonthly) * 100 : 0);
  const dailyMax = useMemo(
    () => Math.max(1, ...(usage?.daily || []).map((d) => Number(d.amount || 0))),
    [usage?.daily],
  );

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "نظرة عامة" },
    { id: "usage", label: "الاستخدام" },
    { id: "billing", label: "الفوترة والخطط" },
    { id: "settings", label: "الإعدادات" },
  ];

  function selectTab(id: Tab) {
    setTab(id);
    router.replace(`/console?tab=${id}`);
  }

  return (
    <div className="web-console">
      <header className="web-console__top">
        <div>
          <p className="web-console__brand">
            {PRODUCT} <span>by {COMPANY}</span>
          </p>
          <h1>حسابك</h1>
          <p className="web-console__sub">
            الاستخدام، التوكنز، والخطط — أي ترقية هنا تُفعَّل مباشرة في التطبيق.
          </p>
        </div>
        <div className="web-console__top-actions">
          <Link href="/" className="btn btn-ghost">
            فتح التطبيق
          </Link>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              signOut();
              router.push("/login");
            }}
          >
            خروج
          </button>
        </div>
      </header>

      <nav className="web-console__tabs" aria-label="أقسام الحساب">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`web-console__tab ${tab === t.id ? "is-active" : ""}`}
            onClick={() => selectTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "overview" && (
        <section className="web-console__panel page-grid page-grid--2">
          <article className="web-stat">
            <span>الخطة</span>
            <strong>{plans[user.plan]?.label?.ar || user.plan}</strong>
            <small>{user.role}</small>
          </article>
          <article className="web-stat">
            <span>التوكنز المتبقية</span>
            <strong>{user.tokensRemaining}</strong>
            <small>من أصل {user.tokensMonthly} شهرياً</small>
          </article>
          <article className="web-stat">
            <span>المستخدم هذا الشهر</span>
            <strong>{used}</strong>
            <div className="web-meter" aria-hidden>
              <i style={{ width: `${Math.min(100, pct)}%` }} />
            </div>
            <small>{pct.toFixed(1)}% من الحصة</small>
          </article>
          <article className="web-stat">
            <span>المميزات المفتوحة</span>
            <strong>{user.entitlements.length}</strong>
            <ul className="web-feat-chips">
              {user.entitlements.slice(0, 8).map((f) => (
                <li key={f}>{FEATURE_LABELS_AR[f] || f}</li>
              ))}
            </ul>
          </article>
        </section>
      )}

      {tab === "usage" && (
        <section className="web-console__panel">
          <div className="web-stat" style={{ marginBottom: 12 }}>
            <span>ملخص الفترة</span>
            <strong>
              {used} / {user.tokensMonthly}
            </strong>
            <div className="web-meter">
              <i style={{ width: `${Math.min(100, pct)}%` }} />
            </div>
          </div>

          {(usage?.daily || []).length > 0 && (
            <div className="web-bars" aria-label="الاستخدام اليومي">
              {[...(usage?.daily || [])].reverse().map((d) => (
                <div key={String(d.day)} className="web-bars__col" title={`${d.day}: ${d.amount}`}>
                  <div
                    className="web-bars__fill"
                    style={{ height: `${(Number(d.amount || 0) / dailyMax) * 100}%` }}
                  />
                  <span>{String(d.day || "").slice(5)}</span>
                </div>
              ))}
            </div>
          )}

          {(usage?.by_reason || []).length > 0 && (
            <ul className="web-reason-list">
              {(usage?.by_reason || []).map((r) => (
                <li key={String(r.reason)}>
                  <span>{FEATURE_LABELS_AR[String(r.reason)] || r.reason}</span>
                  <em>{r.amount}</em>
                </li>
              ))}
            </ul>
          )}

          <ul className="web-usage-list">
            {(usage?.events || []).map((ev) => (
              <li key={String(ev.id || `${ev.at}-${ev.amount}`)}>
                <div>
                  <strong>{FEATURE_LABELS_AR[String(ev.reason)] || ev.reason || "task"}</strong>
                  <span>{ev.at || ""}</span>
                </div>
                <em>−{ev.amount ?? 0}</em>
              </li>
            ))}
            {!usage?.events?.length && (
              <li className="empty">لا سجلات استخدام بعد — ستظهر هنا عند عمل الوكيل.</li>
            )}
          </ul>
        </section>
      )}

      {tab === "billing" && (
        <section className="web-console__panel">
          <p className="settings-hint">
            بعد تأكيد الدفع تُفتح مميزات الخطة فوراً في {PRODUCT}. الأسعار النهائية تُضبط لاحقاً.
          </p>
          <div className="page-grid page-grid--2">
            {Object.entries(plans).map(([name, row]) => (
              <article key={name} className={`web-plan ${user.plan === name ? "is-current" : ""}`}>
                <header>
                  <strong>{row.label?.ar || name}</strong>
                  <span>{row.price_note || "السعر لاحقاً"}</span>
                </header>
                <p>{row.tokens_monthly ?? "—"} توكن / شهر</p>
                <ul>
                  {(row.features || []).slice(0, 6).map((f) => (
                    <li key={f}>{FEATURE_LABELS_AR[f] || f}</li>
                  ))}
                </ul>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy || user.plan === name}
                  onClick={() => void confirmPay(name)}
                >
                  {user.plan === name
                    ? "خطتك الحالية"
                    : ((catalog?.payments as { stripe_configured?: boolean } | undefined)
                        ?.stripe_configured
                        ? "ادفع الآن"
                        : "فعّل الخطة الآن")}
                </button>
              </article>
            ))}
          </div>
          {msg ? <p className="settings-hint">{msg}</p> : null}
          <p className="settings-hint">
            أو راجع صفحة{" "}
            <Link href="/pricing" className="back-link">
              الأسعار
            </Link>
            .
          </p>
        </section>
      )}

      {tab === "settings" && (
        <section className="web-console__panel">
          <div className="settings-form" style={{ maxWidth: 420 }}>
            <label>
              الاسم الظاهر
              <input value={user.name} onChange={(e) => update({ name: e.target.value })} />
            </label>
            <label>
              البريد
              <input value={user.email} disabled dir="ltr" />
            </label>
            <label>
              الخطة الحالية
              <input value={plans[user.plan]?.label?.ar || user.plan} disabled />
            </label>
            <p className="settings-hint">
              الجلسة مرتبطة بحساب {COMPANY}. التطبيق وسطح المكتب يستخدمان نفس الخطة والتوكنز.
            </p>
            <Link href="/pricing" className="btn btn-primary">
              ترقية الخطة
            </Link>
          </div>
        </section>
      )}
    </div>
  );
}
