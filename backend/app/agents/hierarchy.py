"""Cursor-class agent hierarchy for Evolve.

ChiefAgent (owned internal brain) = general lead
  └─ Worker pool (coding / reasoning / critic / …)
  └─ If all busy → Chief spawns + fast-trains a new worker → assigns task
  └─ IndependentCritic never self-approves implementation

MasterOrchestrator remains the chat seat; ChiefOrchestra is the runtime pool.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentRoute:
    intent: str
    label_ar: str
    specialists: tuple[str, ...]
    include_critic: bool = False
    draft_proposal: bool = False


# Ordered specificity — first match wins after keyword scoring.
INTENT_ROUTES: tuple[IntentRoute, ...] = (
    IntentRoute(
        "design",
        "تصميم وواجهة",
        ("UIDesigner", "UXResearcher", "FrontendArchitect", "FrontendDeveloper"),
        draft_proposal=True,
    ),
    IntentRoute(
        "security",
        "أمن وثغرات",
        ("SecurityAuditor", "VulnerabilityAnalyst", "PermissionsAnalyst"),
        include_critic=True,
    ),
    IntentRoute(
        "quality",
        "اختبار وجودة",
        ("QAEngineer", "TestEngineer", "PerformanceAnalyst", "CodeReviewer"),
        include_critic=True,
    ),
    IntentRoute(
        "ops",
        "تشغيل ونشر",
        ("DevOpsEngineer", "DeploymentAgent", "MonitoringAgent"),
        include_critic=True,
    ),
    IntentRoute(
        "docs",
        "توثيق",
        ("TechnicalWriter", "APIDocumentationAgent", "KnowledgeCurator"),
        draft_proposal=True,
    ),
    IntentRoute(
        "refactor",
        "إعادة هيكلة",
        ("RefactoringAgent", "SoftwareArchitect", "CodeReviewer"),
        include_critic=True,
        draft_proposal=True,
    ),
    IntentRoute(
        "implement",
        "بناء وتطوير",
        (
            "FullstackDeveloper",
            "BackendDeveloper",
            "FrontendDeveloper",
            "SoftwareArchitect",
            "TechnicalWriter",
        ),
        include_critic=True,
        draft_proposal=True,
    ),
    IntentRoute(
        "analyze",
        "فهم وتحليل",
        (
            "CodebaseExplorer",
            "ProjectAnalyst",
            "BusinessLogicAnalyst",
            "SoftwareArchitect",
            "FeatureStrategist",
        ),
    ),
    IntentRoute(
        "product",
        "منتج ومتطلبات",
        ("ProductManager", "RequirementsAnalyst", "FeatureStrategist"),
        draft_proposal=True,
    ),
)

INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "design": (
        "ui",
        "ux",
        "design",
        "css",
        "layout",
        "واجهة",
        "تصميم",
        "شكل",
        "موقع",
        "website",
        "web app",
        "landing",
        "صفحة",
        "صفحات",
        "frontend",
        "landing page",
    ),
    "security": ("security", "auth", "xss", "permission", "vuln", "ثغر", "أمن", "صلاح"),
    "quality": ("test", "qa", "pytest", "coverage", "أداء", "اختبار", "جودة"),
    "ops": ("deploy", "docker", "ci", "k8s", "devops", "نشر", "تشغيل"),
    "docs": ("doc", "readme", "توثيق", "وثّق", "وثق"),
    "refactor": ("refactor", "cleanup", "إعادة هيكل", "نظّف", "نظف"),
    "implement": (
        "add",
        "build",
        "create",
        "implement",
        "fix",
        "endpoint",
        "app",
        "feature",
        "أضف",
        "ابني",
        "أنشئ",
        "اصنع",
        "تطبيق",
        "برنامج",
        "أصلح",
        "طوّر",
        "طور",
        "نفذ",
        "نفّذ",
        "اكتب كود",
        "اكتب لي",
        "سوي",
        "سوّي",
        "برمج",
        "software",
        "service",
        "api",
        "backend",
        "fullstack",
    ),
    "analyze": ("explain", "understand", "analyze", "what", "كيف", "اشرح", "حلل", "فهم"),
    "product": ("roadmap", "requirement", "priority", "متطلب", "منتج", "أولوية"),
}

_BUILD_HINTS = (
    "ابني",
    "بني",
    "أنشئ",
    "اصنع",
    "سوي",
    "سوّي",
    "build",
    "create",
    "make",
    "implement",
    "موقع",
    "website",
    "تطبيق",
    "برنامج",
    "landing",
    "web app",
)


def looks_like_product_build(text: str) -> bool:
    t = (text or "").lower()
    return any(h in t for h in _BUILD_HINTS)


def classify_intent(text: str) -> IntentRoute:
    t = text.lower()
    scores: dict[str, int] = {route.intent: 0 for route in INTENT_ROUTES}
    for intent, words in INTENT_KEYWORDS.items():
        for w in words:
            if w in t:
                scores[intent] = scores.get(intent, 0) + (2 if len(w) > 3 else 1)

    # Product/build briefs prefer design when UI/site language is present,
    # otherwise implement — never fall through to analyze-only for clear builds.
    if looks_like_product_build(t):
        if scores.get("design", 0) >= scores.get("implement", 0) and (
            scores.get("design", 0) > 0
            or any(
                w in t
                for w in ("موقع", "website", "landing", "واجهة", "ui", "صفحة", "frontend")
            )
        ):
            return next(r for r in INTENT_ROUTES if r.intent == "design")
        return next(r for r in INTENT_ROUTES if r.intent == "implement")

    best_intent = max(scores, key=lambda k: scores[k])
    if scores[best_intent] <= 0:
        # Default Cursor-like: explore then ready to implement
        return next(r for r in INTENT_ROUTES if r.intent == "analyze")
    return next(r for r in INTENT_ROUTES if r.intent == best_intent)


def hierarchy_overview() -> dict:
    return {
        "conductor": {
            "name": "MasterOrchestrator",
            "role": "Chat seat — plans, routes via Chief, synthesizes; never silent-writes production code",
        },
        "chief": {
            "name": "ChiefAgent",
            "role": (
                "General lead on owned internal models — assigns tasks to workers; "
                "when all busy, spawns + fast-trains a new worker and assigns the task"
            ),
        },
        "critic": {
            "name": "IndependentCritic",
            "role": "Challenges weak plans; cannot be bypassed for risky changes",
        },
        "departments": [
            "understanding",
            "engineering",
            "design",
            "product",
            "development",
            "security",
            "quality",
            "operations",
            "documentation",
        ],
        "intents": [
            {
                "intent": r.intent,
                "label_ar": r.label_ar,
                "specialists": list(r.specialists),
                "include_critic": r.include_critic,
                "draft_proposal": r.draft_proposal,
            }
            for r in INTENT_ROUTES
        ],
    }
