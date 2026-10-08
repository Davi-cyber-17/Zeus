"""
Zeus AI - Serviço de linguagem (LLM)
========================================
Camada de abstração sobre o provedor de modelo de linguagem. Hoje usa a
API da Anthropic, mas a interface `LLMProvider` permite plugar outro
provedor (OpenAI, modelo local, etc.) sem alterar o restante do sistema
— um dos pilares de modularidade do Zeus.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, Optional

from backend.core.config import get_settings
from backend.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("services.llm")


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        ...

    def generate_stream(self, system_prompt: str, messages: list[dict[str, str]]) -> Iterator[str]:
        """Gera a resposta em pedaços (streaming). A implementação padrão
        apenas chama `generate` e devolve tudo de uma vez — provedores que
        suportam streaming de verdade (ex.: Anthropic) devem sobrescrever
        este método."""
        yield self.generate(system_prompt, messages)


class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        import anthropic

        self.client = anthropic.Anthropic(api_key=settings.LLM_API_KEY)

    def generate(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        response = self.client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            system=system_prompt,
            messages=messages,
        )
        return "".join(block.text for block in response.content if block.type == "text")

    def generate_stream(self, system_prompt: str, messages: list[dict[str, str]]) -> Iterator[str]:
        with self.client.messages.stream(
            model=settings.LLM_MODEL,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            system=system_prompt,
            messages=messages,
        ) as stream:
            yield from stream.text_stream


class EchoFallbackProvider(LLMProvider):
    """Usado quando nenhuma API key está configurada — evita que o sistema
    quebre em ambiente de desenvolvimento/demonstração sem credenciais."""

    def generate(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return (
            "[Zeus - modo demonstração, sem LLM_API_KEY configurada]\n"
            f"Recebi sua mensagem: \"{last_user_msg}\". "
            "Configure LLM_API_KEY no .env para respostas inteligentes reais."
        )

    def generate_stream(self, system_prompt: str, messages: list[dict[str, str]]) -> Iterator[str]:
        # Simula streaming palavra a palavra, só para o frontend poder usar
        # o mesmo código de renderização incremental em modo demonstração.
        text = self.generate(system_prompt, messages)
        words = text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")


def _build_provider() -> LLMProvider:
    if not settings.LLM_API_KEY:
        logger.warning("LLM_API_KEY não configurada — usando provedor de fallback (echo).")
        return EchoFallbackProvider()
    try:
        if settings.LLM_PROVIDER == "anthropic":
            return AnthropicProvider()
        raise NotImplementedError(f"Provedor '{settings.LLM_PROVIDER}' ainda não implementado.")
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha ao inicializar provedor LLM (%s). Usando fallback.", exc)
        return EchoFallbackProvider()


_LANGUAGE_NAMES = {
    "pt-BR": "português do Brasil",
    "en-US": "inglês (Estados Unidos)",
    "es-ES": "espanhol",
}


class ZeusBrain:
    """Ponto único de acesso à inteligência conversacional do Zeus."""

    def __init__(self) -> None:
        self.provider = _build_provider()

    def _build_system_prompt(
        self, memory_context: str, language: Optional[str], extra_system_instructions: Optional[str]
    ) -> str:
        system_prompt = settings.ZEUS_SYSTEM_PROMPT
        if language:
            language_name = _LANGUAGE_NAMES.get(language, language)
            system_prompt += f"\n\nResponda sempre em {language_name}, independentemente do idioma da pergunta."
        if memory_context:
            system_prompt += f"\n\n{memory_context}"
        if extra_system_instructions:
            system_prompt += f"\n\n{extra_system_instructions}"
        return system_prompt

    def think(
        self,
        user_message: str,
        history: list[dict[str, str]],
        memory_context: str = "",
        language: Optional[str] = None,
        extra_system_instructions: Optional[str] = None,
    ) -> str:
        system_prompt = self._build_system_prompt(memory_context, language, extra_system_instructions)
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": user_message})

        logger.info("Gerando resposta (%d mensagens de histórico).", len(history))
        return self.provider.generate(system_prompt=system_prompt, messages=messages)

    def think_stream(
        self,
        user_message: str,
        history: list[dict[str, str]],
        memory_context: str = "",
        language: Optional[str] = None,
        extra_system_instructions: Optional[str] = None,
    ) -> Iterator[str]:
        system_prompt = self._build_system_prompt(memory_context, language, extra_system_instructions)
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": user_message})

        logger.info("Gerando resposta em streaming (%d mensagens de histórico).", len(history))
        yield from self.provider.generate_stream(system_prompt=system_prompt, messages=messages)


_brain: Optional[ZeusBrain] = None


def get_brain() -> ZeusBrain:
    global _brain
    if _brain is None:
        _brain = ZeusBrain()
    return _brain
