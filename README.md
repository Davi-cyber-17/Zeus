# ⚡ ZEUS — Assistente de Inteligência Artificial Pessoal

Zeus é um assistente de IA pessoal modular e seguro, inspirado no
conceito do J.A.R.V.I.S., mas com identidade, arquitetura e recursos
próprios. Compreende linguagem natural, fala e ouve (via navegador),
possui memória inteligente com busca por palavra-chave, aprende
preferências do usuário e é extensível através de um sistema de
plugins — tudo isso 100% local, sem Docker, sem modelos para baixar.

```
   ⚡ ZEUS
   ├── Compreensão de linguagem natural (LLM — API da Anthropic)
   ├── Voz: fala (TTS) e escuta (STT) via Web Speech API do navegador
   ├── Memória estruturada + busca por palavra-chave (100% SQLite)
   ├── Plugins/extensões
   ├── Painel administrativo
   └── Interface holográfica futurista
```

A única dependência externa do Zeus é a **API da Anthropic** (o
"cérebro" que gera as respostas) — precisa de internet e de uma chave
de API. Todo o resto roda localmente: banco de dados (SQLite puro),
busca de contexto (SQL/Python) e voz (Web Speech API, já embutida no
Chrome/Edge).

> **Changelog (revisão de segurança e novas funcionalidades)**
> - 🔒 Corrigido acesso indevido a conversas de outros usuários (IDOR)
>   em `GET /api/chat/conversations/{id}/messages`.
> - 🔒 Corrigido *path traversal* no upload de documentos (nome de
>   arquivo agora é sanitizado) + limite de tamanho (`MAX_UPLOAD_SIZE_MB`).
> - 🔒 `ALLOWED_ORIGINS` agora inclui a porta usada pelo próprio README
>   (`5500`), evitando erros de CORS "de fábrica".
> - 🔒 Corrigido XSS no frontend (`loadContext`/`loadPlugins` não usam
>   mais `innerHTML` com conteúdo dinâmico).
> - 🔒 Rate limiting em memória para login/registro; refresh tokens +
>   endpoint de troca de senha (`/api/auth/refresh`, `/api/auth/change-password`).
> - 🕒 Plugin de data/hora agora usa o fuso configurado (`TIMEZONE`), em
>   vez do horário local do servidor.
> - ✨ Streaming de respostas (`POST /api/chat/stream`, SSE).
> - ✨ Plugin e API de **lembretes** (`/api/reminders`, "lembre-me de...").
> - ✨ Telas de **Anotações**, **Documentos** e **Painel Admin** no
>   frontend (antes eram botões sem função).
> - ✨ Seletor de idioma funcional (PT-BR / EN-US / ES-ES), usado na voz
>   e na instrução de idioma enviada ao LLM.
> - ✨ Zeus agora funciona como **PWA** (instalável, com ícone e
>   funcionamento básico offline da interface).

---

## Sumário

