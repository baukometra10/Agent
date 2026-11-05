import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  className?: string;
  title?: string;
  action?: ReactNode;
  as?: "section" | "article" | "div";
};

export function GlassCard({
  children,
  className = "",
  title,
  action,
  as: Tag = "section",
}: Props) {
  return (
    <Tag className={`glass-card ${className}`.trim()}>
      {(title || action) && (
        <header className="glass-card__head">
          {title ? <h2 className="glass-card__title">{title}</h2> : <span />}
          {action}
        </header>
      )}
      {children}
    </Tag>
  );
}
