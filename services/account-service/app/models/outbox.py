from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.database import Base


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"

    id = Column(String(36), primary_key=True)
    aggregate_type = Column(String(50), nullable=False)
    aggregate_id = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload_json = Column(Text, nullable=False)
    correlation_id = Column(String(36), nullable=True)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(DateTime, server_default=func.now(), nullable=False)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<OutboxEvent(id={self.id}, type={self.event_type}, status={self.status})>"
