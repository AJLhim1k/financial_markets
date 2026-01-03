import os
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, BigInteger, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import validates
import mimetypes

# Импортируем Base из вашей существующей структуры
from .base import Base  # или from .database_manager import Base


class Lecture(Base):
    __tablename__ = 'lectures'

    id = Column(Integer, primary_key=True, index=True)

    # Основная информация
    title = Column(String(200), nullable=False, index=True)
    author = Column(String(100), nullable=False, index=True)

    # Даты
    lecture_date = Column(DateTime, nullable=False)  # Дата проведения лекции
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Файл видео
    file_name = Column(String(300), nullable=False)  # Имя файла: "introduction.mp4"
    file_path = Column(String(500), nullable=False)  # Полный путь: "/uploads/lectures/introduction.mp4"
    file_size = Column(BigInteger, nullable=True)  # Размер в байтах (важно для стриминга!)
    file_type = Column(String(50), default="video/mp4")  # MIME-тип

    # Метаданные видео (опционально, но полезно)
    duration = Column(Integer, nullable=True)  # Длительность в секундах
    width = Column(Integer, nullable=True)  # Ширина видео в пикселях
    height = Column(Integer, nullable=True)  # Высота видео в пикселях
    bitrate = Column(Integer, nullable=True)  # Битрейт в kbps

    # Дополнительная информация
    description = Column(Text, nullable=True)
    thumbnail_path = Column(String(500), nullable=True)  # Путь к превью
    is_processed = Column(Boolean, default=False)  # Обработано ли видео (превью и т.д.)
    is_public = Column(Boolean, default=True)  # Публичное ли видео

    # Для SEO и организации
    slug = Column(String(200), unique=True, index=True, nullable=True)
    category = Column(String(100), nullable=True, index=True)

    @validates('file_path')
    def validate_file_path(self, key, file_path):
        """Проверяем, что файл имеет допустимое расширение"""
        allowed_extensions = {'.mp4', '.webm', '.mov', '.avi', '.mkv'}
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in allowed_extensions:
            raise ValueError(f"Недопустимое расширение файла. Разрешены: {allowed_extensions}")
        return file_path

    @property
    def file_exists(self):
        """Проверяет, существует ли файл на диске"""
        return os.path.exists(self.file_path) if self.file_path else False

    @property
    def file_extension(self):
        """Возвращает расширение файла"""
        return os.path.splitext(self.file_name)[1].lower() if self.file_name else ''

    @property
    def human_file_size(self):
        """Возвращает размер файла в человеко-читаемом формате"""
        if not self.file_size:
            return "Неизвестно"

        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"

    @property
    def video_info(self):
        """Возвращает информацию о видео для фронтенда"""
        return {
            "duration": self.duration,
            "resolution": f"{self.width}x{self.height}" if self.width and self.height else None,
            "bitrate": self.bitrate
        }

    def to_dict(self, include_video_url=False):
        """Сериализация модели в словарь"""
        result = {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "lecture_date": self.lecture_date.isoformat() if self.lecture_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "description": self.description,
            "file_name": self.file_name,
            "file_size": self.human_file_size,
            "file_type": self.file_type,
            "duration": self.duration,
            "thumbnail_url": f"/api/lectures/{self.id}/thumbnail" if self.thumbnail_path else None,
            "is_processed": self.is_processed,
            "is_public": self.is_public,
            "file_exists": self.file_exists
        }

        if include_video_url:
            result["video_url"] = f"/api/lectures/{self.id}/stream"
            result["video_download_url"] = f"/api/lectures/{self.id}/download"

        return result

    def get_video_stream_range(self):
        """Получает информацию о файле для стриминга"""
        if not self.file_exists:
            return None

        return {
            "file_path": self.file_path,
            "file_size": self.file_size or os.path.getsize(self.file_path),
            "content_type": self.file_type or mimetypes.guess_type(self.file_path)[0] or "video/mp4"
        }

    def __repr__(self):
        return f"<Lecture(id={self.id}, title='{self.title}', author='{self.author}')>"


# Опционально: Модель для статистики просмотров
class LectureView(Base):
    __tablename__ = 'lecture_views'

    id = Column(Integer, primary_key=True)
    lecture_id = Column(Integer, index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=True)  # если есть пользователи
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    watched_at = Column(DateTime, default=datetime.utcnow)
    watch_duration = Column(Integer, default=0)  # сколько секунд посмотрел
    completed = Column(Boolean, default=False)  # досмотрел ли до конца