# config/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool  # для SQLite в памяти

from models.base import Base  # импортируем ТВОЙ Base

# Выбираем тип БД
DB_TYPE = os.getenv("DB_TYPE", "sqlite")  # sqlite, postgresql, mysql

if DB_TYPE == "sqlite":
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lectures.db")
    # Для SQLite нужны особые настройки
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
        poolclass=StaticPool if DATABASE_URL == "sqlite:///:memory:" else None,
        echo=True  # Включаем SQL логгирование для отладки
    )
elif DB_TYPE == "postgresql":
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/lectures")
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    raise ValueError(f"Unsupported DB type: {DB_TYPE}")

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency для получения сессии БД
    Использование:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Создает все таблицы"""
    Base.metadata.create_all(bind=engine)

def drop_tables():
    """Удаляет все таблицы (для тестов)"""
    Base.metadata.drop_all(bind=engine)

# Опционально: создаем таблицы при импорте
if __name__ == "__main__":
    create_tables()
    print("✅ Tables created!")