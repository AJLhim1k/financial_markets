"""
Фикстуры для тестирования системы управления пользователями
"""
import pytest
from datetime import datetime, timedelta
import uuid
import sys
import os

# Добавляем корень проекта в путь для импортов
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from models.database_manager import db, UserType
from models.database_manager import make_seminarist, make_admin, reset_to_student


@pytest.fixture(scope="function", autouse=True)
def clean_database():
    """Очистка базы данных перед каждым тестом"""
    # Проверяем, есть ли метод drop_tables
    if hasattr(db, 'drop_tables'):
        db.drop_tables()

    # Инициализируем БД
    if hasattr(db, 'init_db'):
        db.init_db()
    elif hasattr(db, 'create_tables'):
        db.create_tables()
    elif hasattr(db, 'metadata'):
        # Включаем проверку внешних ключей для SQLite
        if hasattr(db, 'engine') and 'sqlite' in str(db.engine.url):
            from sqlalchemy import event
            from sqlalchemy.engine import Engine
            @event.listens_for(Engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        db.metadata.create_all(db.engine)

    yield


@pytest.fixture
def db_session():
    """Фикстура для получения сессии базы данных с обработкой ошибок"""
    # Пробуем разные варианты получения сессии
    if hasattr(db, 'get_session'):
        with db.get_session() as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise
            finally:
                # Не закрываем сессию здесь - она закроется в context manager
                pass
    elif hasattr(db, 'Session'):
        session = db.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    elif hasattr(db, 'session'):
        yield db.session
    else:
        # Если ничего не работает, создаем сессию напрямую
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=db.engine)
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Алиас для совместимости со старыми тестами
@pytest.fixture
def session(db_session):
    """Алиас для db_session для обратной совместимости"""
    yield db_session


@pytest.fixture
def test_users(db_session):
    """Создание тестовых пользователей"""
    unique_id = int(str(abs(hash(str(uuid.uuid4()))))[:8])  # Генерируем уникальный положительный ID

    student = db.get_or_create_user(1000 + unique_id, "Иван Петров", UserType.STUDENT)
    seminarist = db.get_or_create_user(2000 + unique_id, "Анна Семенова", UserType.SEMINARIAN)
    admin = db.get_or_create_user(3000 + unique_id, "Сергей Администратор", UserType.ADMIN)

    # Фиксируем изменения в БД
    try:
        db_session.commit()
    except:
        db_session.flush()

    return {
        "student": student,
        "seminarist": seminarist,
        "admin": admin
    }


@pytest.fixture
def test_groups(db_session):
    """Создание тестовых групп с уникальными именами"""
    groups = []
    unique_suffix = str(uuid.uuid4())[:8]  # Уникальный суффикс для имен

    for i, name in enumerate(["Группа А", "Группа Б", "Группа В"], 1):
        unique_name = f"{name}_{unique_suffix}"
        group = db.create_group(unique_name, max_students=25)
        groups.append(group)

    # Фиксируем изменения в БД
    try:
        db_session.commit()
    except:
        db_session.flush()

    return groups


@pytest.fixture
def test_students(db_session):
    """Создание дополнительных студентов"""
    students = []
    unique_id = int(str(abs(hash(str(uuid.uuid4()))))[:8])

    for i in range(3):
        student_id = 4000 + unique_id + i
        student = db.get_or_create_user(student_id, f"Студент {student_id}", UserType.STUDENT)
        students.append(student)

    # Фиксируем изменения в БД
    try:
        db_session.commit()
    except:
        db_session.flush()

    return students


@pytest.fixture
def temp_video_file():
    """Фикстура для создания временного видеофайла"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
        f.write(b"fake video content" * 100)  # Создаем "видео" файл
        temp_path = f.name

    yield temp_path

    # Удаляем временный файл после теста
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def sample_lecture_data():
    """Фикстура с тестовыми данными лекции"""
    return {
        "title": "Тестовая лекция",
        "author": "Тестовый автор",
        "lecture_date": datetime.now(),
        "file_name": "test_lecture.mp4",
        "file_path": "/uploads/test_lecture.mp4",
        "file_size": 1024 * 1024,  # 1 MB
        "duration": 3600,
        "width": 1920,
        "height": 1080,
        "description": "Тестовое описание лекции"
    }


@pytest.fixture
def create_lecture(db_session):
    """Фикстура для создания лекции в БД"""
    def _create_lecture(**kwargs):
        from models.lectures import Lecture

        # Базовые данные
        data = {
            "title": "Тестовая лекция",
            "author": "Тестовый автор",
            "lecture_date": datetime.now(),
            "file_name": "test_lecture.mp4",
            "file_path": "/uploads/test_lecture.mp4",
            "file_size": 1024 * 1024,
        }

        # Обновляем переданными параметрами
        data.update(kwargs)

        lecture = Lecture(**data)

        db_session.add(lecture)
        try:
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            raise e

        return lecture

    return _create_lecture


# Регистрируем маркер интеграции для pytest
def pytest_configure(config):
    """Регистрируем кастомные маркеры"""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"
    )