# backend/database.py
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, ForeignKey, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

# Create SQLAlchemy engine and session
DATABASE_URL = "sqlite:///functions.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Function(Base):
    __tablename__ = "functions"  # Fix the double underscore format
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    language = Column(String)
    code = Column(Text)
    timeout = Column(Integer, default=30)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

def create_tables():
    Base.metadata.create_all(bind=engine)
