"""
Zeus AI - Gerenciador de plugins
====================================
Descobre plugins registrados, decide (antes de acionar o LLM) se algum
deles deve tratar a mensagem do usuário — por exemplo, "que horas são?"
não precisa de uma chamada de LLM, um plugin local resolve mais rápido
e de forma determinística.
"""
from __future__ import annotations

from typing import Any, Optional

from backend.core.config import get_settings
from backend.core.logging_config import get_logger
from backend.plugins.base_plugin import ZeusPlugin
from backend.plugins.examples.datetime_plugin import DateTimePlugin
from backend.plugins.examples.reminder_plugin import ReminderPlugin
from backend.plugins.examples.weather_plugin import WeatherPlugin

settings = get_settings()
logger = get_logger("plugins.manager")


class PluginManager:
    def __init__(self) -> None:
        self._plugins: list[ZeusPlugin] = []
        if settings.PLUGINS_ENABLED:
            self._register_default_plugins()

    def _register_default_plugins(self) -> None:
        self.register(DateTimePlugin())
        self.register(WeatherPlugin())
        self.register(ReminderPlugin())

    def register(self, plugin: ZeusPlugin) -> None:
        self._plugins.append(plugin)
        logger.info("Plugin registrado: %s", plugin.name)

    def list_plugins(self) -> list[dict[str, str]]:
        return [{"name": p.name, "description": p.description} for p in self._plugins]

    def route(self, user_message: str, context: dict[str, Any]) -> Optional[str]:
        """Verifica se algum plugin deve tratar a mensagem. Retorna a
        resposta do primeiro plugin compatível, ou None se nenhum
        plugin se aplicar (nesse caso, o LLM assume a resposta)."""
        for plugin in self._plugins:
            try:
                if plugin.can_handle(user_message):
                    logger.info("Mensagem roteada para o plugin '%s'.", plugin.name)
                    return plugin.execute(user_message, context)
            except Exception as exc:  # noqa: BLE001
                logger.error("Erro no plugin '%s': %s", plugin.name, exc)
        return None


_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager
