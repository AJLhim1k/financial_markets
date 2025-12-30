"""
Интеграционные тесты всей системы
"""
import pytest
from datetime import datetime, timedelta

from models import db, UserType, make_seminarist
import uuid


class TestCompleteSystem:
    """Полные интеграционные тесты системы"""

    def test_complete_user_workflow(self):
        """Полный тест рабочего процесса пользователя"""
        # Используем уникальные идентификаторы
        unique_suffix = uuid.uuid4().hex[:8]

        # 1. Создание пользователя
        user_id = int(str(hash(unique_suffix))[:8])
        user = db.get_or_create_user(user_id, f"Интеграционный тест {unique_suffix}", UserType.STUDENT)
        assert user.score == 100

        # 2. Добавление в группу
        group = db.create_group(f"Интеграционная группа {unique_suffix}", max_students=10)
        admin_id = user_id + 1000
        admin = db.get_or_create_user(admin_id, "Админ для интеграции", UserType.ADMIN)
        db.set_user_group(user.id, group.id, changed_by_id=admin.id)

        # 3. Изменение баллов
        seminarist_id = user_id + 2000
        seminarist = db.get_or_create_user(seminarist_id, f"Тестовый семинарист {unique_suffix}", UserType.SEMINARIAN)
        db.update_score(user.id, 50, changed_by_id=seminarist.id)
        assert db.get_score(user.id) == 150

        # 4. Проверка рейтинга
        position, score = db.get_user_position(user.id)
        assert score == 150

        # 5. Проверка группы
        group_students = db.get_group_students(group.id)
        assert len(group_students) >= 1
        assert any(s.id == user.id for s in group_students)

        # 6. Проверка логов
        score_logs = db.get_score_change_log(user.id)
        assert len(score_logs) >= 1
        assert score_logs[0]['delta'] == 50

    def test_multiple_operations(self, test_users, test_groups):
        """Тест множественных операций"""
        student = test_users["student"]
        seminarist = test_users["seminarist"]
        admin = test_users["admin"]
        group1, group2, _ = test_groups

        # Множественные изменения баллов
        operations = [
            (30, seminarist.id),
            (-10, admin.id),
            (25, seminarist.id),
            (15, admin.id),
        ]

        expected_score = student.score
        for delta, changer_id in operations:
            old_score, new_score = db.update_score(student.id, delta, changed_by_id=changer_id)
            assert old_score == expected_score
            expected_score = new_score

        # Проверяем итоговые баллы
        final_score = db.get_score(student.id)
        assert final_score == expected_score

        # Проверяем логи изменений (только от семинариста)
        logs = db.get_score_change_log(student.id)
        seminarist_logs = [log for log in logs if log['changer_username'] == seminarist.username]
        assert len(seminarist_logs) == 2  # Два изменения от семинариста

    def test_student_lifecycle(self):
        """Полный жизненный цикл студента"""
        # 1. Регистрация
        student = db.get_or_create_user(600, "Жизненный цикл", UserType.STUDENT)

        # 2. Запросы к системе
        for _ in range(3):
            db.register_user_request(student.id)

        assert db.get_user_requests_today(student.id) == 3

        # 3. Вступление в группу
        group = db.create_group("Группа жизненного цикла", max_students=20)
        db.set_user_group(student.id, group.id, changed_by_id=student.id)

        # 4. Получение баллов
        seminarist = db.get_or_create_user(601, "Цикловый семинарист", UserType.SEMINARIAN)
        db.update_score(student.id, 75, changed_by_id=seminarist.id)

        # 5. Просмотр рейтинга
        position, score = db.get_user_position(student.id)
        assert score == 175  # 100 + 75

        # 6. Смена группы
        new_group = db.create_group("Новая группа цикла", max_students=20)
        db.set_user_group(student.id, new_group.id, changed_by_id=student.id)

        # 7. Проверка доступных групп (не должна включать текущую)
        available_groups = db.get_available_groups_for_student(student.id)
        available_ids = [g['id'] for g in available_groups]
        assert new_group.id not in available_ids

        # 8. Повышение до семинариста
        make_seminarist(student.id)
        updated_user = db.get_user(student.id)
        assert updated_user.user_type == UserType.SEMINARIAN


    def test_error_handling(self):
        """Тест обработки ошибок"""
        # Используем уникальный идентификатор
        unique_suffix = uuid.uuid4().hex[:8]

        # Несуществующий пользователь
        non_existent_id = int(str(hash(f"nonexistent_{unique_suffix}"))[:8])
        with pytest.raises((ValueError, Exception), match="not found"):
            db.update_score(non_existent_id, 10)

        # Создаем студента и админа
        student_id = int(str(hash(f"error_student_{unique_suffix}"))[:8])
        student = db.get_or_create_user(student_id, f"Ошибочный студент {unique_suffix}", UserType.STUDENT)

        admin_id = int(str(hash(f"error_admin_{unique_suffix}"))[:8])
        admin = db.get_or_create_user(admin_id, f"Ошибочный админ {unique_suffix}", UserType.ADMIN)

        # Несуществующая группа - сначала создаем реальную группу чтобы проверить что ID 99999 не существует
        existing_group = db.create_group(f"Существующая группа {unique_suffix}", max_students=25)

        with pytest.raises((ValueError, Exception), match="not found"):
            # Используем заведомо несуществующий ID группы
            non_existent_group_id = 999999
            db.set_user_group(student.id, non_existent_group_id, changed_by_id=admin.id)

        # Переполнение группы
        small_group = db.create_group(f"Очень маленькая {unique_suffix}", max_students=1)
        db.set_user_group(student.id, small_group.id, changed_by_id=admin.id)

        another_student_id = student_id + 1
        another_student = db.get_or_create_user(another_student_id, f"Другой студент {unique_suffix}", UserType.STUDENT)

        with pytest.raises((ValueError, Exception), match="Группа заполнена|переполнена|нельзя"):
            db.set_user_group(another_student.id, small_group.id, changed_by_id=another_student.id)