"""
Zeus AI - Ponto de entrada
==============================
Inicializa a aplicação FastAPI: configura CORS, logging, banco de
dados e registra todas as rotas modulares. Execute com:

    uvicorn backend.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import admin, auth, chat, documents, memory, plugins, reminders
from backend.core.config import get_settings
from backend.core.logging_config import get_logger, setup_logging
from backend.db.database import init_db

settings = get_settings()
setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando %s v%s (%s)...", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    if settings.SECRET_KEY == "CHANGE_ME_IN_PRODUCTION":
        logger.warning(
            "SECRET_KEY ainda está com o valor padrão! Gere uma chave própria "
            "(veja o README) antes de expor o Zeus fora da sua máquina."
        )
    init_db()
    logger.info("Banco de dados pronto. Zeus está online.")
    yield
    logger.info("Encerrando o Zeus. Até logo.")


app = FastAPI(
    title="Zeus AI",
    description="Assistente de inteligência artificial pessoal, modular e seguro.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(memory.router)
app.include_router(documents.router)
app.include_router(admin.router)
app.include_router(plugins.router)
app.include_router(reminders.router)


@app.get("/api/health", tags=["Sistema"])
def health_check() -> dict[str, str]:
    """Endpoint de verificação de saúde do sistema (usado por monitoramento)."""
    return {"status": "online", "app": settings.APP_NAME, "version": settings.APP_VERSION}
