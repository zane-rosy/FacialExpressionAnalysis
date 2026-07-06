# Backend

Backend API del proyecto de tesis.

## Stack

- Python
- FastAPI

## Alcance actual

- endpoint de salud,
- endpoint base para analisis de imagen,
- contratos de request/response,
- servicios stub para integracion futura con detector de emociones y OpenFace.

## Ejecucion

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Nota de entorno

- En Windows se instala `dlib-bin` en lugar de `dlib` para evitar compilacion nativa con Python 3.13.
- En Linux y otros entornos se mantiene `dlib`.

## Endpoints iniciales

- `GET /health`
- `POST /api/v1/analysis/image`
