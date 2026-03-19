# Resumen del Backend - MergeIntel API

## 1. Arquitectura General

El backend de MergeIntel está construido con **FastAPI** y sigue una arquitectura en capas:

```text
┌────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                       │
│                              main.py                              │
└────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│                             Routers                               │
│ /auth/*  /pr/*  /chat/*  /github/webhook                          │
└────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│                           Controllers                             │
│ Orquestan flujos, manejan errores y devuelven respuestas API      │
└────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│                            Services                               │
│ Auth, Session, GitHub, Analyzer, PR, Chat, Mail                   │
└────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────┬──────────────────────┬─────────────────────┐
│    Models (ORM)      │    Database (async)  │    Utils/Helpers    │
│    SQLAlchemy        │ PostgreSQL/asyncpg   │ security, text, tz  │
└──────────────────────┴──────────────────────┴─────────────────────┘
```

### Stack tecnológico

- **Framework:** FastAPI
- **ORM:** SQLAlchemy async
- **Base de datos:** PostgreSQL + asyncpg
- **Migraciones:** Alembic
- **Validación:** Pydantic
- **Integración GitHub:** GitHub REST API v3 con `httpx`
- **IA:** provider unificado con soporte para `groq`, `anthropic`, `openai` y `ollama`
- **Email:** fastapi-mail en desarrollo / Resend en producción

---

## 2. Estructura de Carpetas

```text
backend/
├── main.py
├── config.py
├── dependencies.py
├── exceptions.py
├── logging_config.py
├── timezone.py
│
├── routers/
│   ├── authentication.py
│   ├── pr.py
│   ├── chat.py
│   └── github.py
│
├── controllers/
│   ├── decorators.py
│   ├── authentication.py
│   ├── pr.py
│   ├── chat.py
│   └── github.py
│
├── services/
│   ├── authentication.py
│   ├── session.py
│   ├── pr.py
│   ├── chat.py
│   ├── github_webhook.py
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── factory.py
│   │   └── providers.py
│   ├── analyzer/
│   │   ├── __init__.py
│   │   ├── chat.py
│   │   ├── helpers.py
│   │   ├── prompts.py
│   │   ├── risk.py
│   │   ├── schema.py
│   │   ├── scope.py
│   │   └── summary.py
│   ├── github/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── client.py
│   │   ├── exceptions.py
│   │   ├── parsers.py
│   │   ├── pull_requests.py
│   │   └── types.py
│   └── mail/
│       ├── __init__.py
│       ├── base.py
│       ├── factory.py
│       ├── providers.py
│       ├── schemas.py
│       └── templates.py
│
├── models/
│   ├── __init__.py
│   ├── base.py
│   ├── user.py
│   ├── session.py
│   ├── pr_analysis.py
│   └── chat.py
│
├── schemas/
│   ├── base.py
│   ├── user_managment.py
│   ├── pr.py
│   └── chat.py
│
├── db/
│   ├── __init__.py
│   ├── connection.py
│   └── queries.py
│
├── utils/
│   ├── security.py
│   └── text.py
│
└── templates/
    └── welcome.html
```

---

## 3. Endpoints

### Health

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Estado del servicio |

### Autenticación y sesión

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/auth/user/new` | Crear usuario local |
| `POST` | `/auth/login` | Iniciar sesión con email y contraseña |
| `GET` | `/auth/me` | Obtener usuario autenticado desde cookie de sesión |
| `POST` | `/auth/logout` | Cerrar sesión actual |
| `GET` | `/auth/github/start` | Generar URL de inicio OAuth con GitHub |
| `GET` | `/auth/github/callback` | Callback OAuth de GitHub |

#### `GET /auth/github/start`

- `mode=create`: registro con GitHub
- `mode=login`: login con una cuenta GitHub ya enlazada
- `mode=link`: enlazar GitHub a un usuario autenticado

### Análisis de PR

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/pr/analyze` | Ejecutar análisis completo de un PR |
| `GET` | `/pr/history` | Listar análisis del usuario autenticado |
| `GET` | `/pr/{analysis_id}` | Obtener análisis completo |
| `GET` | `/pr/{analysis_id}/checklist` | Obtener checklist del análisis |
| `DELETE` | `/pr/{analysis_id}` | Eliminar análisis |

