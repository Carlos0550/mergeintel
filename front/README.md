# MergeIntel Frontend

Frontend React migrado a `Vite + TypeScript`.

## Requisitos

- Node.js 18-22
- npm 10

## Variables de entorno

Crea un `.env.local` opcional si quieres apuntar el frontend a otro backend:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

Compatibilidad transitoria:

- `VITE_API_BASE_URL` es la variable oficial.
- Si no existe, el frontend también acepta `REACT_APP_API_BASE_URL`.
- Si ninguna está definida, usa `http://localhost:8000`.

## Scripts

- `npm run dev`: levanta Vite en `http://localhost:3000`
- `npm run build`: ejecuta typecheck y build de producción
- `npm run preview`: sirve el build localmente
- `npm run test`: ejecuta los smoke tests con Vitest

## Instalación

```bash
npm install
npm run dev
```

## Notas

- El proyecto ya no depende de `Create React App`, `CRACO` ni `Emergent visual edits`.
- El alias `@` apunta a `src/`.
- Si el backend corre en otro origen, recuerda habilitar CORS para `http://localhost:3000`.
