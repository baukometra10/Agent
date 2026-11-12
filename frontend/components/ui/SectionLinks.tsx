import Link from "next/link";
import { SECTIONS, type SectionLink } from "@/lib/sectionFlow";

type Props = {
  sectionId: string;
  /** Extra links appended after the section's default flow */
  extra?: SectionLink[];
};

/** Shows this section's job + where work continues next. */
export function SectionLinks({ sectionId, extra = [] }: Props) {
  const meta = SECTIONS[sectionId];
  if (!meta) return null;
  const links = [...meta.next, ...extra];

  return (
    <div className="section-flow" aria-label="ترابط الأقسام">
      <p className="section-flow__role">
        <strong>دور هذا القسم:</strong> {meta.role}
      </p>
      {links.length > 0 ? (
        <nav className="section-flow__links">
          <span>يتصل بـ</span>
          {links.map((l) => (
            <Link key={l.href} href={l.href} className="section-flow__chip">
              {l.label}
            </Link>
          ))}
        </nav>
      ) : null}
    </div>
  );
}
