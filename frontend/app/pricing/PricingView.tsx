"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { API_URL } from "@/lib/api";
import { FEATURE_LABELS_AR } from "@/lib/billing";
import { COMPANY, PRODUCT, PRODUCT_TAGLINE } from "@/lib/brand";
import { useUser } from "@/hooks/useUser";

export default function PricingPage() {
  const { user } = useUser();
  const search = useSearchParams();
  const need = search.get("need") || "";
  const [plans, setPlans] = useState<
    Record<string, { tokens_monthly?: number; price_note?: string; label?: { ar?: string }; features?: string[] }>
  >({});

  useEffect(() => {
    fetch(`${API_URL}/system/billing/catalog`)
      .then((r) => r.json())
      .then((d) => setPlans(d.plans || {}))
      .catch(() => undefined);
  }, []);

  return (
    <div className="pricing-page">
      <header className="pricing-hero">
        <p className="web-console__brand">
          {PRODUCT} <span>by {COMPANY}</span>
        </p>
        <h1>الخطط والتوكنز</h1>
        <p>{PRODUCT_TAGLINE}. اختر خطة — بعد تأكيد الدفع تُفعَّل المميزات في التطبيق فوراً.</p>
        {need ? (
          <p className="pricing-need">
            الميزة «{FEATURE_LABELS_AR[need] || need}» غير مفتوحة في خطتك الحالية — اختر خطة أعلى للتفعيل.
          </p>
        ) : null}
        <div className="pricing-hero__actions">
          <Link href={user.signedIn ? "/console?tab=billing" : "/login"} className="btn btn-primary">
            {user.signedIn ? "إدارة الحساب" : "تسجيل الدخول"}
          </Link>
          <Link href="/" className="btn btn-ghost">
            التطبيق
          </Link>
        </div>
      </header>
      <div className="pricing-grid">
        {Object.entries(plans).map(([name, row]) => {
          const unlocksNeed = need ? (row.features || []).includes(need) : false;
          return (
            <article
              key={name}
              className={`web-plan ${user.plan === name ? "is-current" : ""} ${unlocksNeed ? "is-unlock" : ""}`}
            >
              <header>
                <strong>{row.label?.ar || name}</strong>
                <span>{row.price_note || "السعر لاحقاً"}</span>
              </header>
              <p className="pricing-tokens">{row.tokens_monthly ?? "—"} توكن / شهر</p>
              <ul>
                {(row.features || []).map((f) => (
                  <li key={f} className={f === need ? "is-need" : undefined}>
                    {FEATURE_LABELS_AR[f] || f}
                  </li>
                ))}
              </ul>
              <Link href="/console?tab=billing" className="btn btn-primary">
                {user.plan === name ? "خطتك" : "متابعة الدفع"}
              </Link>
            </article>
          );
        })}
      </div>
    </div>
  );
}
