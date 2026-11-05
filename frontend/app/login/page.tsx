"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { API_URL } from "@/lib/api";
import { BrandMark } from "@/components/shell/BrandMark";
import { COMPANY, PRODUCT } from "@/lib/brand";
import { saveUser, type UserProfile } from "@/lib/user";

function toProfile(u: Record<string, unknown>, fallbackEmail: string): UserProfile {
  return {
    name: String(u.name || fallbackEmail.split("@")[0] || "عضو"),
    role: String(u.role_label || "عضو"),
    email: String(u.email || fallbackEmail),
    avatarUrl: "",
    access: u.access === "admin" ? "admin" : "user",
    plan: (u.plan as UserProfile["plan"]) || "free",
    tokensRemaining: Number(u.tokens_remaining ?? 0),
    tokensMonthly: Number(u.tokens_monthly ?? 0),
    entitlements: (u.entitlements as string[]) || [],
    sessionToken: String(u.session_token || ""),
    signedIn: Boolean(u.session_token),
  };
}

/** Anmeldung nur mit E-Mail + Telefon (Identitätsbestätigung). */
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [phoneCode, setPhoneCode] = useState("");
  const [step, setStep] = useState<"identity" | "codes">("identity");
  const [devEmail, setDevEmail] = useState("");
  const [devPhone, setDevPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [hint, setHint] = useState("");

  async function onStart(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setHint("");
    try {
      const res = await fetch(`${API_URL}/system/auth/identity/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, phone }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setError(
          data?.detail?.error === "invalid_phone"
            ? "رقم الهاتف غير صالح — استخدم الصيغة الدولية مثل +49..."
            : "تعذّر إرسال رموز التحقق.",
        );
        setBusy(false);
        return;
      }
      setPhone(String(data.phone || phone));
      setEmail(String(data.email || email));
      setDevEmail(String(data.dev_email_code || ""));
      setDevPhone(String(data.dev_phone_code || ""));
      setHint(String(data.message || ""));
      setStep("codes");
    } catch {
      setError("تعذّر الاتصال.");
    }
    setBusy(false);
  }

  async function onVerify(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/system/auth/identity/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          phone,
          email_code: emailCode,
          phone_code: phoneCode,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setError("رمز البريد أو رمز SMS غير صحيح.");
        setBusy(false);
        return;
      }
      if (data.needs_second_factor) {
        setError("تأكيد الهوية غير مكتمل — أعد المحاولة بالبريد والهاتف معاً.");
        setBusy(false);
        return;
      }
      const u = (data.user || {}) as Record<string, unknown>;
      const profile = toProfile(u, email);
      if (!profile.sessionToken) {
        setError("لم تُفعَّل الجلسة — تحقق من الرمزين.");
        setBusy(false);
        return;
      }
      saveUser(profile);
      router.push(profile.access === "admin" ? "/admin" : "/");
    } catch {
      setError("تعذّر التحقق.");
    }
    setBusy(false);
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <BrandMark gradientId="loginBrand" />
        <h1>تسجيل الدخول إلى {PRODUCT}</h1>
        <p>
          تأكيد الهوية: البريد ورقم الهاتف معاً — يُرسل رمز لكل منهما. منتج من {COMPANY}.
        </p>

        {step === "identity" ? (
          <form onSubmit={(e) => void onStart(e)} className="login-form">
            <label>
              البريد الإلكتروني
              <input
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                dir="ltr"
              />
            </label>
            <label>
              رقم الهاتف (دولي)
              <input
                required
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+4917..."
                dir="ltr"
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "…" : "إرسال رمزي التحقق"}
            </button>
          </form>
        ) : (
          <form onSubmit={(e) => void onVerify(e)} className="login-form">
            <p className="settings-hint">{hint || `رموز لـ ${email} و ${phone}`}</p>
            {(devEmail || devPhone) && (
              <p className="settings-hint" dir="ltr">
                تطوير — بريد: <strong>{devEmail || "—"}</strong> · SMS:{" "}
                <strong>{devPhone || "—"}</strong>
              </p>
            )}
            <label>
              رمز البريد
              <input
                required
                autoFocus
                value={emailCode}
                onChange={(e) => setEmailCode(e.target.value)}
                placeholder="000000"
                dir="ltr"
              />
            </label>
            <label>
              رمز SMS
              <input
                required
                value={phoneCode}
                onChange={(e) => setPhoneCode(e.target.value)}
                placeholder="000000"
                dir="ltr"
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              {busy ? "…" : "تأكيد الهوية والدخول"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                setStep("identity");
                setEmailCode("");
                setPhoneCode("");
                setDevEmail("");
                setDevPhone("");
              }}
            >
              رجوع
            </button>
          </form>
        )}
        {error ? <p className="cmd-dock__error">{error}</p> : null}
      </div>
    </div>
  );
}
