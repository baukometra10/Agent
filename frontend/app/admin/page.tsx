"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL } from "@/lib/api";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { isAdmin, useUser } from "@/hooks/useUser";
import { accountStatusLabel, formatIsoWhen, planLabel } from "@/lib/uiLabels";

const links = [
  {
    href: "/settings",
    title: "ملكية النماذج والتدريب",
    text: "تقييم، ضبط دقيق، تقاعد المعلّمين، رفع التغطية — للمسؤول فقط.",
  },
  {
    href: "/settings#rapid-learning",
    title: "منظومة التعلم السريع",
    text: "سبع طبقات · مختبر متعدد الوكلاء · تعلّم من نتائج التنفيذ.",
  },
  {
    href: "/settings#model-factory",
    title: "مصنع تطوير النماذج",
    text: "خمسة محركات · تقييم مستقل · موافقة بشرية قبل الإنتاج.",
  },
  {
    href: "/settings#spixa-ecosystem",
    title: "منظومة ذكاء Spixa",
    text: "ستة تخصصات مملوكة · منسّق · خارطة المراحل.",
  },
  {
    href: "/settings#intelligence-ops",
    title: "نضج · ملكية · استقلال · تطور",
    text: "بوابات جودة · سجل ملكية · فحص استقلال · لوحة تطور.",
  },
  {
    href: "/control-plane",
    title: "لوحة الأسطول",
    text: "إدارة متعددة المشاريع على مستوى المنصة.",
  },
  {
    href: "/maintain",
    title: "صيانة ذاتية",
    text: "دورات إصلاح المنصة دون لمس أصول مشاريع الأعضاء.",
  },
];

type AdminUser = {
  email?: string;
  phone?: string;
  plan?: string;
  status?: string;
  access?: string;
  email_verified?: boolean;
  phone_verified?: boolean;
  tokens_remaining?: number;
  last_login?: string;
};

type Alert = {
  id?: string;
  title?: string;
  detail?: string;
  severity?: string;
  email?: string;
  at?: string;
  acked?: boolean;
};

