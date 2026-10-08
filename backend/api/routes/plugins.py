"""Zeus AI - Rotas de plugins: listagem das extensões ativas."""
from fastapi import APIRouter, Depends

from backend.api.deps import get_current_user
from backend.db import models
from backend.plugins.manager import get_plugin_manager

router = APIRouter(prefix="/api/plugins", tags=["Plugins"])


@router.get("")
def list_plugins(user: models.User = Depends(get_current_user)):
    return get_plugin_manager().list_plugins()
