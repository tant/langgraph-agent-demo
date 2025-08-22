# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "sqlalchemy[asyncio]>=2.0.0",
#     "aiosqlite",
#     "asyncpg", # For Postgres support (optional)
# ]
# ///
"""
Database models and setup for the Mai-Sale chat application.

This script defines the data models and database setup logic.
- Uses SQLAlchemy 2.0 with async support
- Supports SQLite (dev) and Postgres (prod) via aiosqlite and asyncpg
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Integer, Uuid, func
import uuid
from typing import AsyncGenerator, Optional, List
from datetime import datetime

# --- Configuration ---
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "sqlite+aiosqlite:///./database/sqlite.db"
)

# --- Database Setup ---
# Create async engine
engine = create_async_engine(DATABASE_URL, echo=True)  # Set echo=False in production

# Create async session factory
async_session = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

# --- Base Class for Models ---
class Base(DeclarativeBase):
    pass

# --- Data Models ---
class Conversation(Base):
    __tablename__ = "conversations"
    
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), index=True) # Opaque user identifier
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # JSON column for extensible metadata
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", type_=String) 
    
    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, user_id='{self.user_id}')>"


class Message(Base):
    __tablename__ = "messages"
    
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    sender: Mapped[str] = mapped_column(String(50)) # 'user' or 'assistant'
    text: Mapped[str] = mapped_column(Text)
    tokens_estimate: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # JSON column for extensible metadata (e.g., embedding status)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", type_=String)
    
    def __repr__(self) -> str:
        return f"<Message(id={self.id}, conversation_id={self.conversation_id}, sender='{self.sender}')>"


# --- Database Initialization ---
async def init_db():
    """Create all tables defined in the models."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get a database session."""
    async with async_session() as session:
        yield session
        
# --- CRUD Operations ---
async def create_conversation(user_id: str, metadata: Optional[dict] = None) -> Conversation:
    """Create a new conversation."""
    async with async_session() as session:
        conversation = Conversation(user_id=user_id, metadata_=metadata)
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation

async def get_conversation(conversation_id: uuid.UUID) -> Optional[Conversation]:
    """Retrieve a conversation by ID."""
    async with async_session() as session:
        return await session.get(Conversation, conversation_id)

async def create_message(
    conversation_id: uuid.UUID, 
    sender: str, 
    text: str, 
    tokens_estimate: Optional[int] = None,
    metadata: Optional[dict] = None
) -> Message:
    """Create a new message in a conversation."""
    async with async_session() as session:
        message = Message(
            conversation_id=conversation_id,
            sender=sender,
            text=text,
            tokens_estimate=tokens_estimate,
            metadata_=metadata
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        # Update conversation's last_active_at
        conversation = await session.get(Conversation, conversation_id)
        if conversation:
            conversation.last_active_at = func.now()
            await session.commit()
        return message

async def get_messages_history(conversation_id: uuid.UUID) -> List[Message]:
    """Retrieve message history for a conversation, ordered by creation time."""
    async with async_session() as session:
        from sqlalchemy import select, asc
        stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(asc(Message.created_at))
        result = await session.execute(stmt)
        return list(result.scalars().all())