export default function AdminPage() {
  const { user } = useUser();
  const router = useRouter();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [ace, setAce] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState("");

  const reload = useCallback(async () => {
    try {
      const [uRes, aRes, cRes] = await Promise.all([
        fetch(`${API_URL}/system/admin/users`, { cache: "no-store" }),
        fetch(`${API_URL}/system/admin/alerts?limit=50`, { cache: "no-store" }),
        fetch(`${API_URL}/system/ownership/cost-efficiency`, { cache: "no-store" }),
      ]);
      if (uRes.ok) {
        const d = await uRes.json();
        setUsers(d.users || []);
      }
      if (aRes.ok) {
        const d = await aRes.json();
        setAlerts(d.alerts || []);
      }
      if (cRes.ok) setAce(await cRes.json());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (user.signedIn && !isAdmin(user)) router.replace("/");
  }, [user, router]);

  useEffect(() => {
    if (!isAdmin(user)) return;
    void reload();
    const t = setInterval(() => void reload(), 15000);
    return () => clearInterval(t);
  }, [user, reload]);

  async function setStatus(email: string, status: string) {
    setBusy(email + status);
    await fetch(`${API_URL}/system/admin/users/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, status, reason: `admin:${user.email}` }),
    });
    await reload();
    setBusy("");
  }

  async function ack(id: string) {
    await fetch(`${API_URL}/system/admin/alerts/${id}/ack`, { method: "POST" });
    await reload();
  }

  if (!isAdmin(user)) {
    return (
      <div>
        <PageHeader title="غير مصرح" subtitle="هذه الوحدة للمسؤول الأعلى فقط." />
      </div>
    );
  }

  const openAlerts = alerts.filter((a) => !a.acked);

  return (
    <div>
      <PageHeader
        eyebrow="صلاحيات عليا"
        title="وحدة التحكم العليا"
        subtitle="الذكاء الداخلي أولًا · المستخدمون · التنبيهات · اقتصاد النماذج."
      />

      {ace ? (
        <GlassCard title="كفاءة تكلفة الذكاء">
          <p style={{ marginTop: 0, color: "var(--muted)" }}>
            {(ace.doctrine_ar as string) || "الذكاء الداخلي أولًا"}
          </p>
          <div className="fleet-kpis">
            <div>
              <span>الكفاءة</span>
              <strong>{Number(ace.score ?? 0).toFixed(0)}</strong>
            </div>
            <div>
              <span>داخلي</span>
              <strong>{Math.round(Number(ace.internal_task_ratio ?? 0) * 100)}%</strong>
            </div>
            <div>
              <span>خارجي $</span>
              <strong style={{ fontSize: "0.9rem" }}>
                {Number(ace.external_cost_usd ?? 0).toFixed(4)}
              </strong>
            </div>
            <div>
              <span>$ / نجاح</span>
              <strong style={{ fontSize: "0.9rem" }}>
                {Number(ace.cost_per_successful_task_usd ?? 0).toFixed(5)}
              </strong>
            </div>
          </div>
          <Link href="/settings" className="btn btn-ghost" style={{ marginTop: 8 }}>
            ملكية النماذج والتقطير
          </Link>
        </GlassCard>
      ) : null}

      <section className="admin-ops">
        <GlassCard title={`تنبيهات فورية (${openAlerts.length} مفتوحة)`}>
          <p className="settings-hint">
            أي إساءة أو خلل يُسجَّل هنا ويُرسل فوراً إلى قناة التنبيه إن وُجدت.
          </p>
          <ul className="admin-alert-list">
            {!alerts.length && <li className="empty">لا تنبيهات بعد.</li>}
            {alerts.map((a) => (
              <li key={String(a.id)} className={`sev-${a.severity || "medium"} ${a.acked ? "is-acked" : ""}`}>
                <div>
                  <strong>{a.title}</strong>
                  <span dir="ltr">{a.email || "—"}</span>
                  <p>{a.detail}</p>
                  <small dir="ltr">{a.at}</small>
                </div>
                {!a.acked && a.id ? (
                  <button type="button" className="btn btn-ghost" onClick={() => void ack(String(a.id))}>
                    تمت المعالجة
                  </button>
                ) : (
                  <em>مغلق</em>
                )}
              </li>
            ))}
          </ul>
        </GlassCard>

        <GlassCard title={`المستخدمون (${users.length})`}>
          <div className="admin-users">
            {!users.length && <p className="empty">لا مستخدمين بعد.</p>}
            {users.map((u) => (
              <article key={String(u.email)} className="admin-user">
                <header>
                  <strong dir="ltr">{u.email}</strong>
                  <span>{accountStatusLabel(u.status)}</span>
                </header>
                <p>
                  هاتف: <span dir="ltr">{u.phone || "—"}</span>
                  {" · "}
                  {planLabel(u.plan)} · توكن {u.tokens_remaining}
                </p>
                <p>
                  بريد {u.email_verified ? "موثَّق" : "غير موثَّق"} · هاتف{" "}
                  {u.phone_verified ? "موثَّق" : "غير موثَّق"} ·{" "}
                  {u.access === "admin" ? "مسؤول" : "عضو"}
                </p>
                <small>آخر دخول: {formatIsoWhen(u.last_login) || "—"}</small>
                {u.access !== "admin" ? (
                  <div className="admin-user__actions">
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={busy !== ""}
                      onClick={() => void setStatus(String(u.email), "suspended")}
                    >
                      إيقاف
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={busy !== ""}
                      onClick={() => void setStatus(String(u.email), "banned")}
                    >
                      حظر
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={busy !== ""}
                      onClick={() => void setStatus(String(u.email), "active")}
                    >
                      تفعيل
                    </button>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        </GlassCard>
      </section>

      <div className="page-grid page-grid--2" style={{ marginTop: "1.25rem" }}>
        {links.map((l) => (
          <GlassCard key={l.href} title={l.title}>
            <p style={{ color: "var(--muted)", marginTop: 0 }}>{l.text}</p>
            <Link href={l.href} className="btn btn-primary">
              فتح
            </Link>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
