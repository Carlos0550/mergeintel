**MergeIntel**

Planificación de desarrollo — Backend

Documento de seguimiento técnico

Versión 1.0 · Marzo 2026

# **Estado actual del proyecto**

El backend de MergeIntel tiene implementada la capa de autenticación completa: registro con email/contraseña, OAuth con GitHub (creación y enlace de cuentas), modelos ORM (User, OAuthAccount), servicio de email, manejo de errores y arquitectura en capas (router → controller → service → db).

**Lo que sigue es el core del producto: la integración con la GitHub API para analizar PRs, la capa de análisis con IA y el chat contextual.**

# **Mapa de fases**


| Fase                       | Descripción                                                                              | Estado          | Archivos clave                                                        |
| -------------------------- | ---------------------------------------------------------------------------------------- | --------------- | --------------------------------------------------------------------- |
| Fase 0 — Auth              | Autenticación completa: email/pass GitHub OAuth, modelos User/OAuthAccount, mail service | **✅ Hecho**     | routers/authentication.py, services/authentication.py, models/user.py |
| Fase 1 — GitHub Client     | Cliente HTTP base para la GitHub API, gestión del token del usuario, rate limiting       | **⏳ Pendiente** | github/client.py, github/exceptions.py                                |
| Fase 2 — PR Fetching       | Obtener commits, autores, diffs y metadata de un PR dado su URL o número                 | **⏳ Pendiente** | github/commits.py, github/diff.py                                     |
| Fase 3 — Análisis estático | Detección de migraciones, cambios fuera de scope, divergencia de rama                    | **⏳ Pendiente** | github/divergence.py, analyzer/schema.py, analyzer/scope.py           |
| Fase 4 — LLM Summary       | Generación del resumen con IA, scoring de riesgo, checklist pre-merge                    | **⏳ Pendiente** | analyzer/summary.py, analyzer/risk.py                                 |
| Fase 5 — PR Endpoints      | Endpoints REST para disparar análisis y recuperar resultados, modelo PRAnalysis en DB    | **⏳ Pendiente** | routers/pr.py, controllers/pr.py, models/pr.py                        |
| Fase 6 — AI Chat           | Chat contextual sobre el PR con historial de mensajes y contexto completo del diff       | **⏳ Pendiente** | routers/chat.py, analyzer/chat.py, models/chat.py                     |
| Fase 7 — Frontend MVP      | Dashboard React: cards por autor, checklist, chat, visualización del análisis            | **⏳ Pendiente** | frontend/src/                                                         |
| Fase 8 — GitHub Actions    | Action para disparar análisis automáticamente al abrir un PR                             | **🚀 Post-MVP** | action.yml, github/webhook.py                                         |


# **Fase 1 — GitHub API Client**

Base de toda la integración. Un cliente async con httpx que usa el accesstoken de GitHub del usuario autenticado para llamar a la API. Sin esto no hay nada.

## **Archivos a crear**


| Archivo / Módulo                 | Responsabilidad                                                                                                  |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **backend/github/init.py**       | Init del módulo                                                                                                  |
| **backend/github/client.py**     | GitHubClient: clase principal con httpx.AsyncClient, autenticación por token, retry básico y rate limit handling |
| **backend/github/exceptions.py** | GitHubAPIError, RateLimitError, RepoNotFoundError, PRNotFoundError                                               |


## **Lógica del cliente**

- Recibe el accesstoken de OAuthAccount al instanciarse
- Todas las requests llevan header Authorization: Bearer {token}
- Maneja 401 (token inválido/expirado), 403 (sin permisos), 404, 429 (rate limit)
- Rate limit: leer headers X-RateLimit-Remaining / X-RateLimit-Reset
- Métodos base: get(), post() — el resto de módulos usan el cliente

## **Dependency injection**

Agregar getgithubclient() en dependencies.py — recibe el user actual, busca su OAuthAccount con provider=github, instancia GitHubClient con ese token.

# **Fase 2 — PR Fetching y mapeo de commits**

Con el cliente listo, traer toda la información de un PR: commits, autores, archivos tocados y diffs.

## **Archivos a crear**


| Archivo / Módulo                 | Responsabilidad                                                                                                         |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **backend/github/commits.py**    | Obtener lista de commits de un PR, mapear cada commit a su autor (nombre, email, login de GitHub)                       |
| **backend/github/diff.py**       | Obtener los archivos modificados por commit, parsear hunks del diff, detectar tipo de cambio (add/modify/delete/rename) |
| **backend/github/divergence.py** | Comparar el timestamp del primer commit del PR con el historial de main para calcular días de divergencia               |
| **backend/schemas/pr.py**        | PRInfo, CommitInfo, AuthorInfo, FileChange, DiffHunk (esquemas Pydantic de respuesta)                                   |


## **GitHub API endpoints que se usarán**


| Método  | Ruta                                                 | Descripción                          |
| ------- | ---------------------------------------------------- | ------------------------------------ |
| **GET** | GET /repos/{owner}/{repo}/pulls/{pullnumber}         | Metadata del PR                      |
| **GET** | GET /repos/{owner}/{repo}/pulls/{pullnumber}/commits | Lista de commits del PR              |
| **GET** | GET /repos/{owner}/{repo}/commits/{sha}              | Detalle de un commit (archivos diff) |
| **GET** | GET /repos/{owner}/{repo}/compare/{base}...{head}    | Divergencia entre ramas              |


