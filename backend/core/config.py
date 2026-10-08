"""
Zeus AI - Configurações centrais
=================================
Carrega e valida todas as configurações do sistema a partir de variáveis
de ambiente (.env), usando Pydantic Settings para validação em tempo de
inicialização. Nenhum outro módulo deve ler os.environ diretamente —
tudo passa por aqui.
"""
from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Identidade do sistema ---------------------------------------
    APP_NAME: str = "Zeus"
    APP_VERSION: str = "1.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True

    # --- Segurança ------------------------------------------------------
    SECRET_KEY: str = Field(default="CHANGE_ME_IN_PRODUCTION")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # token de acesso de curta duração
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # refresh token de 30 dias
    # Origens padrão cobrindo os jeitos mais comuns de servir o frontend
    # localmente (arquivo estático servido por `python -m http.server` nas
    # portas mais usadas, e o próprio host do backend).
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ]

    # --- Rate limiting (proteção simples contra força bruta) --------------
    # Implementado em memória (sem Redis/serviço externo), adequado para uso
    # pessoal/local. Em produção com múltiplos workers, prefira um backend
    # compartilhado (ex.: Redis).
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    REGISTER_RATE_LIMIT_ATTEMPTS: int = 10
    REGISTER_RATE_LIMIT_WINDOW_SECONDS: int = 3600

    # --- Banco de dados relacional ---------------------------------------
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'zeus.db'}"

    # --- Documentos enviados pelo usuário ---------------------------------
    # O texto completo de cada documento é extraído e guardado no próprio
    # SQLite (campo Document.content), permitindo busca por palavra-chave
    # sem depender de nenhum serviço externo.
    DOCS_DIR: str = str(BASE_DIR / "data" / "documents")
    MAX_UPLOAD_SIZE_MB: int = 15

    # --- Modelo de linguagem (LLM) ---------------------------------------
    LLM_PROVIDER: Literal["anthropic", "openai", "local"] = "anthropic"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "claude-sonnet-4-6"
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.6
    ZEUS_SYSTEM_PROMPT: str = (
        "Você é Zeus, um assistente de inteligência artificial pessoal. "
        "Seja preciso, proativo e conciso. Use o contexto de memória fornecido "
        "quando relevante. Responda no idioma em que o usuário falar."
    )

    # --- Voz (STT / TTS) ---------------------------------------------------
    # A fala/escuta é feita 100% pelo navegador via Web Speech API (já
    # embutida no Chrome/Edge), então não há nenhuma configuração de
    # motor de voz no backend — zero downloads, zero dependências.

    # --- Idiomas suportados -----------------------------------------------
    DEFAULT_LANGUAGE: str = "pt-BR"
    SUPPORTED_LANGUAGES: List[str] = ["pt-BR", "en-US", "es-ES"]

    # --- Fuso horário --------------------------------------------------
    # Usado pelos plugins (ex.: data/hora) para responder com o horário
    # correto independentemente de onde o servidor esteja hospedado.
    TIMEZONE: str = "America/Sao_Paulo"

    # --- Logs -----------------------------------------------------------
    LOG_DIR: str = str(BASE_DIR / "data" / "logs")
    LOG_LEVEL: str = "INFO"

    # --- Plugins ----------------------------------------------------------
    PLUGINS_ENABLED: bool = True

    def ensure_directories(self) -> None:
        """Garante que os diretórios de dados existam antes do boot."""
        for path in [
            Path(self.DATABASE_URL.replace("sqlite:///", "")).parent,
            Path(self.DOCS_DIR),
            Path(self.LOG_DIR),
        ]:
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância única (singleton) de configurações."""
    settings = Settings()
    settings.ensure_directories()
    return settings
