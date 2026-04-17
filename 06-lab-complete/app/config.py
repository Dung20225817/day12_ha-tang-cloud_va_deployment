"""Production config using environment variables only (12-factor style)."""
import logging
import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    # App
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "Production AI Agent"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Security
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", "dev-key-change-me"))
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
            if origin.strip()
        ]
    )
    admin_user_ids: list[str] = field(
        default_factory=lambda: [
            user.strip()
            for user in os.getenv("ADMIN_USER_IDS", "admin").split(",")
            if user.strip()
        ]
    )

    # LLM
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))

    # Rate limiting and budget
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    )
    monthly_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("MONTHLY_BUDGET_USD", "10.0"))
    )

    # Stateless storage
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    history_max_messages: int = field(
        default_factory=lambda: int(os.getenv("HISTORY_MAX_MESSAGES", "20"))
    )
    history_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("HISTORY_TTL_SECONDS", str(30 * 24 * 3600)))
    )

    def validate(self):
        logger = logging.getLogger(__name__)
        if self.environment == "production" and self.agent_api_key == "dev-key-change-me":
            raise ValueError("AGENT_API_KEY must be changed in production")
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not set, mock LLM will be used")
        return self


settings = Settings().validate()
