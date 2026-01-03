"""
Тесты для системы пользователей и баллов
"""
import pytest
from datetime import datetime
import uuid

from models import db, UserType, make_seminarist, make_admin, reset_to_student


class TestUserSystem:
    """Тесты системы пользователей"""

    def test_create_users(self, test_users):
        """Тест создания пользователей разных типов"""
        student = test_users["student"]
        seminarist = test_users["seminarist"]
        admin = test_users["admin"]

        assert student.username == "Иван Петров"
        assert student.user_type.value == "student"
        assert student.score == 100

        assert seminarist.username == "Анна Семенова"
        assert seminarist.user_type.value == "seminarist"

        assert admin.username == "Сергей Администратор"
        assert admin.user_type.value == "admin"

    def test_user_type_changes(self):
        """Тест изменения типа пользователя"""
        # Создаем студента с уникальным ID
        student_id = int(str(hash(str(uuid.uuid4())))[:8])
        student = db.get_or_create_user(student_id, "Тестовый студент", UserType.STUDENT)
        assert student.user_type == UserType.STUDENT

        # Делаем семинаристом
        make_seminarist(student_id)
        updated_user = db.get_user(student_id)
        assert updated_user.user_type == UserType.SEMINARIAN

        # Делаем админом
        make_admin(student_id)
        updated_user = db.get_user(student_id)
        assert updated_user.user_type == UserType.ADMIN

        # Возвращаем в студенты
        reset_to_student(student_id)
        updated_user = db.get_user(student_id)
        assert updated_user.user_type == UserType.STUDENT

    def test_score_management(self, test_users):
        """Тест управления баллами"""
        student = test_users["student"]
        seminarist = test_users["seminarist"]
        admin = test_users["admin"]

        # Начальные баллы
        initial_score = db.get_score(student.id)
        assert initial_score == 100

        # Семинарист добавляет баллы
        old_score, new_score = db.update_score(student.id, 50, changed_by_id=seminarist.id)
        assert old_score == 100
        assert new_score == 150

        # Админ убирает баллы
        old_score, new_score = db.update_score(student.id, -30, changed_by_id=admin.id)
        assert old_score == 150
        assert new_score == 120

        # Проверяем текущие баллы
        current_score = db.get_score(student.id)
        assert current_score == 120

    def test_user_permissions(self, test_users):
        """Тест проверки прав пользователей"""
        student = test_users["student"]
        seminarist = test_users["seminarist"]
        admin = test_users["admin"]

        # Семинарист может менять баллы
        assert seminarist.can_change_score(student) is True

        # Админ может менять баллы
        assert admin.can_change_score(student) is True

        # Студент НЕ может менять баллы
        assert student.can_change_score(seminarist) is False

    def test_rating_system(self):
        """Тест системы рейтинга"""
        # Создаем несколько студентов с разными баллами и уникальными ID
        base_id = int(str(hash(str(uuid.uuid4())))[:8])

        student1 = db.get_or_create_user(base_id + 1, "Топ студент", UserType.STUDENT)
        db.update_score(student1.id, 200)  # 300 баллов

        student2 = db.get_or_create_user(base_id + 2, "Средний студент", UserType.STUDENT)
        db.update_score(student2.id, 100)  # 200 баллов

        student3 = db.get_or_create_user(base_id + 3, "Начинающий", UserType.STUDENT)
        # 100 баллов по умолчанию

        # Тестируем топ игроков
        top_players = db.get_top_players(limit=3)
        # Может быть больше студентов из других тестов, но проверяем что наш топ студент в списке
        top_names = [p['username'] for p in top_players]
        assert "Топ студент" in top_names

        # Тестируем позицию в рейтинге
        position, score = db.get_user_position(student1.id)
        assert score == 300

        # Тестируем полный рейтинг
        full_rating = db.get_full_rating()
        assert len(full_rating) >= 3  # Минимум 3 студента

    def test_request_counter(self):
        """Тест счетчика запросов"""
        # Используем уникальный ID
        user_id = int(str(hash(str(uuid.uuid4())))[:8])
        user = db.get_or_create_user(user_id, "Тест запросов", UserType.STUDENT)

        # Регистрируем запросы
        db.register_user_request(user_id)
        db.register_user_request(user_id)

        # Проверяем количество запросов
        requests = db.get_user_requests_today(user_id)
        assert requests == 2

        # Проверяем лимит запросов
        remaining = db.can_user_request(user_id, max_attempts=5)
        assert remaining == 3  # 5 - 2 = 3


class TestScoreLogging:
    """Тесты логирования изменений баллов"""

    def test_score_log_creation(self, test_users):
        """Тест создания логов при изменении баллов"""
        student = test_users["student"]
        seminarist = test_users["seminarist"]

        # Изменяем баллы семинаристом (должен создаться лог)
        db.update_score(student.id, 25, changed_by_id=seminarist.id)

        # Проверяем лог
        logs = db.get_score_change_log(student.id)
        assert len(logs) >= 1

        last_log = logs[0]
        assert last_log['user_username'] == student.username
        assert last_log['changer_username'] == seminarist.username
        assert last_log['delta'] == 25

    def test_admin_no_score_log(self, test_users):
        """Тест что админ не создает логов изменений баллов"""
        student = test_users["student"]
        admin = test_users["admin"]

        # Запоминаем текущее количество логов
        logs_before = db.get_score_change_log(student.id)

        # Админ изменяет баллы (не должно создавать лог)
        db.update_score(student.id, 50, changed_by_id=admin.id)

        # Проверяем что количество логов не изменилось
        logs_after = db.get_score_change_log(student.id)
        # У админов логирование отключено, поэтому количество логов не должно измениться
        assert len(logs_after) == len(logs_before)

    def test_operation_logs(self, test_users):
        """Тест логов операций"""
        admin = test_users["admin"]

        # Админ выполняет операцию
        db.log_operation(admin.id, "test_operation")

        # Проверяем лог
        logs = db.get_operation_logs(user_id=admin.id, operation_type="test_operation")
        assert len(logs) >= 1
        assert logs[0]['operation_type'] == "test_operation"
        assert logs[0]['username'] == admin.username