"use client";

import Link from "next/link";
import { IconGear } from "@/components/icons";
import { useUser } from "@/hooks/useUser";
import { planLabel } from "@/lib/uiLabels";
import { AutopilotToggle } from "./AutopilotToggle";
import { BrandMark } from "./BrandMark";
import { CommandSearch } from "./CommandSearch";
import { IdeTopbarHost } from "./IdeTopbarSlot";
import { NotificationsMenu } from "./NotificationsMenu";
import { UserMenu } from "./UserMenu";

type Props = {
  navOpen: boolean;
  onToggleNav: () => void;
};

export function Topbar({ navOpen, onToggleNav }: Props) {
  const { user } = useUser();
  const used = Math.max(0, user.tokensMonthly - user.tokensRemaining);
  const pct = user.tokensMonthly ? Math.min(100, (used / user.tokensMonthly) * 100) : 0;

  return (
    <header className="topbar">
      <button
        type="button"
        className={`icon-btn topbar__nav-toggle ${navOpen ? "is-active" : ""}`}
        onClick={onToggleNav}
        aria-label={navOpen ? "إغلاق القائمة الجانبية" : "فتح القائمة الجانبية"}
        aria-expanded={navOpen}
        title={navOpen ? "إغلاق القائمة" : "فتح القائمة"}
      >
        <IconGear size={20} />
      </button>

      <Link href="/" className="topbar__brand-link" aria-label="الصفحة الرئيسية">
        <BrandMark className="topbar__brand" gradientId="brainGlowTop" />
      </Link>

      <CommandSearch />

      <IdeTopbarHost />

      <AutopilotToggle />

      <div className="topbar__user">
        {user.signedIn ? (
          <Link href="/console?tab=usage" className="token-chip" title="الاستخدام والفوترة">
            <span className="token-chip__plan">{planLabel(user.plan)}</span>
            <span className="token-chip__count">{user.tokensRemaining}</span>
            <span className="token-chip__meter" aria-hidden>
              <i style={{ width: `${pct}%` }} />
            </span>
          </Link>
        ) : null}
        <NotificationsMenu />
        <UserMenu />
      </div>
    </header>
  );
}
