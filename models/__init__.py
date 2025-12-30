"""
Модели базы данных для системы управления пользователями
"""
from .base import Base
from .users import User, UserType, AnswerStat
from .logs import ScoreChangeLog, OperationLog
from .groups import Group
from .database_manager import db, DatabaseManager
from .database_manager import (
    make_seminarist, make_admin, reset_to_student,
    create_group, set_user_group, set_transfer_deadline,
    get_available_groups_for_student
)
from .lectures import Lecture, LectureView
from .questions import Question, UserAnswer  # Добавляем модели вопросов
from .seminar_stats import SeminarStat, UserSeminarStat  # Добавляем статистику

__all__ = [
    'Base',
    'User',
    'UserType',
    'AnswerStat',
    'ScoreChangeLog',
    'OperationLog',
    'Group',
    'db',
    'DatabaseManager',
    'make_seminarist',
    'make_admin',
    'reset_to_student',
    'create_group',
    'set_user_group',
    'set_transfer_deadline',
    'get_available_groups_for_student',
    'Lecture',
    'LectureView',
    'Question',           # Новая модель вопросов
    'UserAnswer',         # Новая модель ответов пользователей
    'SeminarStat',        # Новая статистика по семинарам
    'UserSeminarStat'     # Новая статистика пользователей по семинарам
]