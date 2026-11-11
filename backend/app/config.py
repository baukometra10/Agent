from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[2]  # .../Agent
_BACKEND = Path(__file__).resolve().parents[1]


def _normalize_database_url(url: str, *, async_driver: bool) -> str:
    """Accept Railway/Heroku-style postgres:// and map to SQLAlchemy drivers."""
    u = (url or "").strip()
    if not u:
        return u
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://") :]
    if async_driver:
        if u.startswith("postgresql://") and "+asyncpg" not in u.split("://", 1)[0]:
            u = "postgresql+asyncpg://" + u[len("postgresql://") :]
    else:
        # sync psycopg2 — strip asyncpg if someone reused the async URL
        if "+asyncpg" in u.split("://", 1)[0]:
            u = "postgresql://" + u.split("://", 1)[1]
    return u


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(_BACKEND / ".env"),
            str(_ROOT / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Spixa"
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 7000
    secret_key: str = "change-me-in-production"

    # Default: local SQLite (no Docker). Override with Postgres when available.
    database_url: str = f"sqlite+aiosqlite:///{(_ROOT / 'data' / 'spixa.db').as_posix()}"
    database_url_sync: str = f"sqlite:///{(_ROOT / 'data' / 'spixa.db').as_posix()}"

    @field_validator("database_url", mode="before")
    @classmethod
    def _async_db_url(cls, v: object) -> object:
        if isinstance(v, str):
            return _normalize_database_url(v, async_driver=True)
        return v

    @field_validator("database_url_sync", mode="before")
    @classmethod
    def _sync_db_url(cls, v: object) -> object:
        if isinstance(v, str):
            return _normalize_database_url(v, async_driver=False)
        return v

    workspaces_root: Path = _ROOT / "data" / "workspaces"
    object_storage_endpoint: str = ""
    object_storage_bucket: str = "spixa"

    default_reasoning_model: str = "openai/gpt-4.1"
    default_coding_model: str = "openai/gpt-4.1"
    default_fast_model: str = "openai/gpt-4.1-mini"
    default_multimodal_model: str = "openai/gpt-4.1"
    default_embedding_model: str = "openai/text-embedding-3-small"
    default_critic_model: str = "anthropic/claude-sonnet-4.5"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    # Unified teacher upstream (preferred): one key → GPT/Claude/Gemini/Grok/…
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "https://spixa.local"
    openrouter_app_name: str = "Spixa"
    # openrouter = chat teachers; cursor = Cloud Agents API (coding teacher, async-ish)
    teacher_upstream: str = "openrouter"
    model_gateway_force_simulate: bool = False
    # Cursor Cloud Agents API (https://api.cursor.com) — optional coding teacher
    cursor_api_key: str = ""
    cursor_api_base_url: str = "https://api.cursor.com"
    cursor_default_repo_url: str = ""  # optional GitHub/GitLab URL for repo-bound runs
    cursor_poll_timeout_seconds: float = 180.0
    cursor_poll_interval_seconds: float = 3.0
    # Cloud/Railway: blank projects under WORKSPACES_ROOT (persistent volume) instead of Desktop
    cloud_workspaces: bool = False

    # Internal Intelligence First — external teachers only when quality gates demand
    prefer_internal: bool = True
    internal_intelligence_first: bool = True
    # When a specialty LoRA is promoted, keep traffic on owned students harder
    prefer_promoted_internal: bool = True
    promoted_no_escalate: bool = True  # skip teacher if promoted adapter + confident answer
    # Fast handoff: every verified chat/LTM outcome becomes student fuel immediately
    fast_handoff_enabled: bool = True
    # Phase 29: when specialty is handoff_ready, retire external teachers automatically
    auto_retire_ready_teachers: bool = True
    # Genius loop: absorb successes AND failures/errors/rejections
    learn_from_everything: bool = True
    # Autopilot (مساعد الطيار) — sandbox-only when user is away
    autopilot_enabled_default: bool = False
    autopilot_max_projects: int = 10
    autopilot_interval_seconds: int = 300  # background cycle while enabled
    autopilot_pause_on_manual_chat: bool = True
    internal_confidence_threshold: float = 0.55
    internal_model_base_url: str = ""  # OpenAI-compatible (vLLM/Ollama)
    internal_model_name: str = ""
    internal_model_api_key: str = ""
    # Smaller/faster model for held-out promote gates (falls back to internal_model_name)
    internal_eval_model_name: str = ""
    internal_eval_max_tokens: int = 256
    internal_eval_timeout_seconds: float = 120.0
    # Hard ceiling for interactive IDE/chat calls (Ollama can hang on large models).
    internal_chat_timeout_seconds: float = 90.0
    model_cache_enabled: bool = True
    model_cache_ttl_seconds: int = 3600
    distillation_enabled: bool = True
    distillation_data_root: Path = _ROOT / "data" / "distillation"

    # Eval + LoRA ownership track
    eval_data_root: Path = _ROOT / "data" / "eval"
    eval_min_student_score: float = 0.55
    eval_teacher_parity_ratio: float = 0.9
    training_artifacts_root: Path = _ROOT / "data" / "training"
    lora_min_examples: int = 3
    lora_rank: int = 8
    lora_real_train_enabled: bool = False
    lora_real_train_max_steps: int = 30
    lora_real_train_tiny_fallback: bool = True  # use tiny-gpt2 when base unavailable
    learning_data_root: Path = _ROOT / "data" / "learning"
    # Model Factory: eval pass → proposal only; human approve ships to production
    factory_require_human_approval: bool = True
    factory_regression_tolerance: float = 0.02  # allow tiny score noise vs prior approved

    # Chief Agent dynamic worker pool
    chief_enabled: bool = True
    chief_min_workers: int = 3
    chief_max_workers: int = 12
    chief_distill_outcomes: bool = True

    # Deploy adapters (human-gated; real cloud off by default)
    deploy_provider: str = "simulate"  # simulate | docker_local | azure_container_apps
    azure_deploy_enabled: bool = False
    azure_resource_group: str = ""
    azure_container_app_name: str = ""

    allow_untrusted_code_execution: bool = False
    sandbox_network_disabled: bool = True

    evolution_cron_enabled: bool = False
    notification_email_from: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    # Live alerts — Slack incoming webhook or generic JSON webhook
    notification_webhook_url: str = ""
    notification_webhook_on_urgent_only: bool = False
    # Super-admin email; also *@spixa.admin / *@evolve.admin in local/dev
    super_admin_email: str = "admin@spixa.admin"

    # Stripe Checkout (optional — without keys, billing uses local unlock for dev)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_team: str = ""
    stripe_price_enterprise: str = ""
    stripe_success_url: str = "http://localhost:3000/console?tab=billing&paid=1"
    stripe_cancel_url: str = "http://localhost:3000/console?tab=billing&paid=0"

    # SMS verification (Twilio or generic gateway)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    sms_gateway_url: str = ""
    sms_gateway_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