## **Estructura de datos resultante**

Al finalizar el fetching, el sistema debe tener en memoria una estructura PRAnalysisInput con:

- prinfo: título, descripción, autor del PR, base branch, head branch, estado
- authors: lista de autores únicos con sus commits
- filechanges: por cada archivo → lista de commits que lo tocaron, tipo de cambio, líneas /-
- rawdiffs: diffs completos para pasarle al LLM

# **Fase 3 — Análisis estático**

Antes de invocar al LLM, extraer señales estructurales que no requieren IA: migraciones pendientes, archivos tocados fuera de scope y antigüedad de la rama.

## **Archivos a crear**


| Archivo / Módulo               | Responsabilidad                                                                                                           |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| **backend/analyzer/init.py**   | Init del módulo                                                                                                           |
| **backend/analyzer/schema.py** | Detectar cambios en archivos SQL, migraciones Alembic (alembic/versions/.py), modelos ORM                                 |
| **backend/analyzer/scope.py**  | Comparar archivos tocados por cada autor vs su scope esperado (inferido por el LLM o definido manualmente)                |
| **backend/analyzer/risk.py**   | Score de riesgo 1-10 basado en: días de divergencia, cantidad de archivos, migraciones pendientes, cambios fuera de scope |


## **Detección de migraciones (schema.py)**

- Patrones a detectar: alembic/versions/.py, /migrations/.py, .sql, models.py modificado
- Output: lista de archivos de migración tocados  si hay cambios en modelos ORM sin migración correspondiente
- Warning especial si hay cambio en models.py pero ningún archivo en alembic/versions/

## **Detección de out-of-scope (scope.py)**

- En MVP: el LLM infiere el scope de cada autor basándose en el nombre de sus commits y archivos históricos
- Flags archivos donde el autor nunca había tocado ese módulo antes
- Output por autor: archivos in-scope / out-of-scope con nivel de confianza

## **Risk scorer (risk.py)**

Score numérico 1-10 compuesto por:

- Días de divergencia:  14 días → riesgo alto
- Cantidad de archivos:  50 → riesgo alto
- Migraciones sin generar → riesgo crítico
- Archivos out-of-scope → riesgo medio-alto
- Conflictos potenciales con main → riesgo alto

# **Fase 4 — LLM Summary**

El núcleo de valor de MergeIntel: tomar todo el contexto del PR y generar un resumen técnico accionable, en lenguaje natural.

## **Archivos a crear**


| Archivo / Módulo                | Responsabilidad                                                                                                                  |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **backend/analyzer/summary.py** | Construye el prompt con el contexto del PR, llama al LLM configurado (Anthropic/OpenAI/Ollama), parsea la respuesta estructurada |
| **backend/analyzer/prompts.py** | Templates de prompts separados del código. System prompt, PR summary prompt, scope analysis prompt                               |


## **Qué genera el LLM**

- Resumen ejecutivo del PR (2-4 párrafos)
- Breakdown por autor: qué hizo cada uno, en qué archivos, posibles conflictos
- Lista de breaking changes detectados
- Checklist pre-merge: migraciones a correr, revisiones necesarias, archivos de riesgo
- Scope inference: qué se supone que debía tocar cada autor (si no está definido)

## **Diseño del prompt**

El contexto que se le pasa al LLM incluye:

- Metadata del PR (título, descripción, base/head branch)
- Por autor: commits, archivos tocados, líneas /-
- Señales del análisis estático: migraciones, out-of-scope flags, score de riesgo
- Diffs de archivos críticos (truncados si exceden el context window)

## **Manejo del AI provider**

Ya tenés getaiproviderclient() en dependencies.py. El summary.py simplemente lo usa. La lógica de qué proveedor usar (Anthropic/OpenAI/Ollama) ya está resuelta en la dependency.

# **Fase 5 — PR Endpoints y persistencia**

Exponer todo el análisis vía REST y persistir los resultados en la base de datos.

## **Nuevos archivos**


| Archivo / Módulo              | Responsabilidad                                                                          |
| ----------------------------- | ---------------------------------------------------------------------------------------- |
| **backend/models/pr.py**      | PRAnalysis (resultado completo), CommitRecord, FileChangeRecord, ChecklistItem           |
| **backend/routers/pr.py**     | Endpoints de análisis de PR                                                              |
| **backend/controllers/pr.py** | PRController: orquesta github fetching → análisis estático → LLM summary → guardar en DB |
| **backend/services/pr.py**    | PRService: lógica de negocio, interacción con DB                                         |
| **backend/schemas/pr.py**     | AnalyzePRRequest, PRAnalysisResponse, ChecklistResponse                                  |


## **Endpoints**


