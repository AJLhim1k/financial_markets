import os
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON, Float, CheckConstraint
from sqlalchemy.orm import relationship, validates
from sqlalchemy import func

from .base import Base


class Question(Base):
    """
    Модель вопроса к семинару
    Каждый вопрос имеет 6 вариантов ответа, из которых 1 или несколько верных
    Привязан к номеру семинара (1-20)
    """
    __tablename__ = 'questions'

    id = Column(Integer, primary_key=True, index=True)

    # Привязка к номеру семинара (1-20)
    seminar_number = Column(
        Integer,
        nullable=False,
        index=True,
        info={'check': 'seminar_number BETWEEN 1 AND 20'}
    )

    # Основная информация
    title = Column(String(500), nullable=False)  # Текст вопроса
    description = Column(Text, nullable=True)  # Пояснение к вопросу

    # Сложность вопроса (будет импортироваться из Excel)
    difficulty = Column(String(20), default="medium", nullable=False)  # easy, medium, hard

    # Варианты ответов (храним как JSON) - РОВНО 6 вариантов
    options = Column(JSON, nullable=False)  # Список из 6 вариантов: ["Вариант A", "Вариант B", ...]

    # Верные ответы (индексы от 0 до 5) - минимум 1, максимум 6
    correct_answers = Column(JSON, nullable=False)  # Список индексов верных ответов [1, 3, 5]

    # Время на ответ (в секундах, 0 - без ограничения)
    time_limit = Column(Integer, default=0, nullable=False)

    # Баллы (1 за верный ответ, 0 за неверный)
    points = Column(Integer, default=1, nullable=False)  # Только 1 балл за правильный ответ

    # Порядок и организация
    order = Column(Integer, default=0, nullable=False, index=True)  # Порядок в семинаре
    is_active = Column(Boolean, default=True, nullable=False)  # Активен ли вопрос
    tags = Column(JSON, nullable=True)  # Теги для фильтрации

    # Даты
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    user_answers = relationship("UserAnswer", back_populates="question", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint('seminar_number >= 1 AND seminar_number <= 20', name='check_seminar_range'),
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name='check_difficulty'),
    )

    @validates('seminar_number')
    def validate_seminar_number(self, key, seminar_number):
        """Проверяем, что номер семинара от 1 до 20"""
        if not isinstance(seminar_number, int):
            raise ValueError("Seminar number must be integer")
        if seminar_number < 1 or seminar_number > 20:
            raise ValueError(f"Seminar number must be between 1 and 20, got {seminar_number}")
        return seminar_number

    @validates('difficulty')
    def validate_difficulty(self, key, difficulty):
        """Проверяем сложность вопроса"""
        valid_difficulties = ['easy', 'medium', 'hard']
        if difficulty not in valid_difficulties:
            raise ValueError(f"Difficulty must be one of {valid_difficulties}, got {difficulty}")
        return difficulty

    @validates('options')
    def validate_options(self, key, options):
        """Проверяем, что ровно 6 вариантов ответа"""
        if not isinstance(options, list):
            raise ValueError("Options must be a list")
        if len(options) != 6:
            raise ValueError(f"Must have exactly 6 options, got {len(options)}")

        # Проверяем, что все варианты не пустые
        for i, option in enumerate(options):
            if not option or str(option).strip() == "":
                raise ValueError(f"Option {i + 1} cannot be empty")

        return options

    @validates('correct_answers')
    def validate_correct_answers(self, key, correct_answers):
        """Проверяем корректность верных ответов"""
        if not isinstance(correct_answers, list):
            raise ValueError("Correct answers must be a list")

        if len(correct_answers) == 0:
            raise ValueError("Must have at least 1 correct answer")

        if len(correct_answers) > 6:
            raise ValueError(f"Cannot have more than 6 correct answers, got {len(correct_answers)}")

        # Проверяем индексы
        seen = set()
        for idx in correct_answers:
            if not isinstance(idx, int):
                raise ValueError(f"Answer index must be integer, got {type(idx)}")
            if idx < 0 or idx > 5:
                raise ValueError(f"Answer index must be between 0 and 5, got {idx}")
            if idx in seen:
                raise ValueError(f"Duplicate answer index: {idx}")
            seen.add(idx)

        return sorted(correct_answers)  # Возвращаем отсортированный список

    @validates('points')
    def validate_points(self, key, points):
        """Проверяем, что баллы равны 1"""
        if points != 1:
            raise ValueError("Points must be exactly 1 (1 for correct, 0 for incorrect)")
        return points

    @property
    def options_dict(self) -> Dict[int, str]:
        """Возвращает варианты ответов как словарь {индекс: текст}"""
        return {i: option for i, option in enumerate(self.options)}

    @property
    def correct_options_text(self) -> List[str]:
        """Возвращает текст верных вариантов ответа"""
        return [self.options[idx] for idx in self.correct_answers]

    @property
    def incorrect_options_text(self) -> List[str]:
        """Возвращает текст неверных вариантов ответа"""
        return [self.options[i] for i in range(6) if i not in self.correct_answers]

    @property
    def correct_count(self) -> int:
        """Количество верных ответов"""
        return len(self.correct_answers)

    def is_correct(self, user_answers: List[int]) -> bool:
        """
        Проверяет, верны ли ответы пользователя
        user_answers: список индексов выбранных пользователем ответов

        Вопрос считается верным если:
        1. Все выбранные ответы верные
        2. Выбраны ВСЕ верные ответы (ни одного не пропущено)
        """
        if not user_answers:
            return False

        # Все выбранные ответы должны быть верными
        if not set(user_answers).issubset(set(self.correct_answers)):
            return False

        # Должны быть выбраны ВСЕ верные ответы
        return set(user_answers) == set(self.correct_answers)

    def calculate_score(self, user_answers: List[int], time_spent: int = 0) -> Dict:
        """
        Рассчитывает баллы за ответ
        Возвращает словарь с результатом

        Только 1 балл за полностью верный ответ, 0 за любой другой вариант
        """
        is_correct = self.is_correct(user_answers)

        # Только 1 балл за верный ответ, 0 за неверный
        score = 1 if is_correct else 0

        # Нет бонусов за скорость и нет штрафов

        return {
            'is_correct': is_correct,
            'score': score,
            'max_score': 1,  # Всегда 1
            'correct_answers': self.correct_answers,
            'user_answers': user_answers,
            'time_spent': time_spent,
            'time_limit': self.time_limit,
            'correct_selected': len(set(user_answers) & set(self.correct_answers)) if user_answers else 0,
            'incorrect_selected': len(set(user_answers) - set(self.correct_answers)) if user_answers else 0,
            'difficulty': self.difficulty
        }

    def to_dict(self) -> Dict:
        """Сериализация вопроса в словарь"""
        return {
            'id': self.id,
            'seminar_number': self.seminar_number,
            'title': self.title,
            'description': self.description,
            'difficulty': self.difficulty,
            'options': self.options_dict,
            'correct_answers': self.correct_answers,
            'correct_answers_count': self.correct_count,
            'correct_options': self.correct_options_text,
            'incorrect_options': self.incorrect_options_text,
            'time_limit': self.time_limit,
            'points': self.points,  # Всегда 1
            'order': self.order,
            'is_active': self.is_active,
            'tags': self.tags or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'has_user_answers': len(self.user_answers) > 0,
            'answer_stats': self.get_answer_statistics()
        }

    def get_answer_statistics(self):
        """Статистика ответов пользователей на этот вопрос"""
        if not self.user_answers:
            return None

        total_answers = len(self.user_answers)
        correct_answers = sum(1 for a in self.user_answers if a.is_correct)

        # Распределение выбранных вариантов
        option_counts = {i: 0 for i in range(6)}
        for answer in self.user_answers:
            for idx in answer.selected_answers:
                option_counts[idx] = option_counts.get(idx, 0) + 1

        return {
            'total_answers': total_answers,
            'correct_answers': correct_answers,
            'incorrect_answers': total_answers - correct_answers,
            'accuracy': round((correct_answers / total_answers * 100) if total_answers > 0 else 0, 2),
            'option_popularity': option_counts,
            'average_score': round(sum(a.score for a in self.user_answers) / total_answers,
                                   2) if total_answers > 0 else 0,
            'average_time': round(sum(a.time_spent for a in self.user_answers) / total_answers,
                                  2) if total_answers > 0 else 0
        }

    def __repr__(self):
        return f"<Question(id={self.id}, title='{self.title[:50]}...', seminar={self.seminar_number}, difficulty={self.difficulty})>"


