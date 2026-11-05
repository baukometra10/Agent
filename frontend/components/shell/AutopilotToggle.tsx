"use client";

import Link from "next/link";
import { useAutopilot } from "@/hooks/useAutopilot";

/**
 * Visible global switch:
 * - ON  → الوكيل يعمل وحده (sandbox / اقتراحات / مخاطر) عبر حلقة خلفية
 * - OFF → وضع يدوي: المستخدم يعطي الأوامر بنفسه
 * - Paused → الشات اليدوي أوقف الدورات مؤقتاً
 */
export function AutopilotToggle() {
  const { enabled, paused, busy, loading, lastRun, loopRunning, setEnabled, resume } =
    useAutopilot();

  // المسمّى الرسمي يبدأ دائماً بـ «مساعد الطيار»
  let label = "مساعد الطيار · متوقف";
  if (loading) label = "مساعد الطيار…";
  else if (enabled && paused) label = "مساعد الطيار · معلّق";
  else if (enabled) label = loopRunning ? "مساعد الطيار · نشط" : "مساعد الطيار · يعمل";

  const title = enabled
    ? paused
      ? "مساعد الطيار معلّق لأنك تعمل يدوياً — اضغط لاستئنافه، أو افتح التفاصيل."
      : "مساعد الطيار مفعّل — دورات تجريبية تلقائية. اضغط لإيقافه والعمل يدوياً."
    : "مساعد الطيار متوقف — أنت تعطي الأوامر. اضغط للتشغيل ليعمل الوكيل وحده.";

  async function onClick() {
    if (enabled && paused) {
      await resume();
      return;
    }
    await setEnabled(!enabled);
  }

  const css =
    enabled && paused ? "is-paused" : enabled ? "is-on" : "is-off";

  return (
    <div className={`autopilot-toggle ${css}`}>
      <button
        type="button"
        className="autopilot-toggle__btn"
        disabled={busy || loading}
        aria-pressed={enabled && !paused}
        aria-label={label}
        title={title}
        onClick={() => void onClick()}
      >
        <span className="autopilot-toggle__pulse" aria-hidden />
        <span className="autopilot-toggle__text">
          <strong>مساعد الطيار</strong>
          <small>
            {busy
              ? enabled
                ? paused
                  ? "مساعد الطيار · يستأنف…"
                  : "مساعد الطيار · يتوقف…"
                : "مساعد الطيار · يبدأ…"
              : label.replace(/^مساعد الطيار ·\s*/, "")}
          </small>
        </span>
        <span className="autopilot-toggle__switch" aria-hidden>
          <span className="autopilot-toggle__knob" />
        </span>
      </button>
      <Link href="/copilot" className="autopilot-toggle__more" title="صفحة مساعد الطيار">
        {lastRun ? "تقرير المساعد" : "تفاصيل"}
      </Link>
    </div>
  );
}
