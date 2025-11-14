# Messaging Service (FastAPI)

Microservicio de mensajería para Roomiefy, compatible con los endpoints usados por el frontend (REST + WebSocket).

## Endpoints implementados

- GET /conversations?userId=EMAIL
- POST /conversations
- GET /conversations/{conversation_id}
- GET /conversations/{conversation_id}/messages
- POST /conversations/{conversation_id}/messages
- PATCH /conversations/{conversation_id}/read
- PATCH /messages/{message_id}/status
- WS /ws/chat/{room_id}

## Ejecución local

1. Python 3.10+
2. Crear y activar un virtualenv
3. Instalar dependencias:

```
pip install -r requirements.txt
```

4. Ejecutar servidor (puerto 8000):

```
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Configuración

- Por defecto usa SQLite local (`messaging.db`).
- Variables en `.env`:
  - `DATABASE_URL` (opcional)

## Recomendación de base de datos en Azure (producción)

- Cosmos DB (API MongoDB) para chat/mensajería: baja latencia, escalable globalmente, y soporta Change Feed para integrarse con una arquitectura orientada a eventos.
- Para eventos: Azure Service Bus o Event Hubs.
- Esquema sugerido:
  - conversations: { id, participants: [userId], lastMessage, lastMessageTime }
  - messages: { id, conversationId, senderId, content, timestamp, status, isReadBy: [userId] }

Este microservicio está listo para desarrollo local; para producción, sustituye SQLite por Cosmos DB y agrega autenticación y autorización.
