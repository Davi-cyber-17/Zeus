"""
Plugin de exemplo: integração com API externa de clima (Open-Meteo).
Demonstra como o Zeus pode se conectar a serviços externos através do
sistema de plugins, sem acoplar essa lógica ao núcleo do sistema.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from backend.core.logging_config import get_logger
from backend.plugins.base_plugin import ZeusPlugin

logger = get_logger("plugins.weather")
_PATTERN = re.compile(r"\b(clima|tempo hoje|weather|previsão)\b", re.I)


class WeatherPlugin(ZeusPlugin):
    name = "weather"
    description = "Consulta a previsão do tempo atual via Open-Meteo (API pública gratuita)."

    def can_handle(self, user_message: str) -> bool:
        return bool(_PATTERN.search(user_message))

    def execute(self, user_message: str, context: dict[str, Any]) -> str:
        # Coordenadas padrão (podem vir das preferências do usuário no futuro).
        lat = context.get("latitude", -23.55)
        lon = context.get("longitude", -46.63)
        try:
            response = httpx.get(
                "https://api.open-meteo.com/v1/forecast",
                params={"latitude": lat, "longitude": lon, "current_weather": True},
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json().get("current_weather", {})
            temp = data.get("temperature")
            wind = data.get("windspeed")
            return f"A temperatura atual é {temp}°C, com vento de {wind} km/h."
        except Exception as exc:  # noqa: BLE001
            logger.error("Erro ao consultar API de clima: %s", exc)
            return "Não consegui consultar o clima agora. Tente novamente em instantes."
