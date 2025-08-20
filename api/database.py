"""
Database manager for ChatBot Premium
Handles PostgreSQL connection and operations for NeonDB
"""
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

Base = declarative_base()

class ChatSession(Base):
    __tablename__ = 'chat_sessions'
    
    session_id = Column(String(36), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant' or 'system'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.connected = False
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize database connection"""
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                logger.warning("DATABASE_URL not found. Database features will be disabled.")
                return
            
            # Handle NeonDB SSL requirement
            if 'neon.tech' in database_url and 'sslmode=' not in database_url:
                separator = '&' if '?' in database_url else '?'
                database_url += f'{separator}sslmode=require'
            
            self.engine = create_engine(
                database_url,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=False
            )
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.connected = True
            logger.info("Database connection established successfully")
            
            # Create tables if they don't exist
            self._create_tables()
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            self.connected = False
    
    def _create_tables(self):
        """Create database tables if they don't exist"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created/verified successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
    
    def get_session(self) -> Optional[Session]:
        """Get database session"""
        if not self.connected or not self.SessionLocal:
            return None
        try:
            return self.SessionLocal()
        except Exception as e:
            logger.error(f"Failed to create database session: {e}")
            return None
    
    def create_session(self, session_id: str) -> bool:
        """Create a new chat session"""
        if not self.connected:
            return False
        
        db_session = self.get_session()
        if not db_session:
            return False
        
        try:
            # Check if session already exists
            existing = db_session.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()
            
            if existing:
                return True
            
            # Create new session
            new_session = ChatSession(session_id=session_id)
            db_session.add(new_session)
            db_session.commit()
            logger.info(f"Created new chat session: {session_id}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            db_session.rollback()
            return False
        finally:
            db_session.close()
    
    def add_message(self, session_id: str, role: str, content: str) -> bool:
        """Add a message to a chat session"""
        if not self.connected:
            return False
        
        db_session = self.get_session()
        if not db_session:
            return False
        
        try:
            # Ensure session exists
            self.create_session(session_id)
            
            # Add message
            message = ChatMessage(
                session_id=session_id,
                role=role,
                content=content
            )
            db_session.add(message)
            
            # Update session timestamp
            session = db_session.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()
            if session:
                session.updated_at = datetime.utcnow()
            
            db_session.commit()
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to add message to session {session_id}: {e}")
            db_session.rollback()
            return False
        finally:
            db_session.close()
    
    def get_session_messages(self, session_id: str) -> List[Dict]:
        """Get all messages from a chat session"""
        if not self.connected:
            return []
        
        db_session = self.get_session()
        if not db_session:
            return []
        
        try:
            messages = db_session.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.timestamp).all()
            
            return [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat()
                }
                for msg in messages
            ]
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to get messages for session {session_id}: {e}")
            return []
        finally:
            db_session.close()
    
    def get_recent_sessions(self, limit: int = 50) -> List[Dict]:
        """Get recent chat sessions"""
        if not self.connected:
            return []
        
        db_session = self.get_session()
        if not db_session:
            return []
        
        try:
            # Get sessions with their first user message for preview
            sessions = []
            recent_sessions = db_session.query(ChatSession).order_by(
                ChatSession.updated_at.desc()
            ).limit(limit).all()
            
            for session in recent_sessions:
                # Get first user message for preview
                first_message = db_session.query(ChatMessage).filter(
                    ChatMessage.session_id == session.session_id,
                    ChatMessage.role == 'user'
                ).order_by(ChatMessage.timestamp).first()
                
                # Count total messages
                message_count = db_session.query(ChatMessage).filter(
                    ChatMessage.session_id == session.session_id,
                    ChatMessage.role.in_(['user', 'assistant'])
                ).count()
                
                preview = "New chat"
                if first_message:
                    preview = first_message.content[:50]
                    if len(first_message.content) > 50:
                        preview += "..."
                
                sessions.append({
                    'session_id': session.session_id,
                    'preview': preview,
                    'created_at': session.created_at.isoformat(),
                    'updated_at': session.updated_at.isoformat(),
                    'message_count': message_count
                })
            
            return sessions
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to get recent sessions: {e}")
            return []
        finally:
            db_session.close()
    
    def get_all_sessions(self) -> List[Dict]:
        """Get all chat sessions (alias for get_recent_sessions for backward compatibility)"""
        return self.get_recent_sessions()
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and all its messages"""
        if not self.connected:
            return False
        
        db_session = self.get_session()
        if not db_session:
            return False
        
        try:
            # Delete all messages for this session
            deleted_messages = db_session.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).delete()
            
            # Delete the session
            deleted_session = db_session.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).delete()
            
            db_session.commit()
            
            if deleted_session > 0:
                logger.info(f"Deleted session {session_id} with {deleted_messages} messages")
                return True
            else:
                logger.warning(f"Session {session_id} not found for deletion")
                return False
                
        except SQLAlchemyError as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            db_session.rollback()
            return False
        finally:
            db_session.close()
    
    def health_check(self) -> Dict:
        """Check database health"""
        if not self.connected:
            return {'status': 'disconnected', 'error': 'No database connection'}
        
        try:
            db_session = self.get_session()
            if not db_session:
                return {'status': 'error', 'error': 'Cannot create session'}
            
            # Test query
            db_session.execute(text("SELECT 1"))
            db_session.close()
            
            return {'status': 'healthy', 'connected': True}
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

# Global database manager instance
db_manager = DatabaseManager()