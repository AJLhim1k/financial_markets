# core/lecture_manager.py (ПОЛНАЯ ПРОДАКШЕН ВЕРСИЯ)
from datetime import datetime
from typing import Optional, Dict, Union
from pathlib import Path
import re
import threading
import logging
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.lectures import Lecture
from .uploader import VideoUploader
from .video_processor import SimpleVideoProcessor

logger = logging.getLogger(__name__)


class LectureManager:
    """
    Менеджер для работы с лекциями
    Связывает аплоадер, процессор и модель БД
    """

    def __init__(self, db_session: Session, upload_dir: str = "records"):
        self.db = db_session
        self.engine = db_session.get_bind() if hasattr(db_session, 'get_bind') else None
        self.uploader = VideoUploader(upload_dir)
        self.processor = SimpleVideoProcessor()

    def upload_lecture(
            self,
            file_stream,
            original_filename: str,
            title: str,
            author: str,
            lecture_date: datetime = None,
            description: Optional[str] = None,
            category: Optional[str] = None,
            is_public: bool = True,
            **kwargs  # ← Принимаем дополнительные параметры
    ) -> Dict:
        """
        Полный цикл загрузки лекции

        Args:
            file_stream: Поток с файлом
            original_filename: Исходное имя файла
            title: Название лекции
            author: Автор
            lecture_date: Дата лекции
            description: Описание
            category: Категория
            is_public: Публичная ли лекция
            **kwargs: Дополнительные параметры
                - background_processing: bool (True по умолчанию)
                - immediate_thumbnail: bool (создать превью сразу, для тестов)
        """
        # Если дата не указана - используем текущую
        if lecture_date is None:
            lecture_date = datetime.now()

        # Настройки из kwargs
        background_processing = kwargs.get('background_processing', True)
        immediate_thumbnail = kwargs.get('immediate_thumbnail', False)

        # 1. Сохраняем файл на диск
        file_info = self.uploader.save_from_stream(file_stream, original_filename)

        try:
            # 2. Получаем базовую информацию о видео
            video_info = self.processor.get_basic_info(file_info['original_path'])

            # 3. Создаем запись в БД
            lecture = Lecture(
                title=title,
                author=author,
                lecture_date=lecture_date,
                description=description,
                category=category,
                is_public=is_public,

                # Информация о файле
                file_name=file_info['filename'],
                file_path=file_info['original_path'],
                file_size=file_info['size_bytes'],
                file_type=file_info['mime_type'],

                # Метаданные видео
                duration=int(video_info.get('duration_seconds', 0)) if video_info.get('duration_seconds') else None,

                # Генерация slug
                slug=self._generate_slug(title),

                # created_at и updated_at установятся автоматически через default
            )

            self.db.add(lecture)
            self.db.commit()
            self.db.refresh(lecture)

            # 4. Создаем превью (если нужно сразу)
            thumbnail_path = None
            if immediate_thumbnail:
                thumbnail_path = self._create_thumbnail_sync(
                    lecture_id=lecture.id,
                    video_path=file_info['original_path']
                )

                if thumbnail_path:
                    lecture.thumbnail_path = thumbnail_path
                    lecture.is_processed = True
                    self.db.commit()

            # 5. Запускаем фоновую обработку (если не создали сразу)
            elif background_processing:
                self._start_background_processing(lecture.id, file_info['original_path'])

            # 6. Если фоновая обработка отключена - просто помечаем как обработанное
            else:
                lecture.is_processed = True
                self.db.commit()

            return {
                'success': True,
                'lecture_id': lecture.id,
                'file_info': file_info,
                'lecture': {
                    'title': lecture.title,
                    'author': lecture.author,
                    'file_name': lecture.file_name,
                    'is_processed': lecture.is_processed,
                    'has_thumbnail': bool(lecture.thumbnail_path)
                }
            }

        except Exception as e:
            # Откат: удаляем файл если ошибка БД
            self.uploader.delete_file(file_info['filename'])
            # Откатываем сессию БД если есть метод rollback
            if hasattr(self.db, 'rollback'):
                self.db.rollback()
            logger.error(f"Ошибка загрузки лекции: {e}")
            raise

    def _create_thumbnail_sync(self, lecture_id: int, video_path: str) -> Optional[str]:
        """Синхронное создание превью (для тестов)"""
        try:
            # Создаем превью
            thumbnail_path = Path(video_path).with_suffix('.jpg')
            success = self.processor.create_thumbnail_simple(
                video_path,
                str(thumbnail_path)
            )

            if success and thumbnail_path.exists():
                logger.info(f"Превью создано синхронно для лекции {lecture_id}")
                return str(thumbnail_path)
            else:
                logger.warning(f"Не удалось создать превью для лекции {lecture_id}")
                return None

        except Exception as e:
            logger.error(f"Ошибка создания превью (синхронно): {e}")
            return None

    def _generate_slug(self, title: str) -> str:
        """Генерация slug из названия"""
        # Упрощенная версия
        slug = title.lower()
        # Заменяем все не-буквенные символы на дефисы
        slug = re.sub(r'[^a-z0-9а-яё]+', '-', slug)
        # Убираем лишние дефисы
        slug = re.sub(r'-+', '-', slug).strip('-')

        # Добавляем timestamp для уникальности
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        return f"{slug}-{timestamp}" if slug else f"lecture-{timestamp}"

    def _start_background_processing(self, lecture_id: int, video_path: str):
        """
        Запуск фоновой обработки видео - ТОЛЬКО ДЛЯ ПРОДАКШЕНА
        """
        # Проверяем что есть engine (не в тестах)
        if not self.engine:
            logger.warning("Нет engine для фоновой обработки, пропускаем")
            return

        # Создаем новый поток для обработки
        thread = threading.Thread(
            target=self._background_process,
            args=(lecture_id, video_path),
            daemon=True,
            name=f"VideoProcessing-{lecture_id}"
        )
        thread.start()
        logger.info(f"Запущена фоновая обработка для лекции {lecture_id}")

    def _background_process(self, lecture_id: int, video_path: str):
        """Фоновая обработка видео - продакшен версия"""
        try:
            # Создаем превью (если ffmpeg есть)
            thumbnail_path = Path(video_path).with_suffix('.jpg')
            success = False

            # Проверяем существует ли файл видео
            if Path(video_path).exists():
                success = self.processor.create_thumbnail_simple(
                    video_path,
                    str(thumbnail_path)
                )
                logger.info(f"Превью создано: {success} для лекции {lecture_id}")
            else:
                logger.warning(f"Видео файл не найден: {video_path}")

            # СОЗДАЕМ НОВУЮ СЕССИЮ для этого потока
            SessionLocal = sessionmaker(bind=self.engine)
            new_db = SessionLocal()

            try:
                # Обновляем запись в БД
                lecture = new_db.query(Lecture).filter(Lecture.id == lecture_id).first()
                if lecture:
                    if success and thumbnail_path.exists():
                        lecture.thumbnail_path = str(thumbnail_path)
                    lecture.is_processed = True
                    lecture.updated_at = datetime.now()
                    new_db.commit()

                    logger.info(f"Лекция {lecture_id} успешно обработана в фоне")
                else:
                    logger.warning(f"Лекция {lecture_id} не найдена в БД")

            except Exception as db_error:
                logger.error(f"Ошибка БД при фоновой обработке: {db_error}")
                new_db.rollback()
            finally:
                new_db.close()

        except Exception as e:
            logger.error(f"Ошибка фоновой обработки: {e}")

    # Остальные методы без изменений...
    def get_lecture_by_id(self, lecture_id: int) -> Optional[Lecture]:
        """Получить лекцию по ID"""
        return self.db.query(Lecture).filter(Lecture.id == lecture_id).first()

    def list_lectures(self, limit: int = 100, offset: int = 0, **filters) -> list:
        """Список лекций с фильтрацией"""
        query = self.db.query(Lecture)

        # Применяем фильтры
        if 'category' in filters:
            query = query.filter(Lecture.category == filters['category'])
        if 'author' in filters:
            query = query.filter(Lecture.author == filters['author'])
        if 'is_public' in filters:
            query = query.filter(Lecture.is_public == filters['is_public'])

        return query.order_by(Lecture.created_at.desc()) \
            .offset(offset) \
            .limit(limit) \
            .all()

    def delete_lecture(self, lecture_id: int) -> bool:
        """Удалить лекцию и файлы"""
        lecture = self.get_lecture_by_id(lecture_id)
        if not lecture:
            return False

        try:
            # Удаляем файлы
            if lecture.file_path and Path(lecture.file_path).exists():
                Path(lecture.file_path).unlink()

            if lecture.thumbnail_path and Path(lecture.thumbnail_path).exists():
                Path(lecture.thumbnail_path).unlink()

            # Удаляем из БД
            self.db.delete(lecture)
            self.db.commit()
            return True

        except Exception as e:
            if hasattr(self.db, 'rollback'):
                self.db.rollback()
            logger.error(f"Error deleting lecture: {e}")
            return False