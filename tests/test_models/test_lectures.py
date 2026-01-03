import os
import tempfile
import pytest
from sqlalchemy import text
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from models.lectures import Lecture, LectureView


class TestLectureModel:
    """Тесты для модели Lecture"""

    def test_lecture_creation(self, db_session):
        """Тест создания лекции с минимальными данными"""
        lecture = Lecture(
            title="Введение в Python",
            author="Иван Иванов",
            lecture_date=datetime.now(),
            file_name="intro.mp4",
            file_path="/uploads/lectures/intro.mp4",
            file_size=1024 * 1024,  # 1 MB
        )

        db_session.add(lecture)
        db_session.commit()

        assert lecture.id is not None
        assert lecture.title == "Введение в Python"
        assert lecture.author == "Иван Иванов"
        assert lecture.file_name == "intro.mp4"
        assert lecture.file_size == 1024 * 1024
        assert lecture.is_public is True  # default
        assert lecture.is_processed is False  # default
        assert lecture.created_at is not None
        assert lecture.updated_at is not None

    def test_lecture_creation_full(self, db_session):
        """Тест создания лекции со всеми полями"""
        lecture = Lecture(
            title="Продвинутый Python",
            author="Петр Петров",
            lecture_date=datetime.now() - timedelta(days=7),
            file_name="advanced_python.mp4",
            file_path="/uploads/lectures/advanced_python.mp4",
            file_size=500 * 1024 * 1024,  # 500 MB
            file_type="video/mp4",
            duration=3600,  # 1 час
            width=1920,
            height=1080,
            bitrate=5000,
            description="Продвинутые темы Python: асинхронность, метаклассы, оптимизация",
            thumbnail_path="/uploads/thumbnails/advanced_python.jpg",
            is_processed=True,
            is_public=True,
            slug="advanced-python",
            category="Programming"
        )

        db_session.add(lecture)
        db_session.commit()

        assert lecture.id is not None
        assert lecture.duration == 3600
        assert lecture.width == 1920
        assert lecture.height == 1080
        assert lecture.bitrate == 5000
        assert lecture.description is not None
        assert lecture.slug == "advanced-python"
        assert lecture.category == "Programming"

    def test_required_fields(self, db_session):
        """Тест, что обязательные поля действительно обязательны"""
        lecture = Lecture()  # Все поля пустые

        db_session.add(lecture)

        with pytest.raises(IntegrityError):
            db_session.commit()  # Только commit, без try-except

        # Важно: после ошибки делаем rollback
        db_session.rollback()

    def test_file_path_validation_valid(self, db_session):
        """Тест валидации корректных путей к файлам"""
        valid_paths = [
            "/uploads/lectures/video.mp4",
            "/var/www/videos/lecture.webm",
            "C:\\videos\\lecture.mov",
            "relative/path/video.avi",
            "test.mkv"
        ]

        for file_path in valid_paths:
            lecture = Lecture(
                title="Тест",
                author="Автор",
                lecture_date=datetime.now(),
                file_name="test.mp4",
                file_path=file_path,
                file_size=1000
            )

            # Валидация должна пройти без ошибок
            lecture.validate_file_path('file_path', file_path)

    def test_file_path_validation_invalid(self):
        """Тест валидации некорректных путей к файлам"""
        invalid_paths = [
            "/uploads/lectures/video.txt",
            "/var/www/videos/lecture.pdf",
            "C:\\videos\\lecture.exe",
            "test.jpg",
            "document.docx"
        ]

        lecture = Lecture(
            title="Тест",
            author="Автор",
            lecture_date=datetime.now(),
            file_name="test.mp4",
            file_path="/uploads/test.mp4",
            file_size=1000
        )

        for file_path in invalid_paths:
            with pytest.raises(ValueError, match="Недопустимое расширение файла"):
                lecture.validate_file_path('file_path', file_path)

    def test_file_exists_property(self, db_session, tmpdir):
        """Тест свойства file_exists"""
        # Создаем временный файл
        temp_file = tmpdir.join("test_video.mp4")
        temp_file.write(b"fake video content")

        lecture = Lecture(
            title="Тестовое видео",
            author="Тестер",
            lecture_date=datetime.now(),
            file_name="test_video.mp4",
            file_path=str(temp_file),
            file_size=len(b"fake video content")
        )

        assert lecture.file_exists is True

        # Тест с несуществующим файлом
        lecture.file_path = "/nonexistent/path/video.mp4"
        assert lecture.file_exists is False

    def test_file_extension_property(self, db_session):
        """Тест свойства file_extension"""
        test_cases = [
            ("video.mp4", ".mp4"),
            ("lecture.WEBM", ".webm"),
            ("test.Mp4", ".mp4"),
            ("file_without_extension", ""),
            (None, ""),
        ]

        for file_name, expected_extension in test_cases:
            lecture = Lecture(
                title="Тест",
                author="Автор",
                lecture_date=datetime.now(),
                file_name=file_name,
                file_path="/uploads/test.mp4",
                file_size=1000
            )

            assert lecture.file_extension == expected_extension

    def test_human_file_size_property(self, db_session):
        """Тест свойства human_file_size"""
        test_cases = [
            (500, "500.0 B"),
            (1024, "1.0 KB"),  # 1 KB
            (1024 * 1024, "1.0 MB"),  # 1 MB
            (1024 * 1024 * 1024, "1.0 GB"),  # 1 GB
            (None, "Неизвестно"),
        ]

        for file_size, expected in test_cases:
            lecture = Lecture(
                title="Тест",
                author="Автор",
                lecture_date=datetime.now(),
                file_name="test.mp4",
                file_path="/uploads/test.mp4",
                file_size=file_size
            )

            assert lecture.human_file_size == expected

    def test_video_info_property(self, db_session):
        """Тест свойства video_info"""
        lecture = Lecture(
            title="Тест",
            author="Автор",
            lecture_date=datetime.now(),
            file_name="test.mp4",
            file_path="/uploads/test.mp4",
            file_size=1000,
            duration=3600,
            width=1920,
            height=1080,
            bitrate=5000
        )

        video_info = lecture.video_info
        assert video_info["duration"] == 3600
        assert video_info["resolution"] == "1920x1080"
        assert video_info["bitrate"] == 5000

        # Тест без метаданных
        lecture2 = Lecture(
            title="Тест2",
            author="Автор2",
            lecture_date=datetime.now(),
            file_name="test2.mp4",
            file_path="/uploads/test2.mp4",
            file_size=1000
        )

        video_info2 = lecture2.video_info
        assert video_info2["duration"] is None
        assert video_info2["resolution"] is None
        assert video_info2["bitrate"] is None

    def test_to_dict_method(self, db_session):
        """Тест метода to_dict"""
        lecture_date = datetime(2024, 1, 15, 14, 30)

        lecture = Lecture(
            title="Введение в AI",
            author="Алексей Смирнов",
            lecture_date=lecture_date,
            file_name="ai_intro.mp4",
            file_path="/uploads/lectures/ai_intro.mp4",
            file_size=250 * 1024 * 1024,  # 250 MB
            duration=2700,  # 45 минут
            description="Введение в искусственный интеллект",
            thumbnail_path="/uploads/thumbnails/ai_intro.jpg",
            is_processed=True,
            is_public=True
        )

        db_session.add(lecture)
        db_session.commit()

        # Без видео URL
        data = lecture.to_dict()
        assert data["id"] == lecture.id
        assert data["title"] == "Введение в AI"
        assert data["author"] == "Алексей Смирнов"
        assert data["lecture_date"] == "2024-01-15T14:30:00"
        assert data["description"] == "Введение в искусственный интеллект"
        assert data["file_name"] == "ai_intro.mp4"
        assert data["file_size"] == "250.0 MB"
        assert data["duration"] == 2700
        assert data["thumbnail_url"] == f"/api/lectures/{lecture.id}/thumbnail"
        assert data["is_processed"] is True
        assert data["is_public"] is True
        assert "video_url" not in data
        assert "video_download_url" not in data

        # С видео URL
        data_with_urls = lecture.to_dict(include_video_url=True)
        assert data_with_urls["video_url"] == f"/api/lectures/{lecture.id}/stream"
        assert data_with_urls["video_download_url"] == f"/api/lectures/{lecture.id}/download"

    def test_get_video_stream_range(self, db_session, tmpdir):
        """Тест метода get_video_stream_range"""
        # Создаем временный файл
        temp_file = tmpdir.join("stream_test.mp4")
        content = b"fake video data" * 100
        temp_file.write(content)
        file_size = len(content)

        lecture = Lecture(
            title="Стриминг тест",
            author="Тестер",
            lecture_date=datetime.now(),
            file_name="stream_test.mp4",
            file_path=str(temp_file),
            file_size=file_size,
            file_type="video/mp4"
        )

        stream_info = lecture.get_video_stream_range()
        assert stream_info is not None
        assert stream_info["file_path"] == str(temp_file)
        assert stream_info["file_size"] == file_size
        assert stream_info["content_type"] == "video/mp4"

        # Тест с отсутствующим файлом
        lecture.file_path = "/nonexistent/path/video.mp4"
        assert lecture.get_video_stream_range() is None

        # Тест с автоматическим определением размера
        lecture.file_path = str(temp_file)
        lecture.file_size = None
        stream_info2 = lecture.get_video_stream_range()
        assert stream_info2["file_size"] == file_size

    def test_get_video_stream_range_auto_mime(self, db_session, tmpdir):
        """Тест автоматического определения MIME-типа"""
        temp_file = tmpdir.join("video.webm")
        temp_file.write(b"fake webm video")

        lecture = Lecture(
            title="WebM тест",
            author="Тестер",
            lecture_date=datetime.now(),
            file_name="video.webm",
            file_path=str(temp_file),
            file_size=1000,
            file_type=None  # Не указан
        )

        stream_info = lecture.get_video_stream_range()
        assert "video/webm" in stream_info["content_type"]

    def test_repr_method(self, db_session):
        """Тест метода __repr__"""
        lecture = Lecture(
            title="Тестовая лекция",
            author="Тест Автор",
            lecture_date=datetime.now(),
            file_name="test.mp4",
            file_path="/uploads/test.mp4",
            file_size=1000
        )

        db_session.add(lecture)
        db_session.commit()

        repr_str = repr(lecture)
        assert f"id={lecture.id}" in repr_str
        assert "title='Тестовая лекция'" in repr_str
        assert "author='Тест Автор'" in repr_str

    def test_unique_slug(self, db_session):
        """Тест уникальности slug"""
        lecture1 = Lecture(
            title="Лекция 1",
            author="Автор",
            lecture_date=datetime.now(),
            file_name="lecture1.mp4",
            file_path="/uploads/lecture1.mp4",
            file_size=1000,
            slug="python-intro"
        )

        lecture2 = Lecture(
            title="Лекция 2",
            author="Автор",
            lecture_date=datetime.now(),
            file_name="lecture2.mp4",
            file_path="/uploads/lecture2.mp4",
            file_size=1000,
            slug="python-intro"  # Дублирующий slug
        )

        db_session.add(lecture1)
        db_session.commit()

        db_session.add(lecture2)

        with pytest.raises(IntegrityError):
            db_session.commit()  # Только commit, без flush

        # После ошибки делаем rollback
        db_session.rollback()

    def test_indexes(self, db_session):
        """Тест, что индексы работают корректно"""
        # Создаем несколько лекций для тестирования поиска
        lectures = []
        for i in range(5):
            lecture = Lecture(
                title=f"Лекция {i}",
                author=f"Автор {i % 2}",
                lecture_date=datetime.now() - timedelta(days=i),
                file_name=f"lecture_{i}.mp4",
                file_path=f"/uploads/lecture_{i}.mp4",
                file_size=1000 * (i + 1),
                category="Programming" if i % 2 == 0 else "Math"
            )
            lectures.append(lecture)
            db_session.add(lecture)

        db_session.commit()

        # Тестируем поиск по title (должен использовать индекс)
        found = db_session.query(Lecture).filter(Lecture.title == "Лекция 2").first()
        assert found is not None

        # Тестируем поиск по author
        author_lectures = db_session.query(Lecture).filter(Lecture.author == "Автор 0").all()
        assert len(author_lectures) == 3  # Должно быть 3 лекции

        # Тестируем поиск по category
        programming_lectures = db_session.query(Lecture).filter(Lecture.category == "Programming").all()
        assert len(programming_lectures) == 3


