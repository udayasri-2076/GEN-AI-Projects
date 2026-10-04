from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Draft(Base):
    """
    Stores an AI-generated DSA draft before approval.

    Nothing is written to the DSA GitHub repository
    until the user approves the draft.
    """

    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    problem_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    problem_title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    topic: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    pattern: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    destination: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    submitted_language: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_file: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    source_code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    missing_files: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
    )

    java_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    python_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    readme_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    feedback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )