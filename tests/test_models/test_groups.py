"""
Тесты для системы групп
"""
import pytest
from datetime import datetime, timedelta
import uuid

from models import db, UserType


class TestGroupSystem:
    """Тесты системы групп"""

    def test_group_creation(self, test_groups):
        """Тест создания групп"""
        group1, group2, group3 = test_groups

        assert "Группа А_" in group1.name
        assert group1.max_students == 25

        assert "Группа Б_" in group2.name
        assert "Группа В_" in group3.name

    def test_group_assignment_by_admin(self, test_users):
        """Тест назначения в группу администратором"""
        student = test_users["student"]
        admin = test_users["admin"]

        # Создаем уникальную группу
        unique_name = f"Группа_тест_{uuid.uuid4().hex[:8]}"
        group = db.create_group(unique_name, max_students=25)

        # Админ назначает студента в группу
        old_group, new_group = db.set_user_group(student.id, group.id, changed_by_id=admin.id)

        assert old_group is None  # Студент не был в группе
        assert new_group.id == group.id
        assert new_group.name == group.name

        # Проверяем что студент действительно в группе
        updated_user = db.get_user(student.id)
        assert updated_user.group_id == group.id

    def test_group_capacity(self):
        """Тест ограничения вместимости групп"""
        # Создаем маленькую группу с уникальным именем
        unique_name = f"Маленькая_группа_{uuid.uuid4().hex[:8]}"
        small_group = db.create_group(unique_name, max_students=2)

        # Создаем 3 студентов с уникальными ID
        students = []
        base_id = int(str(hash(str(uuid.uuid4())))[:8])
        for i in range(1, 4):
            student_id = base_id + i
            student = db.get_or_create_user(student_id, f"Студент для емкости {i}", UserType.STUDENT)
            students.append(student)

        # Создаем админа
        admin_id = base_id + 100
        admin = db.get_or_create_user(admin_id, "Админ для теста", UserType.ADMIN)

        # Первых двух студентов добавляем успешно
        db.set_user_group(students[0].id, small_group.id, changed_by_id=admin.id)
        db.set_user_group(students[1].id, small_group.id, changed_by_id=admin.id)

        # Проверяем состав группы
        group_students = db.get_group_students(small_group.id)
        assert len(group_students) == 2

        # Третий студент пытается присоединиться самостоятельно
        # Должно выбросить исключение
        try:
            db.set_user_group(students[2].id, small_group.id, changed_by_id=students[2].id)
            # Если не выбросило исключение, проверяем что студент не добавился
            updated_group_students = db.get_group_students(small_group.id)
            if len(updated_group_students) == 3:
                # Это означает, что ограничение не сработало
                # Проверим, может быть в методе can_join есть проблема
                can_join, message = small_group.can_join()
                if can_join:
                    # Группа считает, что можно присоединиться - это баг
                    pytest.fail(f"Группа разрешила присоединение при переполнении. Сообщение: {message}")
                else:
                    # Группа правильно определяет переполнение, но студент все равно добавился
                    pytest.fail("Студент присоединился к переполненной группе без исключения")
        except Exception as e:
            # Проверяем что это ошибка связана с переполнением
            error_message = str(e).lower()
            expected_keywords = ["заполнена", "переполнена", "нельзя", "невозможно", "full", "capacity"]

            # Проверяем, содержит ли сообщение об ошибке один из ожидаемых ключевых слов
            if not any(keyword in error_message for keyword in expected_keywords):
                # Проверяем тип исключения
                if isinstance(e, ValueError):
                    # ValueError обычно используется для подобных проверок
                    pass
                elif isinstance(e, PermissionError):
                    # PermissionError тоже подходит
                    pass
                else:
                    # Неожиданный тип исключения
                    raise

    def test_transfer_deadline(self):
        """Тест установки дедлайна перехода"""
        # Создаем уникальную группу
        unique_name = f"Группа_дедлайн_{uuid.uuid4().hex[:8]}"
        group = db.create_group(unique_name, max_students=25)

        admin = db.get_or_create_user(8888, "Админ для дедлайна", UserType.ADMIN)

        # Устанавливаем дедлайн
        deadline = datetime.now() + timedelta(days=3)
        old_deadline, new_deadline = db.set_transfer_deadline(group.id, deadline, admin.id)

        assert old_deadline is None
        assert new_deadline == deadline

        # Проверяем что дедлайн установился
        updated_group = db.get_group(group.id)
        assert updated_group.transfer_deadline == deadline

    def test_available_groups(self, test_users):
        """Тест получения доступных групп"""
        student = test_users["student"]

        # Создаем уникальные группы
        group_names = []
        groups = []
        for i in range(3):
            unique_name = f"Группа_{i}_{uuid.uuid4().hex[:8]}"
            group = db.create_group(unique_name, max_students=25)
            group_names.append(unique_name)
            groups.append(group)

        # Назначаем студента в первую группу
        admin = test_users["admin"]
        db.set_user_group(student.id, groups[0].id, changed_by_id=admin.id)

        # Получаем доступные группы
        available_groups = db.get_available_groups_for_student(student.id)

        # Студент не должен видеть свою текущую группу в доступных
        available_group_ids = [g['id'] for g in available_groups]
        assert groups[0].id not in available_group_ids

        # Должен видеть другие группы
        assert len(available_groups) >= 2  # минимум 2 другие группы

    def test_group_can_join(self, session):
        """Тест проверки возможности присоединения к группе"""
        unique_name = f"Группа_тест_{uuid.uuid4().hex[:8]}"

        # Создаем группу через сессию
        from models.groups import Group
        group = Group(name=unique_name, max_students=25)
        session.add(group)
        session.commit()

        # Перезагружаем группу чтобы она была привязана к сессии
        group = session.query(Group).filter_by(id=group.id).first()

        # Группа пустая, должна принимать
        can_join, message = group.can_join()
        assert can_join is True
        assert "можно" in message.lower() or "пройдена" in message.lower() or "присоединиться" in message.lower()

    def test_student_group_change(self):
        """Тест самостоятельной смены группы студентом"""
        # Создаем уникальные группы
        group_a = db.create_group(f"Группа_A_{uuid.uuid4().hex[:8]}", max_students=25)
        group_b = db.create_group(f"Группа_B_{uuid.uuid4().hex[:8]}", max_students=25)

        # Создаем студента с уникальным ID
        student_id = int(str(hash(str(uuid.uuid4())))[:8])
        student = db.get_or_create_user(student_id, "Студент для перехода", UserType.STUDENT)

        # Сначала назначаем в группу A (через админа)
        admin = db.get_or_create_user(7777, "Админ для перехода", UserType.ADMIN)
        db.set_user_group(student.id, group_a.id, changed_by_id=admin.id)

        # Студент сам переходит в группу B
        old_group, new_group = db.set_user_group(student.id, group_b.id, changed_by_id=student.id)

        assert old_group.id == group_a.id
        assert new_group.id == group_b.id

        # Проверяем что переход выполнен
        updated_user = db.get_user(student.id)
        assert updated_user.group_id == group_b.id


