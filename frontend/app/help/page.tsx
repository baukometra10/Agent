"use client";

import Link from "next/link";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { SectionLinks } from "@/components/ui/SectionLinks";

const steps = [
  { href: "/projects", title: "افتح مشروعاً", text: "مساحة عمل للملفات والتطبيقات مع عزل كامل." },
  {
    href: "/brain",
    title: "تحدّث مع العقل",
    text: "أو افتح «الوكيل» (Ctrl+J) — نفس وكيل مساحة العمل في أي صفحة.",
  },
  { href: "/understanding", title: "شغّل الفهم", text: "الوكلاء يبنون معرفة وخارطة ومقترحات." },
  { href: "/proposals", title: "اعتمد المقترح", text: "لا تنفيذ بدون موافقتك." },
  { href: "/execution", title: "نفّذ ثم ادمج", text: "فرع معزول، ثم دمج بشري صريح." },
  {
    href: "/ide",
    title: "مساحة العمل",
    text: "افتح الملفات وعدّلها في المتصفح — نفس تجربة سطح المكتب.",
  },
  {
    href: "/download",
    title: "تنزيل سطح المكتب",
    text: "حمّل تطبيق Spixa وافتح نفس المساحة في نافذة أصلية.",
  },
  {
    href: "/console",
    title: "الحساب على الويب",
    text: "الاستخدام، التوكنز، والفوترة — التفعيل فوري بعد الدفع.",
  },
  { href: "/pricing", title: "الخطط", text: "عرض حصص التوكنز والترقية حسب الخطة." },
];

export default function HelpPage() {
  return (
    <div>
      <PageHeader
        eyebrow="دليل سريع"
        title="المساعدة"
        subtitle="مساحة عمل سحابية وسطح مكتب: وكيل موحّد، مشاريع معزولة، وبوابة بشرية قبل أي تنفيذ."
      />
      <SectionLinks sectionId="help" />
      <div className="page-grid page-grid--2 help-grid">
        {steps.map((s) => (
          <GlassCard key={s.href} title={s.title}>
            <p style={{ color: "var(--muted)", marginTop: 0 }}>{s.text}</p>
            <Link href={s.href} className="btn btn-primary">
              فتح
            </Link>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
