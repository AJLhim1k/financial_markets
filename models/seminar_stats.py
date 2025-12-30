"""
Модели для статистики по семинарам
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, Boolean
from sqlalchemy import func

from .base import Base


class SeminarStat(Base):
    """
    Агрегированная статистика по семинару
    """
    __tablename__ = 'seminar_stats'

    id = Column(Integer, primary_key=True, index=True)
    seminar_number = Column(Integer, nullable=False, index=True, unique=True)

    total_questions = Column(Integer, default=0, nullable=False)
    active_questions = Column(Integer, default=0, nullable=False)

    total_answers = Column(Integer, default=0, nullable=False)
    correct_answers = Column(Integer, default=0, nullable=False)
    incorrect_answers = Column(Integer, default=0, nullable=False)

    average_score = Column(Float, default=0.0, nullable=False)
    average_accuracy = Column(Float, default=0.0, nullable=False)
    average_time = Column(Float, default=0.0, nullable=False)

    easy_questions = Column(Integer, default=0, nullable=False)
    medium_questions = Column(Integer, default=0, nullable=False)
    hard_questions = Column(Integer, default=0, nullable=False)

    option_popularity = Column(JSON, nullable=True)

    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)
    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            'seminar_number': self.seminar_number,
            'questions': {
                'total': self.total_questions,
                'active': self.active_questions,
                'difficulty_distribution': {
                    'easy': self.easy_questions,
                    'medium': self.medium_questions,
                    'hard': self.hard_questions
                }
            },
            'answers': {
                'total': self.total_answers,
                'correct': self.correct_answers,
                'incorrect': self.incorrect_answers,
                'accuracy': round((self.correct_answers / self.total_answers * 100) if self.total_answers > 0 else 0, 2)
            },
            'averages': {
                'score': round(self.average_score, 2),
                'accuracy': round(self.average_accuracy, 2),
                'time': round(self.average_time, 2)
            },
            'last_updated': self.last_updated.isoformat(),
            'calculated_at': self.calculated_at.isoformat()
        }


class UserSeminarStat(Base):
    """
    Статистика пользователя по семинару
    """
    __tablename__ = 'user_seminar_stats'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    seminar_number = Column(Integer, nullable=False, index=True)

    total_answers = Column(Integer, default=0, nullable=False)
    correct_answers = Column(Integer, default=0, nullable=False)
    incorrect_answers = Column(Integer, default=0, nullable=False)

    total_score = Column(Integer, default=0, nullable=False)
    max_possible_score = Column(Integer, default=0, nullable=False)

    total_time_spent = Column(Integer, default=0, nullable=False)
    average_time_per_question = Column(Float, default=0.0, nullable=False)

    completion_percentage = Column(Float, default=0.0, nullable=False)
    first_attempt_at = Column(DateTime, nullable=True)
    last_attempt_at = Column(DateTime, nullable=True)

    is_completed = Column(Boolean, default=False, nullable=False)
    best_score = Column(Integer, default=0, nullable=False)
    attempts_count = Column(Integer, default=0, nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

    @property
    def accuracy_percentage(self) -> float:
        if self.total_answers == 0:
            return 0.0
        return round((self.correct_answers / self.total_answers) * 100, 2)

    @property
    def score_percentage(self) -> float:
        if self.max_possible_score == 0:
            return 0.0
        return round((self.total_score / self.max_possible_score) * 100, 2)

    def to_dict(self) -> dict:
        return {
            'user_id': self.user_id,
            'seminar_number': self.seminar_number,
            'answers': {
                'total': self.total_answers,
                'correct': self.correct_answers,
                'incorrect': self.incorrect_answers,
                'accuracy': self.accuracy_percentage
            },
            'scores': {
                'total': self.total_score,
                'max_possible': self.max_possible_score,
                'percentage': self.score_percentage,
                'best': self.best_score
            },
            'time': {
                'total_seconds': self.total_time_spent,
                'average_per_question': round(self.average_time_per_question, 2)
            },
            'progress': {
                'completion_percentage': round(self.completion_percentage, 2),
                'is_completed': self.is_completed,
                'attempts': self.attempts_count
            },
            'dates': {
                'first_attempt': self.first_attempt_at.isoformat() if self.first_attempt_at else None,
                'last_attempt': self.last_attempt_at.isoformat() if self.last_attempt_at else None,
                'updated': self.updated_at.isoformat() if self.updated_at else None
            }
        }