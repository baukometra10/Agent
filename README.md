# Evolve — AI Software Evolution Platform

## ملف التشغيل (مهم)

الملف الصحيح للتشغيل على Windows:

```text
c:\Users\u4363\Desktop\Agent\start.ps1
```

### شغّله هكذا

```powershell
cd c:\Users\u4363\Desktop\Agent
.\start.ps1          # تشغيل موثوق + انتظار /health
.\stop.ps1           # إيقاف نظيف
```

- **API** → http://127.0.0.1:7000/docs  
- **الواجهة** → http://localhost:3000  

لا يحتاج Docker (SQLite). المنفذ ثابت `7000` ويُكتب في `frontend/.env.local` حتى لا يحدث تعارض متقطع مع الواجهة.

> Windows/Hyper-V يحجز ~7932–9031 فيمنع `8000`. لا تستخدمه.

## بدائل

| الملف | الوظيفة |
|------|---------|
| `start.ps1` | **التشغيل الرئيسي** (API + UI) |
| `scripts\run-dev.ps1` | يستدعي `start.ps1` |
| `docker-compose.yml` | تشغيل كامل مع Postgres (يحتاج Docker Desktop) |

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Vision](docs/VISION.md)
- [Phases](docs/PHASES.md)