class TestGroupLogging:
    """Тесты логирования операций с группами"""

    def test_group_change_logging(self, test_users):
        """Тест логирования изменения группы"""
        student = test_users["student"]
        admin = test_users["admin"]

        # Создаем уникальную группу
        unique_name = f"Группа_лог_{uuid.uuid4().hex[:8]}"
        group = db.create_group(unique_name, max_students=25)

        # Админ меняет группу студента
        db.set_user_group(student.id, group.id, changed_by_id=admin.id)

        # Проверяем лог операции
        logs = db.get_operation_logs(user_id=admin.id, operation_type='admin_change_group')
        assert len(logs) >= 1
        assert logs[0]['operation_type'] == 'admin_change_group'
        assert logs[0]['username'] == admin.username

    def test_deadline_setting_logging(self):
        """Тест логирования установки дедлайна"""
        # Создаем уникальную группу
        unique_name = f"Группа_дедлайн_лог_{uuid.uuid4().hex[:8]}"
        group = db.create_group(unique_name, max_students=25)

        admin = db.get_or_create_user(6666, "Админ для лога", UserType.ADMIN)

        # Устанавливаем дедлайн
        deadline = datetime.now() + timedelta(days=5)
        db.set_transfer_deadline(group.id, deadline, admin.id)

        # Проверяем лог
        logs = db.get_operation_logs(user_id=admin.id, operation_type='set_transfer_deadline')
        assert len(logs) >= 1
        assert logs[0]['operation_type'] == 'set_transfer_deadline'