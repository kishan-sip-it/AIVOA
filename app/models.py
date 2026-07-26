"""
models.py
---------
SQLAlchemy ORM model(s) for the AIVOA Complaint Management System.

A single `Complaint` table stores the committed, final version of a
complaint record once it has passed AI triage and the user commits it
to the QMS (Quality Management System) ledger.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # --- Origin & Customer ---
    complaint_source = Column(String(100), nullable=False)
    customer_name = Column(String(255), nullable=False)

    # --- Product & Batch ---
    product_name = Column(String(255), nullable=False)
    product_strength = Column(String(100), nullable=True)
    batch_number = Column(String(100), nullable=False)
    affected_quantity = Column(String(100), nullable=True)
    manufacturing_date = Column(String(50), nullable=True)
    expiry_date = Column(String(50), nullable=True)

    # --- Facility & Material ---
    originating_site_block = Column(String(100), nullable=False)
    impacted_npm = Column(Text, nullable=True)

    # --- Defect Analysis ---
    complaint_category = Column(String(100), nullable=False)
    complaint_date = Column(String(50), nullable=True)
    priority = Column(String(50), nullable=True)
    complaint_description = Column(Text, nullable=False)

    # --- AI Copilot Risk Assessment ---
    severity_suggested = Column(String(50), nullable=True)
    suggested_next_action = Column(Text, nullable=True)
    initial_risk_assessment = Column(Text, nullable=True)
    complaint_summary = Column(Text, nullable=True)
    root_cause_recommendation = Column(Text, nullable=True)
    capa_recommendation = Column(Text, nullable=True)

    # --- Audit / Traceability ---
    raw_input = Column(Text, nullable=True)          # original free text / PDF text
    chat_history = Column(JSON, nullable=True)        # full copilot conversation
    status = Column(String(50), default="committed", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    committed_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Complaint id={self.id} batch={self.batch_number} status={self.status}>"