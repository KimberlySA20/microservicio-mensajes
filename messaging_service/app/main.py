from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Dict, List, Set
from datetime import datetime
import os

from .db import init_db, get_db, Conversation, ConversationParticipant, Message
from .schemas import ConversationOut, ConversationDetailOut, MessageOut, CreateConversationIn, MessageCreate

app = FastAPI(title="Roomiefy Messaging Service")

# Configuración CORS mejorada
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",  # Vite dev server (alternativa)
    "https://roomiefy.vercel.app"  # Producción
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

init_db()

# -----------------------------
# WebSocket Manager por sala
# -----------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, room_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(room_id, set()).add(websocket)

    def disconnect(self, room_id: int, websocket: WebSocket):
        conns = self.active_connections.get(room_id)
        if conns and websocket in conns:
            conns.remove(websocket)
            if not conns:
                self.active_connections.pop(room_id, None)

    async def broadcast(self, room_id: int, message: dict):
        for ws in list(self.active_connections.get(room_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(room_id, ws)


manager = ConnectionManager()


# -----------------------------
# Helpers
# -----------------------------

def serialize_conversation_summary(db: Session, conv: Conversation) -> ConversationOut:
    last_msg = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.timestamp.desc())
        .first()
    )
    
    # Si la conversación no tiene nombre, asignar uno basado en el ID
    if not hasattr(conv, 'name') or not conv.name:
        name_index = (conv.id - 1) % len(CHAT_NAMES)
        conv.name = CHAT_NAMES[name_index]
    
    return ConversationOut(
        id=conv.id,
        name=conv.name,  # Usar el nombre de la conversación
        avatar=None,
        lastMessage=last_msg.content if last_msg else None,
        lastMessageTime=last_msg.timestamp.strftime("%H:%M") if last_msg else None,
    )


# -----------------------------
# Auto-seed helpers
# -----------------------------
def _enable_auto_seed() -> bool:
    val = os.getenv("ENABLE_AUTO_SEED", "true").lower()
    return val in ("1", "true", "yes", "on")


def ensure_demo_conversations(db: Session, user_id: str) -> None:
    partners = ["roomie_demo_1", "roomie_demo_2"]
    for partner in partners:
        conv = Conversation()
        db.add(conv)
        db.flush()
        db.add(ConversationParticipant(conversation_id=conv.id, user_id=user_id))
        db.add(ConversationParticipant(conversation_id=conv.id, user_id=partner))
        now = datetime.utcnow()
        msgs = [
            (partner, "¡Hola! Vi tu perfil y me interesa conversar."),
            (user_id, "¡Hola! Claro, me gusta tu perfil también."),
            (partner, "¿Qué zona te gustaría y cuál es tu presupuesto?"),
        ]
        for i, (sender, content) in enumerate(msgs):
            m = Message(conversation_id=conv.id, sender_id=sender, content=content, timestamp=now)
            db.add(m)
    db.commit()


# -----------------------------
# REST Endpoints (compatibles con frontend actual)
# -----------------------------
@app.get("/conversations", response_model=List[ConversationOut])
def get_conversations(userId: str | None = None, db: Session = Depends(get_db)):
    if not userId:
        return []
    convs = (
        db.query(Conversation)
        .join(ConversationParticipant)
        .filter(ConversationParticipant.user_id == userId)
        .all()
    )
    if not convs and _enable_auto_seed():
        ensure_demo_conversations(db, userId)
        convs = (
            db.query(Conversation)
            .join(ConversationParticipant)
            .filter(ConversationParticipant.user_id == userId)
            .all()
        )
    return [serialize_conversation_summary(db, c) for c in convs]


@app.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc())
        .all()
    )
    return ConversationDetailOut(id=conversation_id, messages=messages)


@app.get("/conversations/{conversation_id}/messages", response_model=List[MessageOut])
def get_messages(conversation_id: int, db: Session = Depends(get_db)):
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc())
        .all()
    )
    return msgs


# Lista de nombres para los chats
CHAT_NAMES = [
    "Karla Rodríguez",
    "Jorge Méndez",
    "Diego Fernández",
    "Sofía Castillo",
    "Valeria Jiménez",
    "Andrés Navarro",
    "Mariana Solano",
    "Luis Pineda",
    "Camila Herrera",
    "Fernando Rojas",
    "Laura Chacón",
    "Daniel Salas",
    "Gabriela Montoya",
    "Pablo Araya",
    "Natalia Cordero",
    "Ricardo Vargas",
    "Alejandra Pacheco",
    "Sebastián Quesada",
    "Mónica Zamora",
    "Javier Aguirre",
    "Paola Segura",
    "Martín Esquivel",
    "Lucía Morales",
    "Cristian Barboza",
    "Andrea Céspedes",
    "Felipe Marín",
    "Daniela Campos",
    "Marco Leiva"
]

