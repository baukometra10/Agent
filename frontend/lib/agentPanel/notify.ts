/** Desktop notifications when a background agent tab finishes. */

let asked = false;

export async function ensureNotifyPermission(): Promise<boolean> {
  if (typeof window === "undefined" || !("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  if (asked) return false;
  asked = true;
  try {
    const res = await Notification.requestPermission();
    return res === "granted";
  } catch {
    return false;
  }
}

export function notifyTabDone(opts: {
  title: string;
  body?: string;
  tag?: string;
  onClick?: () => void;
}): void {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  // Only when user is looking elsewhere
  if (document.visibilityState === "visible" && document.hasFocus()) return;
  try {
    const n = new Notification(opts.title || "Spixa", {
      body: opts.body || "اكتمل رد الوكيل",
      tag: opts.tag || "spixa-agent",
    });
    n.onclick = () => {
      window.focus();
      opts.onClick?.();
      n.close();
    };
  } catch {
    /* ignore */
  }
}
