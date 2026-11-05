"use client";

import Link from "next/link";
import { GlassCard } from "@/components/ui/GlassCard";
import { PageHeader } from "@/components/ui/PageHeader";

const steps = [
  { href: "/projects", title: "افتح مشروعاً", text: "مساحة عمل للملفات والتطبيقات مع عزل كامل." },
  { href: "/brain", title: "تحدّث مع العقل", text: "أو استخدم زر «أمر» / Ctrl+J للأوامر اليدوية في أي صفحة." },
  { href: "/understanding", title: "شغّل الفهم", text: "الوكلاء يبنون معرفة وخارطة ومقترحات." },
  { href: "/proposals", title: "اعتمد المقترح", text: "لا تنفيذ بدون موافقتك." },
  { href: "/execution", title: "نفّذ ثم ادمج", text: "فرع Git معزول، ثم دمج بشري صريح." },
  { href: "/ide", title: "مساحة العمل IDE", text: "افتح الملفات وعدّلها في المتصفح — نفس تجربة سطح المكتب." },
  { href: "/download", title: "تنزيل سطح المكتب", text: "حمّل تطبيق Spixa من الموقع وافتح نفس المساحة في نافذة أصلية." },
  { href: "/console", title: "الحساب على الويب", text: "الاستخدام، التوكنز، والفوترة — التفعيل فوري بعد الدفع." },
  { href: "/pricing", title: "الخطط", text: "عرض حصص التوكنز والترقية حسب الخطة." },
];

export default function HelpPage() {
  return (
    <div>
      <PageHeader
        eyebrow="دليل سريع"
        title="المساعدة"
        subtitle="Spixa من Suppix AI — مساحة عمل سحابية وسطح مكتب: أوامر يدوية، مشاريع معزولة، وبوابة بشرية قبل أي تنفيذ."
      />
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
