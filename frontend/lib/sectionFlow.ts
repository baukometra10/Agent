/** Each section owns one job; links show how work flows between them. */

export type SectionLink = { href: string; label: string };

export type SectionMeta = {
  id: string;
  title: string;
  role: string;
  next: SectionLink[];
};

export const SECTIONS: Record<string, SectionMeta> = {
  projects: {
    id: "projects",
    title: "المشاريع",
    role: "ربط المجلدات والملفات على الجهاز",
    next: [
      { href: "/ide", label: "مساحة العمل" },
      { href: "/understanding", label: "فهم المشروع" },
      { href: "/brain", label: "عقل الوكيل" },
    ],
  },
  ide: {
    id: "ide",
    title: "مساحة العمل",
    role: "تحرير الملفات مع الوكيل في نفس الجلسة",
    next: [
      { href: "/proposals", label: "المقترحات" },
      { href: "/execution", label: "التنفيذ" },
      { href: "/projects", label: "المشاريع" },
    ],
  },
  brain: {
    id: "brain",
    title: "عقل الوكيل",
    role: "نفس وكيل مساحة العمل — أوامر ومحادثة مرتبطة بالمشروع",
    next: [
      { href: "/ide", label: "مساحة العمل" },
      { href: "/proposals", label: "المقترحات" },
      { href: "/copilot", label: "مساعد الطيار" },
    ],
  },
  understanding: {
    id: "understanding",
    title: "فهم المشروع",
    role: "بناء المعرفة والمقترحات من الكود",
    next: [
      { href: "/knowledge", label: "المعرفة" },
      { href: "/proposals", label: "المقترحات" },
      { href: "/analysis", label: "التحليل" },
    ],
  },
  analysis: {
    id: "analysis",
    title: "التحليل",
    role: "جودة وأمن وتصميم — يغذي المقترحات",
    next: [
      { href: "/proposals", label: "المقترحات" },
      { href: "/knowledge", label: "المعرفة" },
    ],
  },
  knowledge: {
    id: "knowledge",
    title: "المعرفة",
    role: "ذاكرة المشروع المشتركة بين الوكيل والفهم",
    next: [
      { href: "/brain", label: "عقل الوكيل" },
      { href: "/roadmap", label: "خارطة الطريق" },
    ],
  },
  agents: {
    id: "agents",
    title: "فريق الوكلاء",
    role: "هيكل الأوركسترا الذي يقود المحادثة والتنفيذ",
    next: [
      { href: "/brain", label: "عقل الوكيل" },
      { href: "/ide", label: "مساحة العمل" },
      { href: "/copilot", label: "مساعد الطيار" },
    ],
  },
  roadmap: {
    id: "roadmap",
    title: "خارطة الطريق",
    role: "أولويات استراتيجية تنتج مقترحات",
    next: [
      { href: "/proposals", label: "المقترحات" },
      { href: "/understanding", label: "فهم المشروع" },
    ],
  },
  proposals: {
    id: "proposals",
    title: "المقترحات",
    role: "بوابة الموافقة البشرية قبل أي تنفيذ",
    next: [
      { href: "/execution", label: "التنفيذ" },
      { href: "/copilot", label: "مساعد الطيار" },
      { href: "/log", label: "السجل" },
    ],
  },
  execution: {
    id: "execution",
    title: "التنفيذ",
    role: "تطبيق على فرع معزول ثم دمج يدوي",
    next: [
      { href: "/proposals", label: "المقترحات" },
      { href: "/ide", label: "مساحة العمل" },
      { href: "/log", label: "السجل" },
    ],
  },
  copilot: {
    id: "copilot",
    title: "مساعد الطيار",
    role: "تشغيل آلي غير مراقب → مقترحات → موافقتك",
    next: [
      { href: "/proposals", label: "المقترحات" },
      { href: "/execution", label: "التنفيذ" },
      { href: "/control-plane", label: "لوحة الأسطول" },
    ],
  },
  log: {
    id: "log",
    title: "سجل التطوير",
    role: "أثر كل نشاط من الوكيل والتنفيذ",
    next: [
      { href: "/proposals", label: "المقترحات" },
      { href: "/execution", label: "التنفيذ" },
    ],
  },
  help: {
    id: "help",
    title: "المساعدة",
    role: "مسار العمل الكامل من المشروع إلى الدمج",
    next: [
      { href: "/projects", label: "المشاريع" },
      { href: "/ide", label: "مساحة العمل" },
      { href: "/brain", label: "عقل الوكيل" },
    ],
  },
};

export function sectionLinks(id: string): SectionLink[] {
  return SECTIONS[id]?.next || [];
}