1. [Arquitetura](#arquitetura)
2. [Estrutura de pastas](#estrutura-de-pastas)
3. [Pré-requisitos](#pré-requisitos)
4. [Instalação](#instalação)
5. [Configuração](#configuração)
6. [Executando o Zeus](#executando-o-zeus)
7. [Uso da API](#uso-da-api)
8. [Sistema de plugins](#sistema-de-plugins)
9. [Testes automatizados](#testes-automatizados)
10. [Roadmap / expansões futuras](#roadmap--expansões-futuras)
11. [Segurança](#segurança)

---

## Arquitetura

O Zeus segue uma arquitetura modular em camadas, permitindo evoluir ou
substituir qualquer peça (o LLM, o banco de dados) sem impactar as
demais:

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (HTML/CSS/JS)                │
│  Interface holográfica · Chat · Voz (Web Speech API) · Admin │
└───────────────────────────┬───────────────────────────────────┘
                            │ REST (JSON) + JWT
┌───────────────────────────▼───────────────────────────────────┐
│                     API (FastAPI) — backend/api                │
│      auth · chat · memory · documents · admin · plugins        │
└─────┬───────────┬─────────────┬──────────────┬─────────────────┘
      │           │             │              │
┌─────▼─────┐ ┌───▼────┐  ┌─────▼──────┐  ┌────▼─────┐
│  services  │ │ memory │  │  plugins   │  │    db    │
│ llm · docs │ │ palavra│  │ manager +  │  │ SQLAlchemy│
│            │ │ -chave │  │ extensões  │  │ (SQLite) │
└────────────┘ └────────┘  └────────────┘  └───────────┘
```

**Princípios de design:**
- **Modularidade** — cada capacidade (memória, LLM, plugins) é um
  módulo independente com uma interface clara, plugável e testável.
- **Simplicidade local-first** — nenhum modelo pesado para baixar, nenhum
  container para subir; só Python + SQLite + navegador.
- **Resiliência** — se a `LLM_API_KEY` não estiver configurada, o Zeus
  continua funcionando via um provedor de fallback (modo demonstração).
- **Segurança em camadas** — senhas com hashing bcrypt, autenticação via
  JWT, e dados sensíveis (anotações) criptografados em repouso.

---

## Estrutura de pastas

```
zeus_ai/
├── backend/
│   ├── main.py                  # ponto de entrada da API (FastAPI)
│   ├── core/
│   │   ├── config.py             # configurações centrais (.env)
│   │   ├── logging_config.py     # logs de sistema + auditoria
│   │   └── security.py           # JWT, hashing, criptografia
│   ├── db/
│   │   ├── database.py           # conexão SQLAlchemy (SQLite)
│   │   └── models.py             # usuários, conversas, docs, notas...
│   ├── memory/
│   │   └── memory_manager.py     # busca por palavra-chave (100% SQL)
│   ├── services/
│   │   ├── llm_service.py        # cérebro conversacional (Zeus Brain)
│   │   └── document_service.py   # extração/leitura de documentos
│   ├── plugins/
│   │   ├── base_plugin.py        # interface para novas extensões
│   │   ├── manager.py            # roteamento de mensagens a plugins
│   │   └── examples/             # plugins de exemplo (clima, data/hora, lembretes)
│   ├── api/routes/               # auth, chat, memory, documents,
│   │                              # admin, plugins, reminders
│   └── schemas/                  # contratos Pydantic da API
├── frontend/
│   ├── index.html                # interface holográfica (chat, anotações,
│   │                              # documentos, admin, troca de senha)
│   ├── styles.css                # identidade visual do Zeus
│   ├── app.js                    # chat (streaming), voz, painéis, PWA
│   ├── manifest.json             # manifesto do PWA
│   ├── sw.js                     # service worker (app shell offline)
│   └── icon.svg                  # ícone do app
├── tests/                        # testes automatizados (pytest)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Pré-requisitos

- **Python 3.11+**
- **pip** (ou [uv](https://github.com/astral-sh/uv), opcional)
- Um navegador moderno com suporte a Web Speech API (Chrome ou Edge, para
  usar voz — o chat por texto funciona em qualquer navegador)
- *(Opcional)* Chave de API da Anthropic — sem ela, o Zeus responde em
  modo demonstração (echo), ideal para primeiros testes

---

## Instalação

```bash
# 1. Clone ou copie o projeto
cd zeus_ai

# 2. Crie um ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Instale as dependências (tudo puro Python, sem downloads pesados)
pip install -r requirements.txt

# 4. Copie o arquivo de variáveis de ambiente
cp .env.example .env
```

---

## Configuração

Abra o arquivo `.env` e ajuste os valores necessários:

| Variável            | Descrição                                              | Padrão                     |
|---------------------|----------------------------------------------------------|-----------------------------|
| `SECRET_KEY`        | Chave usada para assinar tokens JWT e criptografar dados | **altere obrigatoriamente** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duração do token de acesso                     | `30`                         |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | Duração do refresh token                      | `43200` (30 dias)            |
| `ALLOWED_ORIGINS`   | Origens permitidas por CORS                              | inclui `localhost:5500`      |
| `RATE_LIMIT_ENABLED`| Ativa/desativa o limite de tentativas de login/registro  | `true`                       |
| `DATABASE_URL`      | String de conexão do banco de dados (SQLite)             | SQLite local                |
| `DOCS_DIR`          | Pasta onde os arquivos enviados são guardados             | `./data/documents`          |
| `MAX_UPLOAD_SIZE_MB`| Tamanho máximo de upload de documentos                    | `15`                        |
| `LLM_API_KEY`       | Chave de API da Anthropic                                | vazio (modo demonstração)   |
| `LLM_MODEL`         | Modelo de linguagem usado                                | `claude-sonnet-4-6`         |
| `DEFAULT_LANGUAGE`  | Idioma padrão da interface e da voz                       | `pt-BR`                     |
| `TIMEZONE`          | Fuso horário usado pelo plugin de data/hora               | `America/Sao_Paulo`         |

Gere uma `SECRET_KEY` segura com:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## Executando o Zeus

### Backend (API)

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

A API estará disponível em `http://localhost:8000`, com documentação
interativa (Swagger) em `http://localhost:8000/docs`.

### Frontend

A interface é composta por arquivos estáticos simples. Para desenvolvimento
rápido, basta servi-la com qualquer servidor HTTP:

```bash
cd frontend
python -m http.server 5500
```

Acesse `http://localhost:5500`. No primeiro acesso, clique em **Entrar** —
como ainda não há usuários, o sistema oferecerá criar uma conta (o primeiro
usuário cadastrado se torna administrador automaticamente). O botão de
microfone usa o reconhecimento de voz nativo do navegador (Web Speech API);
as respostas do Zeus também podem ser lidas em voz alta pelo navegador.

---

## Uso da API

### Autenticação

```bash
# Registro
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"tony","email":"tony@zeus.ai","password":"starkindustries"}'

# Login (retorna access_token)
curl -X POST http://localhost:8000/api/auth/login \
  -d "username=tony&password=starkindustries"
```

### Conversar com o Zeus

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Zeus, quais são minhas anotações mais recentes?"}'
```

### Enviar um documento para análise

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer SEU_TOKEN" \
  -F "file=@relatorio.pdf"
```

Consulte todos os endpoints (com exemplos de payload) na documentação
interativa em `/docs`.

> A voz (fala e escuta) não passa pela API — é feita inteiramente no
> navegador via Web Speech API, então não há endpoint de voz no backend.

---

## Sistema de plugins

O Zeus foi desenhado para crescer através de plugins, sem tocar no núcleo
do sistema. Um plugin é uma classe Python que decide, de forma
determinística, se deve tratar uma mensagem antes que ela chegue ao LLM.

```python
# backend/plugins/examples/meu_plugin.py
from backend.plugins.base_plugin import ZeusPlugin

class MeuPlugin(ZeusPlugin):
    name = "meu_plugin"
    description = "Descreva o que este plugin faz."

    def can_handle(self, user_message: str) -> bool:
        return "minha palavra-chave" in user_message.lower()

    def execute(self, user_message: str, context: dict) -> str:
        return "Resposta gerada pelo meu plugin."
```

Registre-o em `backend/plugins/manager.py`, dentro de
`_register_default_plugins`. Os plugins ativos aparecem automaticamente no
painel de contexto do frontend e no endpoint `/api/plugins`.

---

## Testes automatizados

```bash
pytest
# ou, com relatório de cobertura:
pytest --cov=backend
```

Os testes usam um banco SQLite em memória e o provedor de LLM de fallback
(sem chamadas externas), cobrindo autenticação, chat (incluindo roteamento
de plugins) e memória (anotações e preferências).

---

## Roadmap / expansões futuras

- [ ] Controle de dispositivos IoT (integração via MQTT/Home Assistant)
- [ ] Aplicativo desktop nativo (Electron) reaproveitando a API atual
- [ ] Suporte a múltiplos modelos de LLM simultâneos (roteamento por tarefa)
- [ ] Sincronização multi-dispositivo
- [ ] Painel administrativo com dashboards visuais (gráficos de uso)
- [ ] Busca semântica com embeddings (hoje é por palavra-chave)
- [ ] Integração com calendário (Google Calendar/CalDAV) para os lembretes
- [ ] Fluxo de recuperação de senha por e-mail (hoje só há troca de senha
      autenticada, em `/api/auth/change-password`)

A arquitetura modular do Zeus foi pensada exatamente para que cada um
desses itens possa ser adicionado como um novo módulo ou plugin, sem
reescrever o núcleo do sistema.

---

## Segurança

- Senhas armazenadas com **bcrypt** (nunca em texto plano).
- Sessões autenticadas via **JWT** (access token curto + refresh token),
  com `token_version` por usuário para revogar tokens antigos ao trocar
  a senha.
- Rate limiting em memória contra força bruta em login e registro.
- Upload de documentos com nome de arquivo sanitizado (sem *path
  traversal*) e limite de tamanho configurável.
- Cada conversa, documento, anotação e lembrete só pode ser acessado
  pelo próprio dono — nunca por outro usuário do sistema.
- Anotações do usuário criptografadas em repouso com **Fernet (AES-128)**.
- Toda ação relevante é registrada em log de auditoria
  (`data/logs/activity.log`).
- **Nunca** commit o arquivo `.env` — ele já está no `.gitignore`.
- Em produção, sempre troque `SECRET_KEY` e sirva a API atrás de HTTPS.

---

**Zeus** — pensado para crescer com você, um módulo de cada vez. ⚡
