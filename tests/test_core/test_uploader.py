# tests/test_lecture_manager.py
from pathlib import Path

import pytest
import tempfile
import shutil
from datetime import datetime
from io import BytesIO
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.base import Base
from models.lectures import Lecture
from core.lecture_manager import LectureManager


class TestLectureManager:
    """Интеграционные тесты для LectureManager"""

    @pytest.fixture
    def db_session(self):
        """Фикстура: тестовая сессия БД"""
        # Создаем БД в памяти
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        yield session

        session.close()

    @pytest.fixture
    def temp_dir(self):
        """Фикстура: временная директория"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def manager(self, db_session, temp_dir):
        """Фикстура: менеджер лекций"""
        return LectureManager(db_session=db_session, upload_dir=temp_dir)

    @pytest.fixture
    def fake_video_stream(self):
        """Фикстура: фейковый видео поток"""
        stream = BytesIO(b"fake video content" * 1000)
        stream.name = "lecture.mp4"
        return stream

    def test_upload_lecture_success(self, manager, fake_video_stream):
        """Тест: успешная загрузка лекции"""
        result = manager.upload_lecture(
            file_stream=fake_video_stream,
            original_filename="lecture.mp4",
            title="Тестовая лекция",
            author="Тестер",
            lecture_date=datetime.now(),
            description="Описание",
            category="Тест",
            is_public=True
        )

        assert result['success'] is True
        assert 'lecture_id' in result
        assert result['lecture']['title'] == "Тестовая лекция"
        assert result['lecture']['author'] == "Тестер"

        # Проверяем что запись создалась в БД
        lecture = manager.get_lecture_by_id(result['lecture_id'])
        assert lecture is not None
        assert lecture.title == "Тестовая лекция"
        assert lecture.author == "Тестер"
        assert lecture.file_name.endswith('.mp4')
        assert lecture.file_size > 0

    def test_upload_lecture_default_date(self, manager, fake_video_stream):
        """Тест: загрузка с датой по умолчанию"""
        result = manager.upload_lecture(
            file_stream=fake_video_stream,
            original_filename="lecture.mp4",
            title="Лекция без даты",
            author="Автор"
        )

        assert result['success'] is True
        lecture = manager.get_lecture_by_id(result['lecture_id'])
        assert lecture.lecture_date is not None

    def test_upload_lecture_rollback_on_error(self, manager, fake_video_stream, temp_dir):
        """Тест: откат при ошибке"""

        # Мокаем ошибку БД
        class MockDB:
            def add(self, *args, **kwargs):
                raise Exception("DB error")

        manager.db = MockDB()

        with pytest.raises(Exception, match="DB error"):
            manager.upload_lecture(
                file_stream=fake_video_stream,
                original_filename="lecture.mp4",
                title="Лекция с ошибкой",
                author="Автор"
            )

        # Проверяем что файл удален (откат)
        files = list(Path(temp_dir).glob("*.mp4"))
        assert len(files) == 0

    def test_generate_slug(self, manager):
        """Тест: генерация slug"""
        slug = manager._generate_slug("Тестовая Лекция по Python 2024!")

        assert "тестовая-лекция-по-python-2024" in slug
        assert slug.endswith(datetime.now().strftime("%Y%m%d%H%M"))
        assert "--" not in slug  # Нет двойных дефисов

    def test_list_lectures(self, manager, fake_video_stream):
        """Тест: получение списка лекций"""
        # Загружаем несколько лекций
        for i in range(5):
            stream = BytesIO(f"video {i}".encode() * 1000)
            stream.name = f"lecture{i}.mp4"

            manager.upload_lecture(
                file_stream=stream,
                original_filename=f"lecture{i}.mp4",
                title=f"Лекция {i}",
                author=f"Автор {i}",
                category="Математика" if i % 2 == 0 else "Физика"
            )

        # Получаем все лекции
        all_lectures = manager.list_lectures()
        assert len(all_lectures) == 5

        # Фильтрация по категории
        math_lectures = manager.list_lectures(category="Математика")
        assert len(math_lectures) == 3  # 0, 2, 4

        physics_lectures = manager.list_lectures(category="Физика")
        assert len(physics_lectures) == 2  # 1, 3

        # Пагинация
        limited = manager.list_lectures(limit=2)
        assert len(limited) == 2

    def test_delete_lecture(self, manager, fake_video_stream):
        """Тест: удаление лекции"""
        # Загружаем лекцию
        result = manager.upload_lecture(
            file_stream=fake_video_stream,
            original_filename="lecture.mp4",
            title="Лекция для удаления",
            author="Автор"
        )

        lecture_id = result['lecture_id']
        lecture = manager.get_lecture_by_id(lecture_id)
        file_path = Path(lecture.file_path)

        # Проверяем что файл существует
        assert file_path.exists()

        # Удаляем
        success = manager.delete_lecture(lecture_id)
        assert success is True

        # Проверяем что лекция удалена из БД
        deleted_lecture = manager.get_lecture_by_id(lecture_id)
        assert deleted_lecture is None

        # Проверяем что файл удален
        assert not file_path.exists()

    def test_delete_nonexistent_lecture(self, manager):
        """Тест: удаление несуществующей лекции"""
        success = manager.delete_lecture(99999)
        assert success is False