@app.post("/conversations", status_code=201)
def create_conversation(payload: CreateConversationIn, db: Session = Depends(get_db)):
    try:
        print(f"[DEBUG] Creando conversación entre {payload.currentUserId} y {payload.participantId}")
        
        # Verificar si ya existe una conversación entre estos dos usuarios
        from sqlalchemy import func
        
        # Primero obtenemos el conteo de participantes por conversación
        subquery = (
            db.query(
                ConversationParticipant.conversation_id,
                func.count(ConversationParticipant.user_id.distinct()).label('user_count')
            )
            .filter(ConversationParticipant.user_id.in_([payload.currentUserId, payload.participantId]))
            .group_by(ConversationParticipant.conversation_id)
            .subquery()
        )
        
        # Luego filtramos solo las conversaciones que tienen exactamente 2 participantes
        existing_conv = (
            db.query(Conversation)
            .join(subquery, Conversation.id == subquery.c.conversation_id)
            .filter(subquery.c.user_count == 2)
            .first()
        )
        
        if existing_conv:
            print(f"[DEBUG] Conversación existente encontrada: {existing_conv.id}")
            return existing_conv
        
        print("[DEBUG] Creando nueva conversación...")
        
        # Si no existe, creamos una nueva conversación
        conv = Conversation()
        db.add(conv)
        db.flush()
        print(f"[DEBUG] Nueva conversación creada con ID: {conv.id}")

        # Registrar a ambos participantes en la conversación
        participant1 = ConversationParticipant(
            conversation_id=conv.id, 
            user_id=str(payload.participantId)  # Asegurar que sea string
        )
        participant2 = ConversationParticipant(
            conversation_id=conv.id, 
            user_id=str(payload.currentUserId)  # Asegurar que sea string
        )
        
        print(f"[DEBUG] Agregando participantes: {participant1.user_id} y {participant2.user_id}")
        db.add_all([participant1, participant2])

        # Mensaje inicial opcional (lo envía el usuario actual, no como sistema)
        if payload.initialMessage:
            print("[DEBUG] Agregando mensaje inicial")
            msg = Message(
                conversation_id=conv.id, 
                sender_id=str(payload.currentUserId),  # Asegurar que sea string
                content=payload.initialMessage
            )
            db.add(msg)
        
        # Asignar un nombre aleatorio de la lista de nombres
        print("[DEBUG] Asignando nombre a la conversación...")
        name_index = (conv.id - 1) % len(CHAT_NAMES)
        conv.name = CHAT_NAMES[name_index]
        
        print("[DEBUG] Haciendo commit de la transacción...")
        db.commit()
        db.refresh(conv)
        
        print(f"[DEBUG] Conversación creada exitosamente: {conv.id}")
        return {"id": conv.id, "name": conv.name}
        
    except Exception as e:
        print(f"[ERROR] Error al crear conversación: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear la conversación: {str(e)}"
        )


@app.post("/conversations/{conversation_id}/messages", response_model=MessageOut)
def send_message(conversation_id: int, body: MessageCreate, db: Session = Depends(get_db)):
    # Verificar que el remitente sea un participante de la conversación
    participant = db.query(ConversationParticipant).filter(
        ConversationParticipant.conversation_id == conversation_id,
        ConversationParticipant.user_id == body.sender_id
    ).first()
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El remitente no es un participante de esta conversación"
        )
    
    # Crear el mensaje con el sender_id proporcionado
    msg = Message(
        conversation_id=conversation_id, 
        sender_id=body.sender_id, 
        content=body.content,
        status="sent"
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    # Broadcast básico
    payload = {
        "id": msg.id,
        "sender_id": msg.sender_id,
        "content": msg.content,
        "timestamp": msg.timestamp.isoformat(),
        "status": msg.status,
    }
    import anyio
    anyio.from_thread.run(manager.broadcast, conversation_id, payload)
    return msg


@app.patch("/conversations/{conversation_id}/read")
async def mark_conversation_read(conversation_id: int, user_id: str = None, db: Session = Depends(get_db)):
    """
    Marca como leídos los mensajes de una conversación que no pertenecen al usuario actual.
    
    Args:
        conversation_id: ID de la conversación
        user_id: ID del usuario que está leyendo los mensajes
        db: Sesión de base de datos
        
    Returns:
        dict: Estado de la operación
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere el ID del usuario"
        )
    
    try:
        # Verificar que la conversación existe
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversación no encontrada"
            )
        
        # Verificar que el usuario es participante de la conversación
        participant = db.query(ConversationParticipant).filter(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id
        ).first()
        
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para ver esta conversación"
            )
        
        # Marcar como leídos solo los mensajes que no son del usuario actual
        result = db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.sender_id != user_id,
            Message.is_read == False  # Solo marcar los no leídos
        ).update(
            {Message.is_read: True, Message.status: 'read'},
            synchronize_session=False
        )
        
        db.commit()
        
        # Enviar actualización por WebSocket si hay mensajes actualizados
        if result > 0:
            payload = {
                "type": "messages_read",
                "conversation_id": conversation_id,
                "user_id": user_id,
                "count": result
            }
            import anyio
            await anyio.from_thread.run(manager.broadcast, conversation_id, payload)
        
        return {
            "ok": True,
            "updated_count": result,
            "conversation_id": conversation_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al marcar mensajes como leídos: {str(e)}"
        )


@app.patch("/messages/{message_id}/status")
def update_message_status(message_id: int, status: str, db: Session = Depends(get_db)):
    msg = db.get(Message, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.status = status
    db.commit()
    return {"ok": True}


# -----------------------------
# WebSocket
# -----------------------------
@app.websocket("/ws/chat/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int, db: Session = Depends(get_db)):
    await manager.connect(room_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Esperamos: { id, room_id, sender_id, content, timestamp }
            content = data.get("content")
            sender_id = data.get("sender_id")
            if not content or not sender_id:
                await websocket.send_json({"error": "content and sender_id required"})
                continue

            # Persistir
            msg = Message(
                conversation_id=room_id,
                sender_id=sender_id,
                content=content,
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)

            # Respuesta/broadcast normalizada para el frontend (nota: incluye sender como alias)
            payload = {
                "id": msg.id,
                "sender": sender_id,  # para clase sent/received
                "sender_id": sender_id,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "status": msg.status,
            }
            await manager.broadcast(room_id, payload)
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)
    except Exception as e:
        manager.disconnect(room_id, websocket)
        raise e