class TestLectureViewModel:
    """Тесты для модели LectureView"""

    def test_lecture_view_creation(self, db_session):
        """Тест создания записи о просмотре"""
        # Сначала создаем лекцию
        lecture = Lecture(
            title="Тестовая лекция",
            author="Автор",
            lecture_date=datetime.now(),
            file_name="test.mp4",
            file_path="/uploads/test.mp4",
            file_size=1000
        )
        db_session.add(lecture)
        db_session.commit()

        # Создаем запись о просмотре
        view = LectureView(
            lecture_id=lecture.id,
            user_id=1,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            watch_duration=300,  # 5 минут
            completed=False
        )

        db_session.add(view)
        db_session.commit()

        assert view.id is not None
        assert view.lecture_id == lecture.id
        assert view.user_id == 1
        assert view.ip_address == "192.168.1.1"
        assert view.user_agent == "Mozilla/5.0"
        assert view.watch_duration == 300
        assert view.completed is False
        assert view.watched_at is not None

    def test_lecture_view_creation_minimal(self, db_session):
        """Тест создания записи о просмотре с минимальными данными"""
        # Сначала создаем лекцию
        lecture = Lecture(
            title="Минимальная лекция",
            author="Автор",
            lecture_date=datetime.now(),
            file_name="min.mp4",
            file_path="/uploads/min.mp4",
            file_size=1000
        )
        db_session.add(lecture)
        db_session.commit()

        # Создаем запись о просмотре только с обязательными полями
        view = LectureView(
            lecture_id=lecture.id
        )

        db_session.add(view)
        db_session.commit()

        assert view.id is not None
        assert view.lecture_id == lecture.id
        assert view.user_id is None
        assert view.ip_address is None
        assert view.user_agent is None
        assert view.watch_duration == 0  # default
        assert view.completed is False  # default
        assert view.watched_at is not None

    def test_lecture_view_foreign_key(self, db_session):
        """Тест внешнего ключа lecture_id"""
        # Для SQLite foreign keys часто отключены по умолчанию
        # Проверим, работают ли они
        if hasattr(db_session.bind, 'url') and 'sqlite' in str(db_session.bind.url):
            # Создадим тестовую запись для проверки
            test_lecture = Lecture(
                title="Тест для проверки FK",
                author="Автор",
                lecture_date=datetime.now(),
                file_name="test.mp4",
                file_path="/uploads/test.mp4",
                file_size=1000
            )
            db_session.add(test_lecture)
            db_session.commit()
            test_id = test_lecture.id

            # Создаем валидную запись
            valid_view = LectureView(lecture_id=test_id)
            db_session.add(valid_view)

            try:
                db_session.commit()
                # Если это сработало, создадим невалидную
                db_session.rollback()

                invalid_view = LectureView(lecture_id=99999)
                db_session.add(invalid_view)

                try:
                    db_session.commit()
                    # Если commit прошел, значит FK не работают
                    # Удалим ошибочную запись
                    db_session.delete(invalid_view)
                    db_session.commit()

                    # Пропускаем тест
                    pytest.skip("SQLite foreign keys отключены, тест пропущен")

                except IntegrityError:
                    # FK работают - это хорошо!
                    db_session.rollback()
                    assert True, "Foreign keys работают корректно"

            finally:
                # Очистка
                db_session.rollback()
                if test_lecture.id:
                    db_session.delete(test_lecture)
                    db_session.commit()

        else:
            # Для других БД (PostgreSQL, MySQL) тест должен работать
            view = LectureView(lecture_id=99999)
            db_session.add(view)

            with pytest.raises(IntegrityError):
                db_session.commit()

            db_session.rollback()

    def test_lecture_view_completed(self, db_session):
        """Тест поля completed"""
        # Создаем лекцию
        lecture = Lecture(
            title="Лекция для теста завершения",
            author="Автор",
            lecture_date=datetime.now(),
            file_name="complete.mp4",
            file_path="/uploads/complete.mp4",
            file_size=1000,
            duration=600  # 10 минут
        )
        db_session.add(lecture)
        db_session.commit()

        # Создаем запись о НЕзавершенном просмотре
        view_incomplete = LectureView(
            lecture_id=lecture.id,
            watch_duration=300,  # 5 из 10 минут
            completed=False
        )

        # Создаем запись о завершенном просмотре
        view_complete = LectureView(
            lecture_id=lecture.id,
            watch_duration=600,  # все 10 минут
            completed=True
        )

        db_session.add_all([view_incomplete, view_complete])
        db_session.commit()

        # Проверяем запросы
        incomplete_views = db_session.query(LectureView).filter(
            LectureView.lecture_id == lecture.id,
            LectureView.completed == False
        ).all()

        complete_views = db_session.query(LectureView).filter(
            LectureView.lecture_id == lecture.id,
            LectureView.completed == True
        ).all()

        assert len(incomplete_views) == 1
        assert len(complete_views) == 1
        assert incomplete_views[0].watch_duration == 300
        assert complete_views[0].watch_duration == 600


