"""Pydantic-Settings configuration. All env-driven; no literals in code."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    PUBLIC_BASE_URL: str = "http://localhost:8080"
    LOG_LEVEL: str = "INFO"
    PREFLIGHT_MODE: int = 0

    # LLM provider toggle: groq | nearai. Both serve openai/gpt-oss-120b.
    # 'nearai' routes investigation memos through NEAR AI Cloud's TEE-attested
    # OpenAI-compatible endpoint (Intel TDX + NVIDIA H200 confidential compute,
    # per-request cryptographic attestation). 'groq' is the original Groq path.
    LLM_PROVIDER: str = "groq"

    # Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TIMEOUT_SECONDS: int = 30

    # NEAR AI Cloud (TEE-attested confidential AI)
    NEAR_AI_API_KEY: str = ""
    NEAR_AI_BASE_URL: str = "https://cloud-api.near.ai/v1"
    NEAR_AI_MODEL: str = "openai/gpt-oss-120b"
    NEAR_AI_TIMEOUT_SECONDS: int = 30

    # Postgres
    POSTGRES_URL: str = "postgresql+asyncpg://hawkeye:hawkeye_dev_change_me@postgres:5432/hawkeye"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Neo4j
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASS: str = "hawkeye_neo4j_change_me"

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_TOPIC_EVENTS: str = "hawkeye.events"
    KAFKA_CONSUMER_GROUP: str = "hawkeye-scorer"

    # Keycloak
    KEYCLOAK_URL: str = "http://keycloak:8080"
    KEYCLOAK_REALM: str = "hawkeye"
    KEYCLOAK_CLIENT_ID: str = "hawkeye-frontend"
    KEYCLOAK_BACKEND_CLIENT_ID: str = "hawkeye-backend"
    KEYCLOAK_BACKEND_CLIENT_SECRET: str = ""

    # Artifacts & data
    ARTIFACTS_DIR: str = "artifacts"
    DATA_DIR: str = "data"

    # Scoring
    SCORE_THRESHOLD: float = 0.16032509001471132
    ALERT_DEDUP_WINDOW_MINUTES: int = 60
    ALERT_DEDUP_DELTA: float = 0.05

    # Replay
    REPLAY_DEFAULT_RATE: int = 500
    REPLAY_MAX_RATE: int = 5000

    @property
    def artifacts_path(self) -> Path:
        return Path(self.ARTIFACTS_DIR)

    @property
    def data_path(self) -> Path:
        return Path(self.DATA_DIR)

    @property
    def is_preflight_mode(self) -> bool:
        return bool(self.PREFLIGHT_MODE)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