class UserAnswer(Base):
    """
    Модель ответа пользователя на вопрос
    """
    __tablename__ = 'user_answers'

    id = Column(Integer, primary_key=True, index=True)

    # Связи
    user_id = Column(Integer, nullable=False, index=True)  # ID пользователя из вашей системы
    question_id = Column(Integer, ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, index=True)
    question = relationship("Question", back_populates="user_answers")

    # Номер семинара (дублируем для быстрых запросов)
    seminar_number = Column(Integer, nullable=False, index=True)

    # Ответ пользователя
    selected_answers = Column(JSON, nullable=False)  # Список индексов выбранных ответов [0, 2, 5]

    # Результат
    is_correct = Column(Boolean, nullable=False)  # Был ли ответ верным
    score = Column(Integer, default=0, nullable=False)  # Набранные баллы (0 или 1)
    max_score = Column(Integer, default=1, nullable=False)  # Всегда 1

    # Время
    started_at = Column(DateTime, nullable=False)  # Когда начал отвечать
    answered_at = Column(DateTime, nullable=False)  # Когда ответил
    time_spent = Column(Integer, nullable=False)  # Сколько секунд потратил (0 если не ограничено)

    # Дополнительная информация
    ip_address = Column(String(45), nullable=True)  # IP пользователя
    user_agent = Column(Text, nullable=True)  # Браузер пользователя
    device_info = Column(JSON, nullable=True)  # Информация об устройстве

    # Для анализа
    attempt_number = Column(Integer, default=1, nullable=False)  # Номер попытки
    session_id = Column(String(100), nullable=True, index=True)  # ID сессии

    __table_args__ = (
        CheckConstraint('seminar_number >= 1 AND seminar_number <= 20', name='check_user_answer_seminar_range'),
        CheckConstraint('score IN (0, 1)', name='check_score_binary'),
    )

    @validates('selected_answers')
    def validate_selected_answers(self, key, selected_answers):
        """Проверяем выбранные ответы"""
        if not isinstance(selected_answers, list):
            raise ValueError("Selected answers must be a list")

        if len(selected_answers) == 0:
            raise ValueError("Must select at least 1 answer")

        if len(selected_answers) > 6:
            raise ValueError(f"Cannot select more than 6 answers, got {len(selected_answers)}")

        seen = set()
        for idx in selected_answers:
            if not isinstance(idx, int):
                raise ValueError(f"Answer index must be integer, got {type(idx)}")
            if idx < 0 or idx > 5:
                raise ValueError(f"Answer index must be between 0 and 5, got {idx}")
            if idx in seen:
                raise ValueError(f"Duplicate selected answer index: {idx}")
            seen.add(idx)

        return sorted(selected_answers)  # Возвращаем отсортированный список

    @validates('seminar_number')
    def validate_seminar_number(self, key, seminar_number):
        """Проверяем номер семинара"""
        if not isinstance(seminar_number, int):
            raise ValueError("Seminar number must be integer")
        if seminar_number < 1 or seminar_number > 20:
            raise ValueError(f"Seminar number must be between 1 and 20, got {seminar_number}")
        return seminar_number

    @validates('score')
    def validate_score(self, key, score):
        """Проверяем, что баллы 0 или 1"""
        if score not in [0, 1]:
            raise ValueError(f"Score must be 0 or 1, got {score}")
        return score

    @validates('max_score')
    def validate_max_score(self, key, max_score):
        """Проверяем, что максимальный балл равен 1"""
        if max_score != 1:
            raise ValueError(f"Max score must be 1, got {max_score}")
        return max_score

    @property
    def selected_options_text(self) -> List[str]:
        """Возвращает текст выбранных вариантов"""
        if not self.question:
            return []
        return [self.question.options[idx] for idx in self.selected_answers]

    @property
    def correct_options_text(self) -> List[str]:
        """Возвращает текст верных вариантов"""
        if not self.question:
            return []
        return self.question.correct_options_text

    @property
    def time_spent_formatted(self) -> str:
        """Возвращает потраченное время в формате MM:SS"""
        if not self.time_spent:
            return "00:00"
        minutes = self.time_spent // 60
        seconds = self.time_spent % 60
        return f"{minutes:02d}:{seconds:02d}"

    @property
    def is_partially_correct(self) -> bool:
        """Для совместимости - всегда False, так как нет частичных баллов"""
        return False

    def to_dict(self, include_question: bool = False) -> Dict:
        """Сериализация ответа в словарь"""
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'question_id': self.question_id,
            'seminar_number': self.seminar_number,
            'selected_answers': self.selected_answers,
            'selected_options': self.selected_options_text,
            'is_correct': self.is_correct,
            'is_partially_correct': False,  # Всегда False
            'score': self.score,
            'max_score': self.max_score,
            'score_percentage': 100.0 if self.score == 1 else 0.0,  # 0% или 100%
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'answered_at': self.answered_at.isoformat() if self.answered_at else None,
            'time_spent': self.time_spent,
            'time_spent_formatted': self.time_spent_formatted,
            'attempt_number': self.attempt_number,
            'session_id': self.session_id,
            'device_info': self.device_info
        }

        if include_question and self.question:
            result['question'] = self.question.to_dict()
            result['correct_answers'] = self.question.correct_answers
            result['correct_options'] = self.correct_options_text
            result['question_difficulty'] = self.question.difficulty

        return result

    def __repr__(self):
        status = "CORRECT" if self.is_correct else "WRONG"
        return f"<UserAnswer(id={self.id}, user={self.user_id}, seminar={self.seminar_number}, {status})>"