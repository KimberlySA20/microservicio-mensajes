from app.db import SessionLocal, init_db, Conversation, ConversationParticipant, Message
from sqlalchemy import exists, and_
from datetime import datetime, timedelta

TEST_USER_ID = "102239748272978520578"
PARTNER_IDS = [
    ("roomie_demo_1", "Roomie Demo 1"),
    ("roomie_demo_2", "Roomie Demo 2"),
]


def ensure_conversation(db, user_a: str, user_b: str):
    # Crea una conversación nueva siempre (para simplificar los tests)
    conv = Conversation()
    db.add(conv)
    db.flush()

    db.add(ConversationParticipant(conversation_id=conv.id, user_id=user_a))
    db.add(ConversationParticipant(conversation_id=conv.id, user_id=user_b))

    base_time = datetime.utcnow() - timedelta(minutes=5)

    demo_messages = [
        (user_b, "¡Hola! Vi tu perfil y me interesa conversar."),
        (user_a, "¡Hola! Claro, me gusta tu perfil también."),
        (user_b, "¿Qué zona te gustaría y cuál es tu presupuesto?"),
        (user_a, "Zona centro, presupuesto alrededor de 400-500 USD."),
        (user_b, "Perfecto, tengo opciones por esa zona. 😊"),
    ]

    for i, (sender, content) in enumerate(demo_messages):
        msg = Message(
            conversation_id=conv.id,
            sender_id=sender,
            content=content,
            timestamp=base_time + timedelta(minutes=i),
            status="read" if sender == user_b else "delivered",
            is_read=True if sender == user_b else False,
        )
        db.add(msg)

    return conv


def main():
    init_db()
    db = SessionLocal()
    try:
        created = []
        for partner_id, _partner_name in PARTNER_IDS:
            conv = ensure_conversation(db, TEST_USER_ID, partner_id)
            created.append(conv.id)
        db.commit()
        print("Conversaciones creadas:", created)
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