| Método     | Ruta                       | Descripción                                                             |
| ---------- | -------------------------- | ----------------------------------------------------------------------- |
| **POST**   | /pr/analyze                | Recibe repourl prnumber, dispara análisis completo, devuelve analysisid |
| **GET**    | /pr/{analysisid}           | Recupera un análisis guardado por ID                                    |
| **GET**    | /pr/{analysisid}/checklist | Solo el checklist pre-merge                                             |
| **GET**    | /pr/history                | Lista de análisis del usuario autenticado                               |
| **DELETE** | /pr/{analysisid}           | Eliminar un análisis guardado                                           |


## **Modelo PRAnalysis en DB**

Campos principales:

- id, userid (FK), createdat, updatedat (hereda de BaseModel)
- repofullname: string (ej: 'carlos/mergeintel')
- prnumber: int
- prtitle: string
- summaryjson: JSONB — el resumen completo del LLM
- riskscore: int (1-10)
- authorsjson: JSONB — breakdown por autor
- checklistjson: JSONB — items del checklist
- divergencedays: int
- status: enum (pending, processing, done, error)

# **Fase 6 — AI Chat**

Chat contextual sobre un PR específico. El usuario puede hacer preguntas en lenguaje natural y el LLM responde con el contexto completo del análisis.

## **Nuevos archivos**


| Archivo / Módulo                | Responsabilidad                                                                                             |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| **backend/analyzer/chat.py**    | Construye el contexto del chat a partir del PRAnalysis guardado, maneja historial de mensajes, llama al LLM |
| **backend/routers/chat.py**     | Endpoints del chat                                                                                          |
| **backend/controllers/chat.py** | ChatController                                                                                              |
| **backend/models/chat.py**      | ChatSession, ChatMessage                                                                                    |
| **backend/schemas/chat.py**     | ChatRequest, ChatResponse, MessageHistory                                                                   |


## **Endpoints**


| Método     | Ruta                       | Descripción                               |
| ---------- | -------------------------- | ----------------------------------------- |
| **POST**   | /chat/{analysisid}/message | Enviar mensaje, recibir respuesta del LLM |
| **GET**    | /chat/{analysisid}/history | Historial de mensajes de una sesión       |
| **DELETE** | /chat/{analysisid}         | Limpiar historial de chat                 |


## **Diseño del chat**

