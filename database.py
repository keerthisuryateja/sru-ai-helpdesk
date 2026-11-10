import os
from datetime import datetime, timezone
import json
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./helpdesk.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Faculty(Base):
    __tablename__ = "faculty"

    emp_id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    email = Column(String(120), nullable=True, default=None)
    cabin_id = Column(String(50), nullable=True, default=None)

    def to_dict(self):
        return {
            "emp_id": self.emp_id,
            "name": self.name,
            "email": self.email or "Not Available",
            "cabin_id": self.cabin_id
        }


class AdministrativePersonnel(Base):
    __tablename__ = "administrative_personnel"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role = Column(String(150), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(120), nullable=True, default=None)
    cabin_room_number = Column(String(50), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "name": self.name,
            "email": self.email or "Not Available",
            "cabin_room_number": self.cabin_room_number
        }


class UniversityKnowledge(Base):
    __tablename__ = "university_knowledge"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    category = Column(String(100), nullable=False, index=True)  # e.g., fees, rules, permissions, events, placements, hostel, facilities
    title = Column(String(200), nullable=False, index=True)
    content = Column(Text, nullable=False)
    tags = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "tags": [t.strip() for t in (self.tags or "").split(",") if t.strip()]
        }


class StudentClub(Base):
    __tablename__ = "student_clubs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    club_name = Column(String(150), nullable=False, index=True)
    social_media_link = Column(String(255), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "club_name": self.club_name,
            "social_media_link": self.social_media_link
        }


class CollegeWebsite(Base):
    __tablename__ = "college_websites"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url = Column(String(255), nullable=False)
    purpose_tags = Column(Text, nullable=False)  # Stored as comma-separated or JSON string

    def to_dict(self):
        # Format tags cleanly for response
        tags_list = []
        if self.purpose_tags:
            try:
                parsed = json.loads(self.purpose_tags)
                if isinstance(parsed, list):
                    tags_list = parsed
                else:
                    tags_list = [str(parsed)]
            except Exception:
                tags_list = [t.strip() for t in self.purpose_tags.split(",") if t.strip()]

        return {
            "id": self.id,
            "url": self.url,
            "purpose_tags": self.purpose_tags,
            "tags_list": tags_list
        }


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    matched_sources = Column(Text, nullable=True)  # JSON string of source records
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        sources = []
        if self.matched_sources:
            try:
                sources = json.loads(self.matched_sources)
            except Exception:
                sources = [self.matched_sources]
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "matched_sources": sources,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
