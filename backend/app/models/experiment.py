"""Experiment + ExperimentAssignment models (Phase 6).

A/B test infrastructure. An admin defines an Experiment with named variants
and traffic allocation. Users are deterministically bucketed via a
SHA-256(slug + user_id) hash modulo the allocation table — same user, same
experiment → same variant for the experiment's lifetime.

Exposure and conversion are recorded as `ExperimentAssignment` rows so that
analysis is auditable (no live counts, no on-the-fly recomputation needed
for replay).

Hard rules enforced at the service layer:
  - One assignment row per (experiment_id, user_id, variant) — re-exposure
    is idempotent.
  - Conversion can only be stamped on an existing assignment.
  - Result aggregation is a count of rows, never a sample of behaviour.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
)

from app.database import Base


class ExperimentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    slug = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    hypothesis = Column(Text, nullable=True)

    # JSON list of {"name": "control", "weight": 50}, weights sum to 100.
    variants_json = Column(Text, nullable=False,
                           default='[{"name":"control","weight":50},{"name":"treatment","weight":50}]')

    # Which event is the success metric — e.g. "booking.completed".
    success_event_name = Column(String(80), nullable=False,
                                default="booking.completed")

    status = Column(Enum(ExperimentStatus, native_enum=False),
                    nullable=False, default=ExperimentStatus.DRAFT)

    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
        nullable=False,
    )


class ExperimentAssignment(Base):
    __tablename__ = "experiment_assignments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    experiment_id = Column(String, ForeignKey("experiments.id"),
                           nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    variant = Column(String(40), nullable=False)
    exposure_count = Column(Integer, nullable=False, default=1)

    converted = Column(Boolean, nullable=False, default=False)
    converted_at = Column(DateTime, nullable=True)
    conversion_count = Column(Integer, nullable=False, default=0)

    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_exp_assign_exp_user", "experiment_id", "user_id", unique=True),
        Index("ix_exp_assign_exp_variant", "experiment_id", "variant"),
    )
