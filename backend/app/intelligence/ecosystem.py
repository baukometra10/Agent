"""Spixa Proprietary Intelligence Ecosystem — adopted strategy catalog."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.distillation.engine import get_distillation_engine
from app.gateway.internal import family_catalog
from app.gateway.intelligent_router import get_intelligent_router
from app.training.lora import get_lora_trainer

SPIXA_FAMILY: tuple[dict[str, Any], ...] = (
    {
        "product": "Spixa Reasoner",
        "specialty": "reasoning",
        "internal_id": "internal/reasoning",
        "adapter": "lora-reasoning",
        "priority": "very_high",
        "priority_ar": "عالية جدًا",
        "role_ar": "التفكير والتحليل والتخطيط",
    },
    {
        "product": "Spixa Coder",
        "specialty": "coding",
        "internal_id": "internal/coding",
        "adapter": "lora-coding",
        "priority": "critical",
        "priority_ar": "قصوى",
        "role_ar": "كتابة الكود وتعديله وإصلاحه",
    },
    {
        "product": "Spixa Architect",
        "specialty": "project_intelligence",
        "internal_id": "internal/project-intelligence",
        "adapter": "lora-project-intel",
        "priority": "critical",
        "priority_ar": "قصوى",
        "role_ar": "فهم المشاريع وتصميم المعماريات",
    },
    {
        "product": "Spixa Critic",
        "specialty": "critic",
        "internal_id": "internal/critic",
        "adapter": "lora-critic",
        "priority": "high",
        "priority_ar": "عالية",
        "role_ar": "مراجعة النتائج واكتشاف الأخطاء والمخاطر",
    },
    {
        "product": "Spixa Vision",
        "specialty": "vision",
        "internal_id": "internal/vision",
        "adapter": "lora-vision",
        "priority": "medium",
        "priority_ar": "متوسطة",
        "role_ar": "فهم الواجهات والتصميمات وتحليل الصور",
    },
    {
        "product": "Spixa Embed",
        "specialty": "embeddings",
        "internal_id": "internal/embeddings",
        "adapter": "lora-embeddings",
        "priority": "high",
        "priority_ar": "عالية",
        "role_ar": "البحث الدلالي وربط المعرفة واسترجاعها",
    },
)

LAYERS: tuple[dict[str, str], ...] = (
    {"id": "product", "title": "Spixa Product Layer", "items": "Web · IDE · Desktop · API · Project Fleet"},
    {
        "id": "orchestrator",
        "title": "Spixa Intelligence Orchestrator",
        "items": "Task planning · agent/model coordination · critic loop",
    },
    {
        "id": "gateway",
        "title": "Private Model Gateway",
        "items": "Routing · load · context · cost · entitlements",
    },
    {"id": "specialties", "title": "Specialty Models", "items": "Reasoner · Coder · Architect · Critic · Vision · Embed"},
    {
        "id": "knowledge",
        "title": "Knowledge & Project Intelligence",
        "items": "PostgreSQL · pgvector · Knowledge Graph · Project Memory",
    },
    {
        "id": "factory",
        "title": "Learning & Training Factory",
        "items": "Distillation · Synthetic · Train · Eval · Human gates",
    },
    {
        "id": "infra",
        "title": "Infrastructure & Governance",
        "items": "GPU · Storage · Docker · Security · Registry · Monitoring",
    },
    {
        "id": "governance_crosscut",
        "title": "Human-gated promotion",
        "items": "No production weight/router mutation without factory approval",
    },
)

INTELLIGENCE_ROADMAP: tuple[dict[str, Any], ...] = (
    {
        "id": "I1",
        "name": "Real Training Foundation",
        "name_ar": "أساس التدريب الحقيقي",
        "weeks": "3–5",
        "status": "deferred_until_staging",
        "focus": ["gpu_lora_qlora", "adapter_registry", "pre_post_eval", "first_approved_adapter"],
    },
    {
        "id": "I2",
        "name": "Spixa Coding Intelligence",
        "name_ar": "ذكاء البرمجة",
        "weeks": "4–6",
        "status": "planned",
        "focus": ["coding_corpus", "coder_adapter", "sandbox_exec", "vs_teacher"],
    },
    {
        "id": "I3",
        "name": "Engineering Intelligence",
        "name_ar": "الذكاء الهندسي",
        "weeks": "4–6",
        "status": "planned",
        "focus": ["reasoner", "architect", "large_project_memory"],
    },
    {
        "id": "I4",
        "name": "Quality Intelligence",
        "name_ar": "ذكاء الجودة",
        "weeks": "3–5",
        "status": "planned",
        "focus": ["critic", "security_perf", "agent_eval"],
    },
    {
        "id": "I5",
        "name": "Model Collaboration",
        "name_ar": "تعاون النماذج",
        "weeks": "4–6",
        "status": "planned",
        "focus": ["team_protocols", "fan_out", "team_vs_solo"],
    },
    {
        "id": "I6",
        "name": "Continuous Intelligence Evolution",
        "name_ar": "تطور ذكاء مستمر",
        "weeks": "2–4 months then ongoing",
        "status": "planned",
        "focus": ["execution_learning", "release_trail", "cost_per_success", "routing"],
    },
)

STACK_KEEP: dict[str, str] = {
    "backend": "Python + FastAPI",
    "orchestration": "LangGraph + Chief Agent",
    "serving": "Ollama now → vLLM / SGLang when needed",
    "training": "PyTorch + Transformers + PEFT + TRL",
    "database": "PostgreSQL + pgvector (SQLite ok in local dev)",
    "code_intel": "Tree-sitter + AST",
    "evaluation": "pytest + held-out benchmarks",
    "registry_target": "MLflow",
    "data_versioning_target": "DVC",
    "isolation": "Docker",
    "frontend": "Next.js + TypeScript",
}


def ecosystem_blueprint() -> dict[str, Any]:
    settings = get_settings()
    adapters = {a.get("adapter"): a for a in get_lora_trainer().list_adapters()}
    family_live = []
    for spec in SPIXA_FAMILY:
        ad = adapters.get(spec["adapter"]) or {}
        family_live.append(
            {
                **spec,
                "ready": bool(ad.get("ready")),
                "adapter_meta_status": (ad.get("meta") or {}).get("status")
                if isinstance(ad.get("meta"), dict)
                else None,
            }
        )

    return {
        "product": "Spixa",
        "ecosystem": "Spixa Proprietary Intelligence Ecosystem",
        "ecosystem_ar": "منظومة ذكاء Spixa المملوكة",
        "adopted": True,
        "priorities": [
            "speed_to_advanced_capability",
            "engineering_quality",
            "ownership_of_weights_data_training",
            "lower_ops_and_train_cost",
        ],
        "priorities_ar": [
            "سرعة الوصول إلى قدرات متقدمة",
            "جودة هندسية عالية",
            "ملكية الأوزان والبيانات والتدريب",
            "تقليل التكلفة التشغيلية والتدريبية",
        ],
        "company_doctrine": (
            "Spixa is an AI company that owns a family of specialized minds — "
            "not merely a platform that uses others' models."
        ),
        "company_doctrine_ar": (
            "Spixa شركة ذكاء اصطناعي تملك عائلة عقول متخصصة — "
            "لا مجرد منصة تستخدم نماذج الآخرين."
        ),
        "next_chapter": [
            "real_training",
            "independent_evaluation",
            "own_weights_and_data",
            "prove_on_real_engineering_tasks",
        ],
        "next_chapter_ar": [
            "التدريب الحقيقي",
            "الاختبارات المستقلة",
            "امتلاك الأوزان والبيانات",
            "إثبات التفوق في المهام الهندسية الفعلية",
        ],
        "non_goal": {
            "train_huge_foundation_from_scratch_as_success_gate": False,
            "note_ar": (
                "لن نجعل تدريب نموذج أساسي ضخم من الصفر شرط نجاح. "
                "نملك التخصصات عبر أفضل مسار تقني لكل مجال؛ "
                "الاستقلال الكامل عن أوزان الأساس مرحلة لاحقة اختيارية."
            ),
        },
        "ownership_shape": {
            "day_one": "shared_open_weight_base_plus_lora_adapters",
            "later": "split_full_models_when_eval_justifies_cost",
            "we_own": [
                "licensed_training_data",
                "synthetic_data",
                "adapter_weights",
                "release_versions",
                "train_eval_tooling",
                "gateway_and_orchestrator",
                "spixa_engineering_knowledge",
            ],
            "base_weights_note": (
                "Adapter ownership does not automatically equal base-weight ownership; "
                "document license per component."
            ),
        },
        "orchestrator": {
            "name": "Spixa Intelligence Orchestrator",
            "implements_via": ["chief_agent", "intelligent_router", "model_gateway", "multi_agent_lab"],
            "rules": [
                "understand_task",
                "select_specialty",
                "fan_out_when_needed",
                "gather_results",
                "independent_critique",
                "retry_or_ship",
                "no_random_peer_links_unified_protocol",
            ],
        },
        "family": family_live,
        "layers": list(LAYERS),
        "roadmap": list(INTELLIGENCE_ROADMAP),
        "stack_keep": STACK_KEEP,
        "live": {
            "prefer_internal": settings.prefer_internal,
            "lora_real_train_enabled": settings.lora_real_train_enabled,
            "factory_require_human_approval": settings.factory_require_human_approval,
            "internal_family": family_catalog(settings),
            "router_metrics": get_intelligent_router().status().get("metrics"),
            "distillation": get_distillation_engine().stats(),
        },
        "docs": "docs/SPIXA_INTELLIGENCE.md",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
