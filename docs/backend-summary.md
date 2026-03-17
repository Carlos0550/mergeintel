# Resumen del Backend - MergeIntel API

## 1. Arquitectura General

El backend de MergeIntel está construido con **FastAPI** siguiendo una arquitectura en capas:

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                       │
│                         (main.py)                                │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Routers (API)                            │
│              /auth/* - Autenticación y gestión de usuarios        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Controllers                                  │
│         Orquestan la lógica, manejan errores, formatean respuestas│
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Services                                    │
│    Lógica de negocio: UserService, MailService (providers)         │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────┬──────────────────────┬────────────────────┐
│   Models (ORM)       │   Database (async)    │   Utils/Helpers     │
│   SQLAlchemy         │   PostgreSQL/asyncpg  │   security, text    │
└──────────────────────┴──────────────────────┴────────────────────┘
```

**Stack tecnológico:**
- **Framework:** FastAPI
- **ORM:** SQLAlchemy (async)
- **Base de datos:** PostgreSQL (asyncpg)
- **Migraciones:** Alembic
- **Validación:** Pydantic
- **Email:** fastapi-mail (dev) / Resend (producción)

---

## 2. Estructura de Carpetas

```
backend/
├── main.py                 # Punto de entrada FastAPI
├── config.py               # Configuración (Settings desde .env)
├── dependencies.py         # Inyección de dependencias FastAPI
├── exceptions.py           # Excepciones de aplicación (AppError)
├── logging_config.py       # Configuración centralizada de logs
├── timezone.py             # Helpers de zona horaria
│
├── routers/                # Definición de endpoints
│   ├── __init__.py
│   └── authentication.py   # Rutas de autenticación
│
├── controllers/            # Capa de orquestación
│   ├── decorators.py       # @handle_controller_errors
│   └── authentication.py   # UserController
│
├── services/               # Lógica de negocio
│   ├── authentication.py   # UserService (crear usuario, GitHub OAuth)
│   └── mail/               # Servicio de correo
│       ├── __init__.py
│       ├── base.py         # MailService (abstracto), MailDeliveryError
│       ├── factory.py     # build_mail_service, validate_mail_settings
│       ├── providers.py   # FastAPIMailService, ResendMailService
│       ├── schemas.py     # EmailPayload
│       └── templates.py   # render_html_template (Jinja2)
│
├── models/                 # Modelos ORM SQLAlchemy
│   ├── __init__.py
│   ├── base.py            # Base, BaseModel (id, timestamps, is_active)
│   └── user.py            # User, OAuthAccount, enums (UserRole, UserStatus, OauthProviders)
│
├── schemas/                # Esquemas Pydantic (request/response)
│   ├── base.py            # BaseResponse, SucessWithData, ErrorResponse
│   └── user_managment.py  # CreateUserRequest, GitHubOAuthRequest, CurrentUser
│
├── db/                     # Acceso a datos
│   ├── __init__.py
│   ├── connection.py      # create_session_factory, close_engine, get_session_factory
│   └── queries.py        # fetch_one, fetch_all, execute (raw SQL helpers)
│
├── utils/                  # Utilidades
│   ├── security.py        # hash_string, verify_string (bcrypt)
│   └── text.py            # capitalize_words
│
└── templates/              # Plantillas HTML (emails)
    └── welcome.html
```

---

## 3. Endpoints (API)

### Health

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/health` | Estado del servicio |

**Respuesta:** `{ "status": "ok", "environment": "<APP_ENV>" }`

---

### Autenticación (`/auth`)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/auth/user/new` | Crear usuario (email + contraseña) |
| `GET` | `/auth/github/start` | Iniciar OAuth con GitHub |
| `GET` | `/auth/github/callback` | Callback de GitHub OAuth |

#### Detalle de endpoints

**`POST /auth/user/new`**
- **Body:** `CreateUserRequest` → `{ name, email, password }`
- **Respuestas:** 200 (éxito), 400 (validación), 409 (email duplicado)

**`GET /auth/github/start`**
- **Query params:** `mode` (create | link), `user_id` (UUID, solo si mode=link)
- **Respuesta:** `{ authorization_url, redirect_uri, state, mode }`

**`GET /auth/github/callback`**
- **Query params:** `code`, `state`, `error`, `error_description`
- **Respuestas:** 200 (éxito), 400 (error GitHub), 404 (usuario no encontrado), 409 (conflictos OAuth), 502 (error GitHub API)

---

## 4. Servicios Disponibles

### UserService (`services/authentication.py`)

| Método | Descripción |
|--------|-------------|
| `create_user(data)` | Crea usuario con email/contraseña, envía email de bienvenida |
| `get_user_by_email(email)` | Busca usuario por email |
| `get_user_by_id(user_id)` | Busca usuario por ID |
| `create_user_with_github(data)` | Crea usuario desde GitHub OAuth o enlaza si ya existe por email |
| `link_github_account(user_id, data)` | Enlaza cuenta GitHub a usuario existente |

**Métodos internos (GitHub):**
- `_resolve_github_identity` – Intercambia code por token y obtiene perfil
- `_exchange_github_code_for_token` – Intercambio OAuth
- `_fetch_github_user` – Obtiene perfil de GitHub API
- `_fetch_primary_github_email` – Obtiene email primario de GitHub
- `_create_github_link` – Crea registro OAuthAccount
- `_send_welcome_email` – Envía email de bienvenida

---

### MailService (`services/mail/`)

**Interfaz abstracta:** `MailService.send_email(payload: EmailPayload)`

**Implementaciones:**
- **FastAPIMailService** – Desarrollo (fastapi-mail, Mailpit en localhost:8025)
- **ResendMailService** – Producción (Resend API)

**Factory:** `build_mail_service(settings)` → selecciona provider según `APP_ENV`

**EmailPayload:**
- `to`: list[str]
- `subject`: str
- `html`: str | None
- `text`: str | None

**Helpers:**
- `render_html_template(template_path, **context)` – Jinja2
- `validate_mail_settings(settings)` – Valida configuración

---

## 5. Controladores

### UserController (`controllers/authentication.py`)

Recibe `AsyncSession` y `MailService` por inyección.

| Método | Descripción |
|--------|-------------|
| `create_user(data)` | Crea usuario y devuelve `SucessWithData` o `ErrorResponse` |
| `create_user_with_github(data)` | Crea usuario con GitHub |
| `link_github_account(user_id, data)` | Enlaza GitHub a usuario existente |

**Decorador:** `@handle_controller_errors` – Captura `AppError`, `IntegrityError` y excepciones genéricas, devuelve `ErrorResponse`.

---

## 6. Modelos (ORM)

### BaseModel (`models/base.py`)

Campos comunes:
- `id`: UUID (gen_random_uuid)
- `is_active`: bool
- `created_at`: datetime (timezone)
- `updated_at`: datetime (timezone)

---

### User (`models/user.py`)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `name` | str | Nombre del usuario |
| `email` | str | Email único |
| `password` | str \| None | Hash bcrypt (null si solo OAuth) |
| `role` | UserRole | admin \| user |
| `status` | UserStatus | active \| inactive \| pending \| banned |
| `oauth_accounts` | relationship | Cuentas OAuth enlazadas |

**Enums:**
- `UserRole`: ADMIN, USER
- `UserStatus`: ACTIVE, INACTIVE, PENDING, BANNED

---

### OAuthAccount (`models/user.py`)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `user_id` | UUID | FK a user.id (CASCADE) |
| `provider` | OauthProviders | github \| no_provider \| google |
| `provider_user_id` | str | ID en el proveedor |
| `provider_login` | str \| None | Login (ej: "carlos-dev") |
| `access_token` | str \| None | Token de acceso |

**Constraints:**
- `uq_oauth_user_provider`: (user_id, provider) único
- `uq_oauth_provider_user`: (provider, provider_user_id) único

---

## 7. Esquemas Pydantic

### Base (`schemas/base.py`)

- **BaseResponse:** `success`, `message`
- **SucessWithData:** hereda + `result: Any`
- **ErrorResponse:** hereda + `err`, `err_code`, `status_code`

### User Management (`schemas/user_managment.py`)

- **CurrentUser:** id, name, email, role, status
- **CreateUserRequest:** name, email, password (validaciones: email válido, password ≥8 chars)
- **GitHubOAuthRequest:** code, redirect_uri (opcional)

---

## 8. Configuración (`config.py`)

Variables de entorno (Settings con Pydantic):

| Variable | Descripción | Default |
|----------|-------------|---------|
| `GITHUB_CLIENT_ID` | OAuth GitHub | - |
| `GITHUB_CLIENT_SECRET` | OAuth GitHub | - |
| `GITHUB_API_BASE_URL` | API GitHub | https://api.github.com |
| `DATABASE_URL` | URL PostgreSQL | requerido |
| `APP_ENV` | Entorno | development |
| `APP_PORT` | Puerto | 8000 |
| `APP_TIMEZONE` | Zona horaria | America/Argentina/Buenos_Aires |
| `MAIL_*` | Config email | ver config.py |
| `RESEND_API_KEY` | Producción | - |
| `AI_PROVIDER` | groq \| anthropic \| openai \| ollama | groq |
| `AI_PROVIDER_API_KEY` | API key del provider seleccionado | - |
| `LOG_*` | Logging | INFO, json, etc. |

---

## 9. Base de Datos

### Conexión (`db/connection.py`)

- **Motor:** SQLAlchemy async (asyncpg)
- **Session factory:** `async_sessionmaker` con `expire_on_commit=False`
- **Lifespan:** `create_session_factory()` al inicio, `close_engine()` al apagado

### Queries (`db/queries.py`)

Helpers para SQL raw:
- `fetch_one(query, *args)` → primera fila o None
- `fetch_all(query, *args)` → lista de filas
- `execute(query, *args)` → ejecuta y commit
- `execute_many(query, args_list)` → ejecuta múltiples sets de parámetros

Soporta placeholders `$1`, `$2` (asyncpg) convertidos a `:p1`, `:p2`.

---

## 10. Dependencias (`dependencies.py`)

| Función | Retorno | Uso |
|---------|---------|-----|
| `get_settings()` | Settings | Configuración |
| `get_db_session()` | AsyncIterator[AsyncSession] | Sesión DB por request |
| `get_mail_service()` | MailService | Servicio de correo |
| `get_ai_provider_client()` | AsyncIterator[client] | Cliente AI unificado (Groq/Anthropic/OpenAI/Ollama) |

---

## 11. Excepciones y Decoradores

### AppError (`exceptions.py`)

- `message`: str
- `err_code`: str
- `status_code`: int

### handle_controller_errors (`controllers/decorators.py`)

- Captura `AppError` → ErrorResponse con message/err_code/status_code
- Captura `IntegrityError` → mapea a ErrorResponse (DUPLICATE_EMAIL, GITHUB_ACCOUNT_ALREADY_LINKED, etc.)
- Cualquier otra excepción → ErrorResponse 500 con mensaje por defecto

---

## 12. Utilidades

### security (`utils/security.py`)

- `hash_string(value)` → bcrypt (pre-hash SHA-256 para normalizar longitud)
- `verify_string(value, hashed_value)` → bool

### text (`utils/text.py`)

- `capitalize_words(value)` → capitaliza cada palabra

### timezone (`timezone.py`)

- `get_app_timezone()` → ZoneInfo
- `now_in_app_timezone()` → datetime actual en zona configurada

---

## 13. Logging (`logging_config.py`)

- **Formatos:** JSON, text
- **Handlers:** stdout, file (RotatingFileHandler)
- **Config:** LOG_LEVEL, LOG_FORMAT, LOG_FILE_PATH, etc.

---

## 14. Migraciones (Alembic)

- **Motor:** async (asyncpg)
- **Modelos:** User, OAuthAccount (Base metadata)
- **Ubicación:** `alembic/versions/`

---

## 15. Middleware y CORS

- **CORS:** `allow_origins=["http://localhost:5173"]`, credentials, métodos y headers permitidos
- **Exception handler:** Excepciones no manejadas → 500 con `{"detail": "Internal server error"}`

---

## 16. Lifespan (Startup/Shutdown)

1. Configurar logging
2. Construir MailService
3. Crear session factory (DB)
4. (Dev) Log de Mailpit en localhost:8025
5. Al shutdown: cerrar engine de DB
