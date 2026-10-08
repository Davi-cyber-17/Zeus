"""
Zeus AI - Base para plugins
================================
Todo plugin do Zeus herda de `ZeusPlugin` e implementa `can_handle` e
`execute`. Isso permite adicionar novas capacidades (clima, IoT,
automações, integrações externas) sem alterar o núcleo do sistema —
o requisito de "sistema de plugins ou extensões" do projeto.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ZeusPlugin(ABC):
    """Interface que toda extensão do Zeus deve implementar."""

    #: Nome único do plugin, usado em logs e no painel administrativo.
    name: str = "base_plugin"
    #: Descrição curta exibida no painel administrativo.
    description: str = ""

    @abstractmethod
    def can_handle(self, user_message: str) -> bool:
        """Retorna True se este plugin deve processar a mensagem."""
        raise NotImplementedError

    @abstractmethod
    def execute(self, user_message: str, context: dict[str, Any]) -> str:
        """Executa a ação do plugin e retorna uma resposta em texto."""
        raise NotImplementedError
