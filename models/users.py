from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Date, ForeignKey, DateTime, Enum, Float

# Импортируем Base из base.py вместо создания здесь
from .base import Base


# Типы пользователей
class UserType(PyEnum):
    STUDENT = "student"
    SEMINARIAN = "seminarist"
    ADMIN = "admin"


# Базовый класс пользователя
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    score = Column(Integer, default=100)
    seminar_grade = Column(Float, nullable=True)  # Оценка за семинары (0-10)
    requests_today = Column(Integer, default=0)
    last_request_date = Column(Date, nullable=True)
    user_type = Column(Enum(UserType), default=UserType.STUDENT, nullable=False)
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=True)

    # Связи будут установлены позже в database_manager.py

    def can_change_score(self, target_user):
        """Проверяет, может ли пользователь изменять баллы другого пользователя"""
        if self.user_type == UserType.ADMIN:
            return True
        elif self.user_type == UserType.SEMINARIAN:
            return True
        return False

    def change_user_score(self, target_user, delta, session=None):
        """Изменяет баллы другого пользователя с учетом типа пользователя"""
        if not self.can_change_score(target_user):
            raise PermissionError(f"User {self.username} cannot change scores")

        if session is None:
            raise ValueError("Session is required for score change")

        old_score = target_user.score
        new_score = old_score + delta
        target_user.score = new_score

        # Логируем изменение, если это не админ (у админов логирование отключено)
        if self.user_type != UserType.ADMIN:
            # Импортируем здесь, чтобы избежать циклических зависимостей
            from .logs import ScoreChangeLog
            log_entry = ScoreChangeLog(
                user_id=target_user.id,
                changed_by_id=self.id,
                old_score=old_score,
                new_score=new_score,
                delta=delta
            )
            session.add(log_entry)

        return old_score, new_score

    def __repr__(self):
        group_info = f", group_id={self.group_id}" if self.group_id else ""
        return f"<User(id={self.id}, username='{self.username}', type={self.user_type.value}{group_info})>"


# Модель для статистики ответов
class AnswerStat(Base):
    __tablename__ = 'answers_stats'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    correct_cnt = Column(Integer, default=0)
    wrong_cnt = Column(Integer, default=0)

    def __repr__(self):
        return f"<AnswerStat(name='{self.name}', correct={self.correct_cnt}, wrong={self.wrong_cnt})>"