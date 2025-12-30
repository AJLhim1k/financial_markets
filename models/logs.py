from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime

# Импортируем Base из base.py
from .base import Base


# Модель для логирования изменений баллов
class ScoreChangeLog(Base):
    __tablename__ = 'score_change_log'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    changed_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    old_score = Column(Integer, nullable=False)
    new_score = Column(Integer, nullable=False)
    delta = Column(Integer, nullable=False)
    change_time = Column(DateTime, default=datetime.now)

    # Связи будут установлены позже в database_manager.py


# Модель для общего лога операций
class OperationLog(Base):
    __tablename__ = 'operation_logs'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    operation_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    # Связь будет установлена позже в database_manager.py

    def __repr__(self):
        return f"<OperationLog(id={self.id}, user_id={self.user_id}, type='{self.operation_type}')>"