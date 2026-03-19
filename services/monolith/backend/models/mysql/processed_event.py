from sqlalchemy import Index, UniqueConstraint

from .common import Base, Column, DateTime, Integer, String, func


class ProcessedEvent(Base):
    """Tracks which events each consumer has already handled.

    The unique constraint on ``(correlation_id, consumer_name)`` allows
    different consumers to process the same event independently while
    preventing any single consumer from handling an event twice.
    """

    __tablename__ = "processed_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    correlation_id = Column(String(36), nullable=False)
    consumer_name = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    processed_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("correlation_id", "consumer_name", name="uq_correlation_consumer"),
        Index("ix_processed_at", "processed_at"),
        {"mysql_engine": "InnoDB"},
    )
