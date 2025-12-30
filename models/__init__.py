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
    get_available_groups_for_student,
    get_group_rating, get_overall_rating, get_user_rating_position,
    get_top_students_by_group, get_top_students_overall,
    get_rating_statistics, calculate_all_seminar_grades
)
from .lectures import Lecture, LectureView
from .questions import Question, UserAnswer  # Добавляем модели вопросов
from .seminar_stats import SeminarStat, UserSeminarStat  # Добавляем статистику
from .rating import calculate_grades, format_rating_message, EXCLUSION_THRESHOLD  # Функции для расчета рейтинга

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
    'get_group_rating',
    'get_overall_rating',
    'get_user_rating_position',
    'get_top_students_by_group',
    'get_top_students_overall',
    'get_rating_statistics',
    'calculate_all_seminar_grades',
    'Lecture',
    'LectureView',
    'Question',           # Новая модель вопросов
    'UserAnswer',         # Новая модель ответов пользователей
    'SeminarStat',        # Новая статистика по семинарам
    'UserSeminarStat',    # Новая статистика пользователей по семинарам
    'calculate_grades',   # Функция для расчета оценок
    'format_rating_message',  # Функция для форматирования рейтинга
    'EXCLUSION_THRESHOLD'  # Порог исключения из расчета рейтинга
]