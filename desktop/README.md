# Spixa Desktop

تطبيق سطح المكتب لـ **Spixa** من **Suppix AI** — نفس مساحة العمل على الويب، داخل نافذة أصلية.

## التشغيل

1. شغّل خادم Spixa (API + واجهة الويب) كما في المشروع الرئيسي.
2. من هذا المجلد:

```bash
npm install
npm start
```

يفتح التطبيق على `http://localhost:3000/ide` افتراضياً.

تغيير العنوان:

```bash
# Windows PowerShell
$env:SPIXA_URL="https://your-host/ide"; npm start
```

## البناء

```bash
npm run dist
```

ينتج مثبتات تحت `dist/` حسب نظامك.