- Cada sesión de chat está ligada a un analysisid
- El system prompt incluye el análisis completo del PR como contexto
- El historial de mensajes se persiste en DB (ChatMessage)
- Límite de tokens: si el contexto  historial excede el límite, truncar mensajes antiguos
- Ejemplos de queries que debe poder responder:
- 'Pedro solo debía tocar el módulo de pagos, ¿lo cumplió?'
- '¿Qué migraciones de Alembic necesito generar?'
- '¿Qué commits tienen más chances de generar conflictos con main?'
- 'Resumí los cambios de Carlos en una oración'
  **MergeIntel**
  Planificación de desarrollo — Backend
  Documento de seguimiento técnico
  Versión 1.0 · Marzo 2026
  # **Estado actual del proyecto**
  El backend de MergeIntel tiene implementada la capa de autenticación completa: registro con email/contraseña, OAuth con GitHub (creación y enlace de cuentas), modelos ORM (User, OAuthAccount), servicio de email, manejo de errores y arquitectura en capas (router → controller → service → db).
  **Lo que sigue es el core del producto: la integración con la GitHub API para analizar PRs, la capa de análisis con IA y el chat contextual.**
  # **Mapa de fases**
  | Fase | Descripción | Estado | Archivos clave |
  | :---- | :---- | :---- | :---- |
  | Fase 0 — Auth | Autenticación completa: email/pass \+ GitHub OAuth, modelos User/OAuthAccount, mail service | **✅ Hecho** | routers/[authentication.py](http://authentication.py), services/[authentication.py](http://authentication.py), models/[user.py](http://user.py) |
  | Fase 1 — GitHub Client | Cliente HTTP base para la GitHub API, gestión del token del usuario, rate limiting | **⏳ Pendiente** | github/[client.py](http://client.py), github/[exceptions.py](http://exceptions.py) |
  | Fase 2 — PR Fetching | Obtener commits, autores, diffs y metadata de un PR dado su URL o número | **⏳ Pendiente** | github/[commits.py](http://commits.py), github/[diff.py](http://diff.py) |
  | Fase 3 — Análisis estático | Detección de migraciones, cambios fuera de scope, divergencia de rama | **⏳ Pendiente** | github/[divergence.py](http://divergence.py), analyzer/[schema.py](http://schema.py), analyzer/[scope.py](http://scope.py) |
  | Fase 4 — LLM Summary | Generación del resumen con IA, scoring de riesgo, checklist pre-merge | **⏳ Pendiente** | analyzer/[summary.py](http://summary.py), analyzer/[risk.py](http://risk.py) |
  | Fase 5 — PR Endpoints | Endpoints REST para disparar análisis y recuperar resultados, modelo PRAnalysis en DB | **⏳ Pendiente** | routers/[pr.py](http://pr.py), controllers/[pr.py](http://pr.py), models/[pr.py](http://pr.py) |
  | Fase 6 — AI Chat | Chat contextual sobre el PR con historial de mensajes y contexto completo del diff | **⏳ Pendiente** | routers/[chat.py](http://chat.py), analyzer/[chat.py](http://chat.py), models/[chat.py](http://chat.py) |
  | Fase 7 — Frontend MVP | Dashboard React: cards por autor, checklist, chat, visualización del análisis | **⏳ Pendiente** | frontend/src/ |
  | Fase 8 — GitHub Actions | Action para disparar análisis automáticamente al abrir un PR | **🚀 Post-MVP** | action.yml, github/[webhook.py](http://webhook.py) |
  # **Fase 1 — GitHub API Client**
  Base de toda la integración. Un cliente async con httpx que usa el access\_token de GitHub del usuario autenticado para llamar a la API. Sin esto no hay nada.
  ## **Archivos a crear**
  | Archivo / Módulo | Responsabilidad |
  | :---- | :---- |
  | **backend/github/\_\_init\_\_.py** | Init del módulo |
  | **backend/github/[client.py](http://client.py)** | GitHubClient: clase principal con httpx.AsyncClient, autenticación por token, retry básico y rate limit handling |
  | **backend/github/[exceptions.py](http://exceptions.py)** | GitHubAPIError, RateLimitError, RepoNotFoundError, PRNotFoundError |
  ## **Lógica del cliente**
  * Recibe el access\_token de OAuthAccount al instanciarse
  * Todas las requests llevan header Authorization: Bearer {token}
  * Maneja 401 (token inválido/expirado), 403 (sin permisos), 404, 429 (rate limit)
  * Rate limit: leer headers X-RateLimit-Remaining / X-RateLimit-Reset
  * Métodos base: get(), post() — el resto de módulos usan el cliente
  ## **Dependency injection**
  Agregar get\_github\_client() en [dependencies.py](http://dependencies.py) — recibe el user actual, busca su OAuthAccount con provider=github, instancia GitHubClient con ese token.
  # **Fase 2 — PR Fetching y mapeo de commits**
  Con el cliente listo, traer toda la información de un PR: commits, autores, archivos tocados y diffs.
  ## **Archivos a crear**
  | Archivo / Módulo | Responsabilidad |
  | :---- | :---- |
  | **backend/github/[commits.py](http://commits.py)** | Obtener lista de commits de un PR, mapear cada commit a su autor (nombre, email, login de GitHub) |
  | **backend/github/[diff.py](http://diff.py)** | Obtener los archivos modificados por commit, parsear hunks del diff, detectar tipo de cambio (add/modify/delete/rename) |
  | **backend/github/[divergence.py](http://divergence.py)** | Comparar el timestamp del primer commit del PR con el historial de main para calcular días de divergencia |
  | **backend/schemas/[pr.py](http://pr.py)** | PRInfo, CommitInfo, AuthorInfo, FileChange, DiffHunk (esquemas Pydantic de respuesta) |
  ## **GitHub API endpoints que se usarán**
  | Método | Ruta | Descripción |
  | ----- | :---- | :---- |
  | **GET** | GET /repos/{owner}/{repo}/pulls/{pull\_number} | Metadata del PR |
  | **GET** | GET /repos/{owner}/{repo}/pulls/{pull\_number}/commits | Lista de commits del PR |
  | **GET** | GET /repos/{owner}/{repo}/commits/{sha} | Detalle de un commit (archivos \+ diff) |
  | **GET** | GET /repos/{owner}/{repo}/compare/{base}...{head} | Divergencia entre ramas |
  ## **Estructura de datos resultante**
  Al finalizar el fetching, el sistema debe tener en memoria una estructura PRAnalysisInput con:
  * pr\_info: título, descripción, autor del PR, base branch, head branch, estado
  * authors: lista de autores únicos con sus commits
  * file\_changes: por cada archivo → lista de commits que lo tocaron, tipo de cambio, líneas \+/-
  * raw\_diffs: diffs completos para pasarle al LLM
  # **Fase 3 — Análisis estático**
  Antes de invocar al LLM, extraer señales estructurales que no requieren IA: migraciones pendientes, archivos tocados fuera de scope y antigüedad de la rama.
  ## **Archivos a crear**
  | Archivo / Módulo | Responsabilidad |
  | :---- | :---- |
  | **backend/analyzer/\_\_init\_\_.py** | Init del módulo |
  | **backend/analyzer/[schema.py](http://schema.py)** | Detectar cambios en archivos SQL, migraciones Alembic (alembic/versions/\*.py), modelos ORM |
  | **backend/analyzer/[scope.py*](http://scope.py)* | Comparar archivos tocados por cada autor vs su scope esperado (inferido por el LLM o definido manualmente) |
  | **backend/analyzer/[risk.py](http://risk.py)** | Score de riesgo 1-10 basado en: días de divergencia, cantidad de archivos, migraciones pendientes, cambios fuera de scope |
  ## **Detección de migraciones ([schema.py](http://schema.py))**
   *Patrones a detectar: alembic/versions/\*.py, \*\*/migrations/\*.py, \*.sql, [models.py](http://models.py) modificado
  * Output: lista de archivos de migración tocados \+ si hay cambios en modelos ORM sin migración correspondiente
  * Warning especial si hay cambio en [models.py](http://models.py) pero ningún archivo en alembic/versions/
  ## **Detección de out-of-scope ([scope.py](http://scope.py))**
  * En MVP: el LLM infiere el scope de cada autor basándose en el nombre de sus commits y archivos históricos
  * Flags archivos donde el autor nunca había tocado ese módulo antes
  * Output por autor: archivos in-scope / out-of-scope con nivel de confianza
  ## **Risk scorer ([risk.py](http://risk.py))**
  Score numérico 1-10 compuesto por:
  * Días de divergencia: \> 14 días → riesgo alto
  * Cantidad de archivos: \> 50 → riesgo alto
  * Migraciones sin generar → riesgo crítico
  * Archivos out-of-scope → riesgo medio-alto
  * Conflictos potenciales con main → riesgo alto
  # **Fase 4 — LLM Summary**
  El núcleo de valor de MergeIntel: tomar todo el contexto del PR y generar un resumen técnico accionable, en lenguaje natural.
  ## **Archivos a crear**
  | Archivo / Módulo | Responsabilidad |
  | :---- | :---- |
  | **backend/analyzer/[summary.py](http://summary.py)** | Construye el prompt con el contexto del PR, llama al LLM configurado (Anthropic/OpenAI/Ollama), parsea la respuesta estructurada |
  | **backend/analyzer/[prompts.py](http://prompts.py)** | Templates de prompts separados del código. System prompt, PR summary prompt, scope analysis prompt |
  ## **Qué genera el LLM**
  * Resumen ejecutivo del PR (2-4 párrafos)
  * Breakdown por autor: qué hizo cada uno, en qué archivos, posibles conflictos
  * Lista de breaking changes detectados
  * Checklist pre-merge: migraciones a correr, revisiones necesarias, archivos de riesgo
  * Scope inference: qué se supone que debía tocar cada autor (si no está definido)
  ## **Diseño del prompt**
  El contexto que se le pasa al LLM incluye:
  * Metadata del PR (título, descripción, base/head branch)
  * Por autor: commits, archivos tocados, líneas \+/-
  * Señales del análisis estático: migraciones, out-of-scope flags, score de riesgo
  * Diffs de archivos críticos (truncados si exceden el context window)
  ## **Manejo del AI provider**
  Ya tenés get\_ai\_provider\_client() en [dependencies.py](http://dependencies.py). El [summary.py](http://summary.py) simplemente lo usa. La lógica de qué proveedor usar (Anthropic/OpenAI/Ollama) ya está resuelta en la dependency.
  # **Fase 5 — PR Endpoints y persistencia**
  Exponer todo el análisis vía REST y persistir los resultados en la base de datos.
  ## **Nuevos archivos**
  | Archivo / Módulo | Responsabilidad |
  | :---- | :---- |
  | **backend/models/[pr.py](http://pr.py)** | PRAnalysis (resultado completo), CommitRecord, FileChangeRecord, ChecklistItem |
  | **backend/routers/[pr.py](http://pr.py)** | Endpoints de análisis de PR |
  | **backend/controllers/[pr.py](http://pr.py)** | PRController: orquesta github fetching → análisis estático → LLM summary → guardar en DB |
  | **backend/services/[pr.py](http://pr.py)** | PRService: lógica de negocio, interacción con DB |
  | **backend/schemas/[pr.py](http://pr.py)** | AnalyzePRRequest, PRAnalysisResponse, ChecklistResponse |
  ## **Endpoints**
  | Método | Ruta | Descripción |
  | ----- | :---- | :---- |
  | **POST** | /pr/analyze | Recibe repo\_url \+ pr\_number, dispara análisis completo, devuelve analysis\_id |
  | **GET** | /pr/{analysis\_id} | Recupera un análisis guardado por ID |
  | **GET** | /pr/{analysis\_id}/checklist | Solo el checklist pre-merge |
  | **GET** | /pr/history | Lista de análisis del usuario autenticado |
  | **DELETE** | /pr/{analysis\_id} | Eliminar un análisis guardado |
  ## **Modelo PRAnalysis en DB**
  Campos principales:
  * id, user\_id (FK), created\_at, updated\_at (hereda de BaseModel)
  * repo\_full\_name: string (ej: 'carlos/mergeintel')
  * pr\_number: int
  * pr\_title: string
  * summary\_json: JSONB — el resumen completo del LLM
  * risk\_score: int (1-10)
  * authors\_json: JSONB — breakdown por autor
  * checklist\_json: JSONB — items del checklist
  * divergence\_days: int
  * status: enum (pending, processing, done, error)
  # **Fase 6 — AI Chat**
  Chat contextual sobre un PR específico. El usuario puede hacer preguntas en lenguaje natural y el LLM responde con el contexto completo del análisis.
  ## **Nuevos archivos**
  | Archivo / Módulo | Responsabilidad |
  | :---- | :---- |
  | **backend/analyzer/[chat.py](http://chat.py)** | Construye el contexto del chat a partir del PRAnalysis guardado, maneja historial de mensajes, llama al LLM |
  | **backend/routers/[chat.py](http://chat.py)** | Endpoints del chat |
  | **backend/controllers/[chat.py](http://chat.py)** | ChatController |
  | **backend/models/[chat.py](http://chat.py)** | ChatSession, ChatMessage |
  | **backend/schemas/[chat.py](http://chat.py)** | ChatRequest, ChatResponse, MessageHistory |
  ## **Endpoints**
  | Método | Ruta | Descripción |
  | ----- | :---- | :---- |
  | **POST** | /chat/{analysis\_id}/message | Enviar mensaje, recibir respuesta del LLM |
  | **GET** | /chat/{analysis\_id}/history | Historial de mensajes de una sesión |
  | **DELETE** | /chat/{analysis\_id} | Limpiar historial de chat |
  ## **Diseño del chat**
  * Cada sesión de chat está ligada a un analysis\_id
  * El system prompt incluye el análisis completo del PR como contexto
  * El historial de mensajes se persiste en DB (ChatMessage)
  * Límite de tokens: si el contexto \+ historial excede el límite, truncar mensajes antiguos
  * Ejemplos de queries que debe poder responder:
  * 'Pedro solo debía tocar el módulo de pagos, ¿lo cumplió?'
  * '¿Qué migraciones de Alembic necesito generar?'
  * '¿Qué commits tienen más chances de generar conflictos con main?'
  * 'Resumí los cambios de Carlos en una oración'
  # **Fase 7 — Frontend MVP**
  Dashboard React \+ TypeScript con Vite. El backend ya sirve el frontend buildeado como archivos estáticos desde FastAPI.
  ## **Stack frontend**
  * React \+ TypeScript (ya configurado con Vite)
  * Tailwind CSS — utilidades, sin componentes pesados
  * TanStack Query (React Query) — fetching, cache, loading states
  * React Router — navegación
  * Zustand — estado global mínimo (auth token, usuario actual)
  ## **Vistas principales**
  | Archivo / Módulo | Responsabilidad |
  | :---- | :---- |
  | **/ (Home)** | Landing con input de URL de PR y botón 'Analizar' |
  | **/login** | Login con email/pass \+ botón 'Continuar con GitHub' |
  | **/dashboard** | Lista de análisis previos del usuario |
  | **/analysis/:id** | Vista principal: resumen, cards por autor, checklist, score de riesgo |
  | **/analysis/:id/chat** | Chat contextual sobre el PR |
  ## **Componentes clave**
  * AuthorCard — card por autor con archivos tocados, commits, flags out-of-scope
  * RiskBadge — badge visual con el score 1-10 y color (verde/amarillo/rojo)
  * MigrationWarning — alerta destacada si hay migraciones pendientes
  * PreMergeChecklist — lista interactiva con checkboxes
  * ChatInterface — input \+ historial de mensajes, streaming de respuesta
  # **Estructura de archivos al finalizar el MVP**
  | Archivo / Módulo | Responsabilidad |
  | :---- | :---- |
  | **backend/github/\_\_init\_\_.py** | Init |
  | **backend/github/[client.py](http://client.py)** | GitHubClient (httpx async) |
  | **backend/github/[exceptions.py](http://exceptions.py)** | Excepciones específicas de GitHub API |
  | **backend/github/[commits.py](http://commits.py)** | Fetching de commits y mapeo de autores |
  | **backend/github/[diff.py](http://diff.py)** | Parser de diffs, archivos modificados |
  | **backend/github/[divergence.py](http://divergence.py)** | Cálculo de divergencia de rama |
  | **backend/analyzer/\_\_init\_\_.py** | Init |
  | **backend/analyzer/[schema.py](http://schema.py)** | Detección de migraciones y cambios ORM |
  | **backend/analyzer/[scope.py](http://scope.py)** | Detección de archivos out-of-scope |
  | **backend/analyzer/[risk.py](http://risk.py)** | Risk scorer 1-10 |
  | **backend/analyzer/[summary.py](http://summary.py)** | Generación de resumen con LLM |
  | **backend/analyzer/[prompts.py](http://prompts.py)** | Templates de prompts |
  | **backend/analyzer/[chat.py](http://chat.py)** | Contexto y handler del chat IA |
  | **backend/models/[pr.py](http://pr.py)** | ORM: PRAnalysis, CommitRecord, FileChangeRecord |
  | **backend/models/[chat.py](http://chat.py)** | ORM: ChatSession, ChatMessage |
  | **backend/routers/[pr.py](http://pr.py)** | Endpoints /pr/\* |
  | **backend/routers/[chat.py*](http://chat.py)* | Endpoints /chat/\* |
  | **backend/controllers/[pr.py*](http://pr.py)* | PRController |
  | **backend/controllers/[chat.py](http://chat.py)** | ChatController |
  | **backend/services/[pr.py](http://pr.py)** | PRService |
  | **backend/schemas/[pr.py](http://pr.py)** | Esquemas Pydantic de PR |
  | **backend/schemas/[chat.py](http://chat.py)** | Esquemas Pydantic de chat |
  # **Dependencias adicionales a agregar**
  | Archivo / Módulo | Responsabilidad |
  | :---- | :---- |
  | **httpx** | Ya en uso. Cliente HTTP async para GitHub API |
  | **anthropic** | SDK oficial de Anthropic (Claude). Ya configurado en [dependencies.py](http://dependencies.py) |
  | **openai** | SDK OpenAI (alternativa). Ya configurado |
  | **tiktoken** | Contar tokens antes de enviar al LLM, para truncar contexto si hace falta |
  | **jinja2** | Ya en uso para templates de email. Reutilizar para templates de prompts |
  No se requieren dependencias nuevas para el core del producto. Todo lo necesario ya está en requirements.txt o es parte del stdlib de Python.
  # **Orden de implementación recomendado**
  Cada fase desbloquea la siguiente. No saltar fases — el cliente de GitHub es la base de todo.
  | Fase | Descripción | Estado | Archivos clave |
  | :---- | :---- | :---- | :---- |
  | 1\. GitHub Client | [client.py](http://client.py) \+ [exceptions.py](http://exceptions.py). Sin esto, nada más funciona. | **⏳ Pendiente** | github/[client.py](http://client.py) |
  | 2\. PR Fetching | [commits.py](http://commits.py) \+ [diff.py](http://diff.py) \+ [divergence.py](http://divergence.py). El motor de datos del análisis. | **⏳ Pendiente** | github/[commits.py](http://commits.py), [diff.py](http://diff.py) |
  | 3\. Análisis estático | [schema.py](http://schema.py) \+ [scope.py](http://scope.py) \+ [risk.py](http://risk.py). No requiere LLM, testeable de inmediato. | **⏳ Pendiente** | analyzer/[schema.py](http://schema.py) |
  | 4\. LLM Summary | [summary.py](http://summary.py) \+ [prompts.py](http://prompts.py). Primer 'wow moment' del producto. | **⏳ Pendiente** | analyzer/[summary.py](http://summary.py) |
  | 5\. PR Endpoints | models/[pr.py](http://pr.py) \+ routers/[pr.py](http://pr.py) \+ controller \+ service. Exponer todo vía API y persistir. | **⏳ Pendiente** | routers/[pr.py](http://pr.py) |
  | 6\. Migración DB | Alembic: CREATE TABLE pr\_analysis, commit\_record, chat\_session, chat\_message. | **⏳ Pendiente** | alembic/versions/ |
  | 7\. AI Chat | analyzer/[chat.py](http://chat.py) \+ routers/[chat.py](http://chat.py). El contexto ya está, es agregar la interfaz de chat. | **⏳ Pendiente** | routers/[chat.py](http://chat.py) |
  | 8\. Frontend | React dashboard. Consumir los endpoints ya construidos. | **⏳ Pendiente** | frontend/src/ |
  # **Notas de arquitectura**
  ## **Análisis asíncrono**
  El análisis de un PR puede tardar 10-30 segundos (fetching de GitHub \+ LLM). El endpoint POST /pr/analyze debe devolver inmediatamente un analysis\_id con status=pending y procesar en background con BackgroundTasks de FastAPI o una task queue (Celery/ARQ) si se quiere más control.
  ## **Caché de análisis**
  Si el mismo usuario pide analizar el mismo PR dos veces, devolver el análisis existente si tiene menos de N minutos. El PR puede haber cambiado, así que agregar un parámetro force\_refresh=true para forzar re-análisis.
  ## **Tokens del LLM**
  Los diffs de PRs grandes pueden exceder el context window. Estrategia: priorizar archivos con más cambios y los detectados como críticos (migraciones, modelos), truncar el resto con un resumen de líneas \+/-. tiktoken permite calcular esto antes de hacer la llamada.
  ## **Seguridad del GitHub token**
  El access\_token de GitHub está guardado en OAuthAccount.access\_token. En producción, encriptarlo en la DB (o usar un vault). Para el MVP, al menos no loguearlo nunca.

# **Fase 7 — Frontend MVP**

Dashboard React  TypeScript con Vite. El backend ya sirve el frontend buildeado como archivos estáticos desde FastAPI.

## **Stack frontend**

- React  TypeScript (ya configurado con Vite)
- Tailwind CSS — utilidades, sin componentes pesados
- TanStack Query (React Query) — fetching, cache, loading states
- React Router — navegación
- Zustand — estado global mínimo (auth token, usuario actual)

## **Vistas principales**


| Archivo / Módulo       | Responsabilidad                                                       |
| ---------------------- | --------------------------------------------------------------------- |
| **/ (Home)**           | Landing con input de URL de PR y botón 'Analizar'                     |
| **/login**             | Login con email/pass botón 'Continuar con GitHub'                     |
| **/dashboard**         | Lista de análisis previos del usuario                                 |
| **/analysis/:id**      | Vista principal: resumen, cards por autor, checklist, score de riesgo |
| **/analysis/:id/chat** | Chat contextual sobre el PR                                           |


## **Componentes clave**

- AuthorCard — card por autor con archivos tocados, commits, flags out-of-scope
- RiskBadge — badge visual con el score 1-10 y color (verde/amarillo/rojo)
- MigrationWarning — alerta destacada si hay migraciones pendientes
- PreMergeChecklist — lista interactiva con checkboxes
- ChatInterface — input  historial de mensajes, streaming de respuesta

# **Estructura de archivos al finalizar el MVP**


| Archivo / Módulo                 | Responsabilidad                                 |
| -------------------------------- | ----------------------------------------------- |
| **backend/github/init.py**       | Init                                            |
| **backend/github/client.py**     | GitHubClient (httpx async)                      |
| **backend/github/exceptions.py** | Excepciones específicas de GitHub API           |
| **backend/github/commits.py**    | Fetching de commits y mapeo de autores          |
| **backend/github/diff.py**       | Parser de diffs, archivos modificados           |
| **backend/github/divergence.py** | Cálculo de divergencia de rama                  |
| **backend/analyzer/init.py**     | Init                                            |
| **backend/analyzer/schema.py**   | Detección de migraciones y cambios ORM          |
| **backend/analyzer/scope.py**    | Detección de archivos out-of-scope              |
| **backend/analyzer/risk.py**     | Risk scorer 1-10                                |
| **backend/analyzer/summary.py**  | Generación de resumen con LLM                   |
| **backend/analyzer/prompts.py**  | Templates de prompts                            |
| **backend/analyzer/chat.py**     | Contexto y handler del chat IA                  |
| **backend/models/pr.py**         | ORM: PRAnalysis, CommitRecord, FileChangeRecord |
| **backend/models/chat.py**       | ORM: ChatSession, ChatMessage                   |
| **backend/routers/pr.py**        | Endpoints /pr/                                  |
| **backend/routers/chat.py**      | Endpoints /chat/                                |
| **backend/controllers/pr.py**    | PRController                                    |
| **backend/controllers/chat.py**  | ChatController                                  |
| **backend/services/pr.py**       | PRService                                       |
| **backend/schemas/pr.py**        | Esquemas Pydantic de PR                         |
| **backend/schemas/chat.py**      | Esquemas Pydantic de chat                       |


# **Dependencias adicionales a agregar**


| Archivo / Módulo | Responsabilidad                                                           |
| ---------------- | ------------------------------------------------------------------------- |
| **httpx**        | Ya en uso. Cliente HTTP async para GitHub API                             |
| **anthropic**    | SDK oficial de Anthropic (Claude). Ya configurado en dependencies.py      |
| **openai**       | SDK OpenAI (alternativa). Ya configurado                                  |
| **tiktoken**     | Contar tokens antes de enviar al LLM, para truncar contexto si hace falta |
| **jinja2**       | Ya en uso para templates de email. Reutilizar para templates de prompts   |


No se requieren dependencias nuevas para el core del producto. Todo lo necesario ya está en requirements.txt o es parte del stdlib de Python.

# **Orden de implementación recomendado**

Cada fase desbloquea la siguiente. No saltar fases — el cliente de GitHub es la base de todo.


| Fase                | Descripción                                                                            | Estado          | Archivos clave             |
| ------------------- | -------------------------------------------------------------------------------------- | --------------- | -------------------------- |
| 1 GitHub Client     | client.py exceptions.py. Sin esto, nada más funciona.                                  | **⏳ Pendiente** | github/client.py           |
| 2 PR Fetching       | commits.py diff.py divergence.py. El motor de datos del análisis.                      | **⏳ Pendiente** | github/commits.py, diff.py |
| 3 Análisis estático | schema.py scope.py risk.py. No requiere LLM, testeable de inmediato.                   | **⏳ Pendiente** | analyzer/schema.py         |
| 4 LLM Summary       | summary.py prompts.py. Primer 'wow moment' del producto.                               | **⏳ Pendiente** | analyzer/summary.py        |
| 5 PR Endpoints      | models/pr.py routers/pr.py controller service. Exponer todo vía API y persistir.       | **⏳ Pendiente** | routers/pr.py              |
| 6 Migración DB      | Alembic: CREATE TABLE pranalysis, commitrecord, chatsession, chatmessage.              | **⏳ Pendiente** | alembic/versions/          |
| 7 AI Chat           | analyzer/chat.py routers/chat.py. El contexto ya está, es agregar la interfaz de chat. | **⏳ Pendiente** | routers/chat.py            |
| 8 Frontend          | React dashboard. Consumir los endpoints ya construidos.                                | **⏳ Pendiente** | frontend/src/              |


# **Notas de arquitectura**

## **Análisis asíncrono**

El análisis de un PR puede tardar 10-30 segundos (fetching de GitHub  LLM). El endpoint POST /pr/analyze debe devolver inmediatamente un analysisid con status=pending y procesar en background con BackgroundTasks de FastAPI o una task queue (Celery/ARQ) si se quiere más control.

## **Caché de análisis**

Si el mismo usuario pide analizar el mismo PR dos veces, devolver el análisis existente si tiene menos de N minutos. El PR puede haber cambiado, así que agregar un parámetro forcerefresh=true para forzar re-análisis.

## **Tokens del LLM**

Los diffs de PRs grandes pueden exceder el context window. Estrategia: priorizar archivos con más cambios y los detectados como críticos (migraciones, modelos), truncar el resto con un resumen de líneas /-. tiktoken permite calcular esto antes de hacer la llamada.

## **Seguridad del GitHub token**

El accesstoken de GitHub está guardado en OAuthAccount.accesstoken. En producción, encriptarlo en la DB (o usar un vault). Para el MVP, al menos no loguearlo nunca.