class TestLectureRelationships:
    """Тесты связей между моделями"""

    def test_lecture_with_multiple_views(self, db_session):
        """Тест, что у одной лекции может быть много просмотров"""
        lecture = Lecture(
            title="Популярная лекция",
            author="Известный автор",
            lecture_date=datetime.now(),
            file_name="popular.mp4",
            file_path="/uploads/popular.mp4",
            file_size=1000
        )
        db_session.add(lecture)
        db_session.commit()

        # Создаем несколько просмотров
        views = []
        for i in range(5):
            view = LectureView(
                lecture_id=lecture.id,
                user_id=i + 1,
                ip_address=f"192.168.1.{i + 1}",
                watch_duration=i * 100
            )
            views.append(view)
            db_session.add(view)

        db_session.commit()

        # Получаем все просмотры для этой лекции
        lecture_views = db_session.query(LectureView).filter(
            LectureView.lecture_id == lecture.id
        ).all()

        assert len(lecture_views) == 5
        for i, view in enumerate(lecture_views):
            assert view.user_id == i + 1
            assert view.watch_duration == i * 100

    def test_cascade_delete(self, db_session):
        """Тест каскадного удаления (если настроено)"""
        # Зависит от настроек БД
        # Обычно просмотры не удаляются каскадно

        lecture = Lecture(
            title="Лекция для удаления",
            author="Автор",
            lecture_date=datetime.now(),
            file_name="delete.mp4",
            file_path="/uploads/delete.mp4",
            file_size=1000
        )
        db_session.add(lecture)
        db_session.commit()

        # Создаем просмотр
        view = LectureView(
            lecture_id=lecture.id,
            user_id=1
        )
        db_session.add(view)
        db_session.commit()

        view_id = view.id

        # Удаляем лекцию
        db_session.delete(lecture)
        db_session.commit()

        # Проверяем, что просмотр остался (если нет каскадного удаления)
        remaining_view = db_session.query(LectureView).filter(LectureView.id == view_id).first()
        # Это зависит от настроек БД, обычно NOT NULL constraint нарушится
        # при попытке создать просмотр без лекции, но существующие могут остаться