### Chat contextual

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/chat/{analysis_id}/message` | Enviar mensaje sobre un PR analizado |
| `GET` | `/chat/{analysis_id}/history` | Recuperar historial del chat |
| `DELETE` | `/chat/{analysis_id}` | Limpiar historial del chat |

### GitHub Webhook

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/github/webhook` | Procesar eventos `pull_request` de GitHub |

---

## 4. Servicios Disponibles

### UserService (`services/authentication.py`)

Responsabilidades principales:

- crear usuarios locales
- autenticar usuarios con email/contraseña
- crear usuarios con GitHub
- iniciar sesión con GitHub sobre cuentas ya enlazadas
- enlazar cuentas GitHub existentes
- intercambiar OAuth code por token
- resolver identidad GitHub y refrescar token cifrado

Métodos relevantes:

- `create_user(data)`
- `authenticate_user(data)`
- `get_user_by_email(email)`
- `get_user_by_id(user_id)`
- `create_user_with_github(data)`
- `authenticate_with_github(data)`
- `link_github_account(user_id, data)`

### SessionService (`services/session.py`)

Responsabilidades:

- crear sesiones persistidas en DB
- revocar una sesión actual
- revocar todas las sesiones de un usuario

Métodos:

- `create_session(user)`
- `revoke_session(session_token)`
- `revoke_user_sessions(user_id)`

### GitHub Services (`services/github/`)

#### GitHubClient

Cliente HTTP reutilizable para:

- OAuth token exchange
- `/user`
- `/user/emails`
- `/repos/{owner}/{repo}/pulls/{number}`
- `/pulls/{number}/commits`
- `/commits/{sha}`
- `/compare/{base}...{head}`

Maneja:

- token inválido
- permisos insuficientes
- rate limit
- repositorio inexistente
- PR inexistente

#### PullRequestService

Construye un `PRAnalysisInput` unificado con:

- metadata del PR
- commits
- autores
- archivos modificados
- patches truncados
- divergencia de rama

#### Helpers adicionales

- `parse_pull_request_reference(...)`
- `truncate_patch(...)`
- `get_github_access_token_for_user(...)`

### Analyzer Services (`services/analyzer/`)

#### `schema.py`

Detecta:

- migraciones Alembic
- cambios en modelos ORM
- cambios `.sql`
- advertencias de modelos sin migración

#### `scope.py`

Evalúa:

- scope explícito por autor si el request trae `author_scopes`
- scope inferido básico si no hay definición previa

#### `risk.py`

Calcula riesgo usando:

- divergencia
- cantidad de archivos
- cambios de schema
- advertencias de migración
- archivos fuera de scope

#### `summary.py`

Genera el resumen del PR usando la capa unificada de IA.

#### `chat.py`

Genera respuestas contextuales sobre un análisis persistido.

### PRService (`services/pr.py`)

Pipeline completo:

1. parsea referencia del PR
2. obtiene datos desde GitHub
3. corre análisis estático
4. genera checklist
5. llama al resumen con IA
6. persiste autores, commits, archivos, checklist y resumen

Además:

- lista historial
- recupera análisis por ID
- elimina análisis

### ChatService (`services/chat.py`)

- crea o reutiliza `ChatSession`
- persiste `ChatMessage`
- reconstruye contexto desde `PRAnalysis`
- responde vía provider IA
- devuelve historial serializado

### GitHubWebhook helpers (`services/github_webhook.py`)

- valida firma `X-Hub-Signature-256`
- resuelve usuario dueño del análisis
- reutiliza el pipeline de `PRService`

### MailService (`services/mail/`)

Se mantiene igual:

- `FastAPIMailService` para desarrollo
- `ResendMailService` para producción

