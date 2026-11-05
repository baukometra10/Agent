import { COMPANY, PRODUCT } from "@/lib/brand";

type Props = {
  compact?: boolean;
  className?: string;
  gradientId?: string;
};

export function BrandMark({
  compact = false,
  className = "",
  gradientId = "brainGlow",
}: Props) {
  return (
    <div className={`brand-lockup ${compact ? "brand-lockup--compact" : ""} ${className}`.trim()}>
      <div className="brand-mark" aria-hidden>
        <span className="brand-mark__glow" />
        <svg viewBox="0 0 48 48" className="brand-mark__svg">
          <defs>
            <radialGradient id={gradientId} cx="50%" cy="45%" r="55%">
              <stop offset="0%" stopColor="#9EF0E6" />
              <stop offset="55%" stopColor="#2EC4B6" />
              <stop offset="100%" stopColor="#1A6B7A" />
            </radialGradient>
          </defs>
          <ellipse cx="24" cy="24" rx="16" ry="14" fill={`url(#${gradientId})`} opacity="0.95" />
          <path
            d="M16 22c0-5 3.5-9 8-9s8 4 8 9c0 2-.5 3.5-1.5 5M20 18c1.5-1 3-1.5 4-1.5M28 18c-1 0-2 .3-3 1M18 26c2 2 4 3 6 3s4-1 6-3"
            stroke="#D7F8F4"
            strokeWidth="1.4"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
      </div>
      <div className="brand-lockup__text">
        <strong>{PRODUCT}</strong>
        <span>{COMPANY}</span>
      </div>
    </div>
  );
}
