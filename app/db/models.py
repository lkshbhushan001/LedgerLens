from enum import Enum
from sqlalchemy import Column, String, DateTime
import datetime
from app.db.database import Base


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentDBRecord(Base):
    __tablename__ = "documents"

    document_id = Column(String, primary_key=True, index=True)
    source_filename = Column(String, nullable=False)
    status = Column(String, nullable=False, default=DocumentStatus.PENDING.value)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))


Document = DocumentDBRecord