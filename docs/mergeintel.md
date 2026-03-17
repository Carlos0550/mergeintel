# MergeIntel

> Analiza un Pull Request antes de mergearlo. Entiende exactamente qué cambió, quién lo cambió y qué podría romperse.

---

## ¿Qué es MergeIntel?

MergeIntel es una herramienta de análisis de Pull Requests impulsada por inteligencia artificial. Se conecta a tu repositorio de GitHub, lee cada commit de un PR y genera un resumen técnico completo de todo lo que está a punto de entrar en `main`.

El objetivo es eliminar la incertidumbre del proceso de merge: en lugar de revisar commit por commit de forma manual, MergeIntel te da un diagnóstico claro y accionable en segundos.

---

## El problema que resuelve

En equipos donde varias personas trabajan en paralelo, los merges son una fuente constante de problemas silenciosos:

- Una rama estuvo desactualizada durante semanas y va a sobreescribir código reciente.
- Un compañero tocó archivos que estaban fuera de su scope sin darse cuenta.
- Hay cambios en modelos ORM pero nadie generó las migraciones de Alembic.
- No queda claro qué bugs se corrigieron ni qué features se agregaron.

MergeIntel automatiza la detección de todos estos problemas antes de que sea demasiado tarde.

---

## ¿Qué hace exactamente?

**Detección automática de autores.** Cada commit se mapea a su autor. El sistema construye un desglose por persona: qué archivos tocó, cuándo hizo cada commit y qué tan desactualizada estaba su rama en ese momento.

**Análisis de cambios en el esquema.** Detecta modificaciones en archivos SQL, migraciones de Alembic y modelos ORM. Si alguien cambió `models.py` pero no hay ningún archivo en `alembic/versions/`, MergeIntel lo señala con una advertencia específica.

**Detección de archivos fuera de scope.** Compara los archivos tocados por cada autor contra lo que se supone que debía modificar (inferido por la IA o definido manualmente). Cualquier archivo fuera de ese scope queda marcado.

**Divergencia de rama.** Compara el timestamp del primer commit del PR contra el historial de `main` para calcular cuántos días lleva desactualizada la rama. Una rama con 3 semanas de divergencia es una señal de alerta importante.

**Checklist pre-merge.** Genera una lista estructurada de todo lo que hay que resolver antes de mergear: migraciones pendientes, breaking changes, archivos riesgosos que merecen revisión manual.

**Chat contextual con IA.** Una vez que el análisis está listo, podés hacerle preguntas en lenguaje natural al sistema. Por ejemplo: *"¿Pedro solo tocó el módulo de pagos?"* o *"¿Qué migraciones necesito generar?"*. La IA responde con el contexto completo del PR.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python + FastAPI |
| Integración con GitHub | GitHub REST API v3 via `httpx` |
| Análisis con IA | Groq / Anthropic / OpenAI / Ollama |
| Frontend | React + TypeScript |
| Base de datos | PostgreSQL via `asyncpg` |
