"""SQLAlchemy models for CircularLens AI.

Document – represents an uploaded circular file.
Chunk – represents a piece of extracted text from a document, used for semantic search.
"""

from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import relationship

from ..database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True, nullable=False)
    upload_time = Column(DateTime, default=datetime.utcnow)
    # Path on disk relative to project root
    path = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    extracted_text = Column(Text, default="", nullable=False)
    page_count = Column(Integer, default=0, nullable=False)
    analysis = Column(JSON, nullable=True)
    deadline = Column(DateTime, nullable=True)
    deadline_confirmed = Column(Boolean, default=False, nullable=False)
    category = Column(String, default="General", nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    content_hash = Column(String, index=True, nullable=True)
    # ``pending`` is explicit when a controlled import could persist source
    # material but could not obtain embeddings. Normal uploads remain indexed.
    index_status = Column(String, default="indexed", nullable=False)
    version_of_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    # Documents are scoped to the uploader and (when available) their workspace.
    # These are nullable for backwards compatibility with pre-authentication data.
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)

    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    text = Column(Text, nullable=False)
    # Optionally store embedding as a stringified list for simplicity
    embedding = Column(Text)
    page_number = Column(Integer, default=1, nullable=False)
    embedding_provider = Column(String, nullable=True)
    embedding_model = Column(String, nullable=True)
    embedding_dimension = Column(Integer, nullable=True)
    index_version = Column(String, nullable=True)

    document = relationship("Document", back_populates="chunks")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    event_type = Column(String, nullable=False)
    detail = Column(String, nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # role column removed from Organization (not needed)


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    # Existing production databases require this field.  Keep a Python-side
    # default so registration works even where SQLite has no server default.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # role column removed from Organization (not needed)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization = relationship('Organization', foreign_keys=[organization_id])
    role = Column(String, default="member", nullable=False)
    token_version = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # role column removed from Organization (not needed)



class NotificationSubscription(Base):
    __tablename__ = "notification_subscriptions"
    id = Column(Integer, primary_key=True)
    channel = Column(String, nullable=False)  # email or webhook/WhatsApp gateway
    destination = Column(String, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # role column removed from Organization (not needed)


class ActionItem(Base):
    __tablename__ = "action_items"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, default="", nullable=False)
    deadline = Column(DateTime, nullable=True)
    priority = Column(String, default="medium", nullable=False)
    status = Column(String, default="pending", nullable=False)
    evidence = Column(Text, default="", nullable=False)
    ai_suggested = Column(Boolean, default=True, nullable=False)
    verified_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action_type = Column(String, default="application", nullable=False)
    amount = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # role column removed from Organization (not needed)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    document = relationship("Document")


class DocumentReview(Base):
    __tablename__ = "document_reviews"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    field_name = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    evidence = Column(Text, default="", nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # role column removed from Organization (not needed)


class InAppNotification(Base):
    __tablename__ = "in_app_notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    kind = Column(String, nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, default="", nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    action_id = Column(Integer, ForeignKey("action_items.id"), nullable=True, index=True)
    scheduled_for = Column(DateTime, nullable=True)
    read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # role column removed from Organization (not needed)


class ReminderDelivery(Base):
    """Persistent idempotency record for an in-app reminder interval."""
    __tablename__ = "reminder_deliveries"
    __table_args__ = (UniqueConstraint("user_id", "action_id", "reminder_kind", name="uq_reminder_delivery"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action_id = Column(Integer, ForeignKey("action_items.id"), nullable=False, index=True)
    reminder_kind = Column(String, nullable=False)
    scheduled_for = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)


class SchedulerLease(Base):
    """A short database lease so concurrent application workers schedule once."""
    __tablename__ = "scheduler_leases"

    name = Column(String, primary_key=True)
    owner_id = Column(String, nullable=False)
    locked_until = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserPreference(Base):
    __tablename__ = "user_preferences"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    departments = Column(JSON, default=list, nullable=False)
    programs = Column(JSON, default=list, nullable=False)
    semesters = Column(JSON, default=list, nullable=False)
    categories = Column(JSON, default=list, nullable=False)
    bookmarks = Column(JSON, default=list, nullable=False)
    timezone = Column(String, default="UTC", nullable=False)


class SystemConfig(Base):
    __tablename__ = "system_config"
    key = Column(String, primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RuleClause(Base):
    __tablename__ = "rule_clauses"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    category = Column(String, nullable=False)
    rule_value = Column(JSON, nullable=False)
    conditions = Column(JSON, default=list, nullable=False)
    effective_date = Column(DateTime, nullable=True)
    source_excerpt = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    verified = Column(Boolean, default=False, nullable=False)
    review_status = Column(String, default="suggested", nullable=False)
    extraction_model = Column(String, nullable=False)
    extraction_version = Column(String, default="academic-rules-v1", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # role column removed from Organization (not needed)
    document = relationship("Document")


class CircularRelationship(Base):
    __tablename__ = "circular_relationships"
    id = Column(Integer, primary_key=True)
    source_document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    target_document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    relationship_type = Column(String, nullable=False)
    scope = Column(JSON, default=dict, nullable=False)
    evidence = Column(Text, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # role column removed from Organization (not needed)


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=True)
    institution = Column(String, nullable=True)
    program = Column(String, nullable=True)
    department = Column(String, nullable=True)
    semester = Column(Integer, nullable=True)
    attendance_percentage = Column(Integer, nullable=True)
    backlog_count = Column(Integer, nullable=True)
    condonation_approved = Column(Boolean, nullable=True)
    previous_marks_percentage = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # role column removed from Organization (not needed)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
