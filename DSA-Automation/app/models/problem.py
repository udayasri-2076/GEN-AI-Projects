from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    title: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    difficulty: Mapped[str] = mapped_column(
        String,
        nullable=False
    )