---

## 5. Controladores

### UserController

Expone:

- `create_user`
- `login`
- `get_current_user_data`
- `logout`
- `create_session_for_user`
- `create_user_with_github`
- `login_with_github`
- `link_github_account`

### PRController

Expone:

- `analyze`
- `get_analysis`
- `get_checklist`
- `list_history`
- `delete_analysis`

### ChatController

Expone:

- `send_message`
- `get_history`
- `clear_history`

### GitHubWebhookController

Expone:

- `handle_pull_request_event`

Todos los controladores usan `@handle_controller_errors`.

---

## 6. Modelos ORM

### BaseModel (`models/base.py`)

Campos comunes:

- `id`
- `is_active`
- `created_at`
- `updated_at`

### User y OAuthAccount (`models/user.py`)

`User`:

- `name`
- `email`
- `password`
- `role`
- `status`
- relaciones a `oauth_accounts`, `sessions`, `pr_analyses`, `chat_sessions`

`OAuthAccount`:

- `user_id`
- `provider`
- `provider_user_id`
- `provider_login`
- `access_token`

Nota:

- `access_token` se guarda cifrado en reposo

### UserSession (`models/session.py`)

- `user_id`
- `token_hash`
- `expires_at`
- `last_seen_at`

### PRAnalysis (`models/pr_analysis.py`)

- `user_id`
- `repo_full_name`
- `pr_number`
- `pr_title`
- `pr_url`
- `base_branch`
- `head_branch`
- `status`
- `summary_text`
- `summary_payload`
- `risk_score`
- `divergence_days`
- `error_message`

### PRAnalysisAuthor

- `analysis_id`
- `github_login`
- `name`
- `email`
- `commit_count`
- `additions`
- `deletions`
- `inferred_scope`
- `scope_confidence`

### PRAnalysisCommit

- `analysis_id`
- `author_id`
- `sha`
- `message`
- `committed_at`
- `additions`
- `deletions`

### PRAnalysisFile

- `analysis_id`
- `author_id`
- `commit_id`
- `path`
- `change_type`
- `additions`
- `deletions`
- `patch`
- `patch_truncated`
- `is_schema_change`
- `out_of_scope`
- `scope_reason`

### PRChecklistItem

- `analysis_id`
- `title`
- `details`
- `severity`
- `completed`

### ChatSession y ChatMessage (`models/chat.py`)

`ChatSession`:

- `analysis_id`
- `user_id`

`ChatMessage`:

- `session_id`
- `role`
- `content`
- `token_count`

---

## 7. Esquemas Pydantic

### Base (`schemas/base.py`)

- `BaseResponse`
- `SucessWithData`
- `ErrorResponse`

### User Management (`schemas/user_managment.py`)

- `CurrentUser`
- `CreateUserRequest`
- `GitHubOAuthRequest`
- `LoginRequest`

### PR (`schemas/pr.py`)

- `AnalyzePRRequest`
- `ChecklistItemResponse`
- `AuthorSummaryResponse`
- `FileSummaryResponse`
- `CommitSummaryResponse`
- `PRAnalysisResponse`
- `PRHistoryItem`

### Chat (`schemas/chat.py`)

- `ChatRequest`
- `ChatMessageResponse`
- `ChatResponse`
- `ChatHistoryResponse`

---

## 8. Dependencias (`dependencies.py`)

| Función | Retorno | Uso |
|---------|---------|-----|
| `get_settings()` | `Settings` | Configuración |
| `get_db_session()` | `AsyncIterator[AsyncSession]` | Sesión DB por request |
| `get_mail_service()` | `MailService` | Servicio de correo |
| `get_ai_provider_client()` | `AsyncIterator[AIProviderClient]` | Cliente IA unificado |
| `get_current_user()` | `CurrentUser` | Usuario autenticado desde cookie |
| `get_optional_current_user()` | `CurrentUser \| None` | Usuario autenticado opcional |
| `get_github_client()` | `AsyncIterator[GitHubClient]` | Cliente GitHub del usuario autenticado |

La autenticación se resuelve con la cookie `mergeintel_session`.

---

## 9. Configuración (`config.py`)

Variables principales:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `GITHUB_CLIENT_ID` | OAuth GitHub | - |
| `GITHUB_CLIENT_SECRET` | OAuth GitHub | - |
| `GITHUB_WEBHOOK_SECRET` | Firma del webhook | - |
| `GITHUB_API_BASE_URL` | Base URL de GitHub API | `https://api.github.com` |
| `GITHUB_TOKEN_ENCRYPTION_KEY` | Clave para cifrar tokens GitHub | - |
| `AI_PROVIDER` | `groq \| anthropic \| openai \| ollama` | `groq` |
| `AI_PROVIDER_API_KEY` | API key del provider | - |
| `AI_MODEL` | Modelo por provider | opcional |
| `DATABASE_URL` | URL PostgreSQL | requerido |
| `APP_ENV` | Entorno | `development` |
| `APP_PORT` | Puerto | `8000` |
| `APP_TIMEZONE` | Zona horaria | `America/Argentina/Buenos_Aires` |
| `MAIL_*` | Config email | ver `config.py` |
| `RESEND_API_KEY` | Resend en producción | - |
| `LOG_*` | Logging | ver `config.py` |

Validaciones relevantes:

- `AI_PROVIDER` debe ser soportado
- `GITHUB_TOKEN_ENCRYPTION_KEY` es obligatoria si GitHub OAuth está activo

---

## 10. Seguridad (`utils/security.py`)

Helpers disponibles:

- `hash_string(value)`
- `verify_string(value, hashed_value)`
- `hash_token(value)`
- `verify_token(value, hashed_value)`
- `generate_opaque_token()`
- `encrypt_secret(value, secret_key)`
- `decrypt_secret(value, secret_key)`

Uso:

- passwords: bcrypt + prehash SHA-256
- sesiones: token opaco + hash persistido
- GitHub token: cifrado reversible en DB

---

## 11. Base de Datos y Migraciones

### Conexión (`db/connection.py`)

- engine async SQLAlchemy
- `async_sessionmaker`
- inicialización en lifespan
- cierre de engine al shutdown

### Queries (`db/queries.py`)

Helpers raw SQL:

- `fetch_one`
- `fetch_all`
- `execute`
- `execute_many`

### Alembic

Migraciones actuales cubren:

- `user`
- `OAuthAccount`
- `user_session`
- `pr_analysis`
- `pr_analysis_author`
- `pr_analysis_commit`
- `pr_analysis_file`
- `pr_checklist_item`
- `chat_session`
- `chat_message`

---

## 12. Logging y Manejo de Errores

### AppError (`exceptions.py`)

Contiene:

- `message`
- `err_code`
- `status_code`

### handle_controller_errors

Maneja:

- `AppError`
- `IntegrityError`
- excepciones genéricas

### Logging (`logging_config.py`)

Soporta:

- formato `json`
- formato `text`
- handler stdout
- handler file rotativo

---

## 13. Middleware y Lifespan

### CORS

- `allow_origins=["http://localhost:5173"]`
- `allow_credentials=True`
- `allow_methods=["*"]`
- `allow_headers=["*"]`

### Exception handlers en `main.py`

- `AppError` -> respuesta estructurada
- excepción no controlada -> `500 Internal server error`

### Startup / Shutdown

1. configura logging
2. construye mail service
3. inicializa session factory
4. deja Mailpit visible en desarrollo
5. cierra engine al apagar

---

## 14. Estado actual del backend

El backend ya implementa:

- autenticación local con sesión persistida
- registro, login, logout y `/auth/me`
- OAuth GitHub para create, login y link
- cifrado de token GitHub en base de datos
- cliente GitHub reusable
- análisis completo de PR con persistencia
- checklist y score de riesgo
- chat contextual por análisis
- webhook de GitHub para `pull_request`
- capa unificada de IA con soporte para `groq`
