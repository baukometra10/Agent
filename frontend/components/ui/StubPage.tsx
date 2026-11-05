import { GlassCard } from "./GlassCard";

type Props = {
  title: string;
  phase: string;
  description: string;
};

export function StubPage({ title, phase, description }: Props) {
  return (
    <div>
      <header className="page-head">
        <h1>{title}</h1>
        <p>{description}</p>
      </header>
      <GlassCard className="stub-panel">
        <span className="stub-badge">قريبًا — {phase}</span>
        <p>
          هذه الشاشة جاهزة ضمن هيكل التنقل وستُربط بواجهات البرمجة في المراحل اللاحقة. يمكنك العودة
          إلى لوحة التحكم لمتابعة حالة الوكيل والمشاريع النشطة.
        </p>
      </GlassCard>
    </div>
  );
}