@pytest.mark.integration
class TestLectureIntegration:
    """Интеграционные тесты для Lecture"""

    def test_full_lecture_lifecycle(self, db_session, tmpdir):
        """Полный жизненный цикл лекции: создание, обновление, удаление"""
        # 1. Создание
        temp_file = tmpdir.join("lifecycle.mp4")
        temp_file.write(b"video content")

        lecture = Lecture(
            title="Жизненный цикл",
            author="Интеграционный тест",
            lecture_date=datetime.now(),
            file_name="lifecycle.mp4",
            file_path=str(temp_file),
            file_size=len(b"video content"),
            description="Тестовая лекция"
        )

        db_session.add(lecture)
        db_session.commit()
        lecture_id = lecture.id

        # 2. Чтение
        saved_lecture = db_session.query(Lecture).filter(Lecture.id == lecture_id).first()
        assert saved_lecture is not None
        assert saved_lecture.title == "Жизненный цикл"
        assert saved_lecture.file_exists is True

        # 3. Обновление
        saved_lecture.title = "Обновленное название"
        saved_lecture.description = "Обновленное описание"
        saved_lecture.is_processed = True
        db_session.commit()

        # Проверяем обновление
        updated_lecture = db_session.query(Lecture).filter(Lecture.id == lecture_id).first()
        assert updated_lecture.title == "Обновленное название"
        assert updated_lecture.description == "Обновленное описание"
        assert updated_lecture.is_processed is True
        assert updated_lecture.updated_at >= updated_lecture.created_at

        # 4. Удаление
        db_session.delete(updated_lecture)
        db_session.commit()

        # Проверяем удаление
        deleted_lecture = db_session.query(Lecture).filter(Lecture.id == lecture_id).first()
        assert deleted_lecture is None

    def test_lecture_statistics(self, db_session):
        """Тест статистики по лекциям"""
        # Создаем несколько лекций с просмотрами
        lectures = []
        for i in range(3):
            lecture = Lecture(
                title=f"Лекция для статистики {i}",
                author="Автор",
                lecture_date=datetime.now(),
                file_name=f"stats_{i}.mp4",
                file_path=f"/uploads/stats_{i}.mp4",
                file_size=1000,
                duration=600  # 10 минут
            )
            lectures.append(lecture)
            db_session.add(lecture)

        db_session.commit()

        # Создаем просмотры
        views_data = [
            (lectures[0].id, 600, True),  # Полностью просмотрена
            (lectures[0].id, 300, False),  # Просмотрена наполовину
            (lectures[1].id, 100, False),  # Только начата
            (lectures[2].id, 600, True),  # Полностью просмотрена
            (lectures[2].id, 600, True),  # Еще раз полностью
        ]

        for lecture_id, duration, completed in views_data:
            view = LectureView(
                lecture_id=lecture_id,
                watch_duration=duration,
                completed=completed
            )
            db_session.add(view)

        db_session.commit()

        # Тестируем агрегатные запросы
        from sqlalchemy import func

        # Количество просмотров по лекциям
        view_counts = db_session.query(
            LectureView.lecture_id,
            func.count(LectureView.id).label('view_count')
        ).group_by(LectureView.lecture_id).all()

        view_count_dict = dict(view_counts)
        assert view_count_dict[lectures[0].id] == 2
        assert view_count_dict[lectures[1].id] == 1
        assert view_count_dict[lectures[2].id] == 2

        # Средняя продолжительность просмотра
        avg_duration = db_session.query(
            LectureView.lecture_id,
            func.avg(LectureView.watch_duration).label('avg_duration')
        ).group_by(LectureView.lecture_id).all()

        avg_dict = dict(avg_duration)
        assert avg_dict[lectures[0].id] == 450.0  # (600 + 300) / 2
        assert avg_dict[lectures[1].id] == 100.0
        assert avg_dict[lectures[2].id] == 600.0