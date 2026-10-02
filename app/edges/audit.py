"""The audit record: one row per decision, saved before the response leaves.

Each row holds what the service saw (the claim text), what it decided (the outcome), why (every
proxy check result) and which exact system decided (provenance). The row is saved in one
transaction; if saving fails, the request fails: no decision leaves without its record.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.core.models import ClaimDecision
from app.edges.config import settings

database = create_engine(settings.database_url)   # SQLAlchemy calls this an "engine": the connection to the database


class Base(DeclarativeBase):
    pass


class AuditRecord(Base):
    __tablename__ = "audit_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    claim_text: Mapped[str] = mapped_column(Text)
    ai_model_answer: Mapped[dict] = mapped_column(JSON)
    proxy_check_results: Mapped[list] = mapped_column(JSON)
    outcome: Mapped[str] = mapped_column(String(20))
    ai_model: Mapped[str] = mapped_column(String(100))
    ai_model_fingerprint: Mapped[str] = mapped_column(String(64))
    instructions_fingerprint: Mapped[str] = mapped_column(String(64))


def create_tables() -> None:
    Base.metadata.create_all(database)


def save_audit_record(claim_text: str, decision: ClaimDecision, provenance: dict, received_at: datetime) -> int:
    record = AuditRecord(
        received_at=received_at,
        claim_text=claim_text,
        ai_model_answer=decision.extracted_claim.model_dump(mode="json"),
        proxy_check_results=[result.model_dump() for result in decision.proxy_check_results],
        outcome=decision.outcome,
        **provenance,
    )
    with Session(database) as session, session.begin():   # one transaction: saved completely, or not at all
        session.add(record)
        session.flush()                                  # the database assigns the record's id
        return record.id


def straight_through_rate() -> dict:
    """The share of decisions made with no person involved, over all audit records."""
    with Session(database) as session:
        decisions = session.scalar(select(func.count()).select_from(AuditRecord))
        automatic = session.scalar(
            select(func.count()).select_from(AuditRecord).where(AuditRecord.outcome == "auto_approve"))
    rate = round(automatic / decisions, 3) if decisions else None
    return {"decisions": decisions, "automatic": automatic, "straight_through_rate": rate}
