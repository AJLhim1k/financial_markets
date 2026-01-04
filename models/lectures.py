import os
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, BigInteger, Boolean, ForeignKey
from sqlalchemy.orm import validates, relationship
import mimetypes

# Импортируем Base из вашей существующей структуры
from .base import Base  # Импортируем из base.py


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
    # Внешние ссылки на видео (вместо файлов)
    external_video_url = Column(String(500), nullable=True)  # Ссылка на YouTube/Vimeo/Яндекс.Диск
    external_slides_url = Column(String(500), nullable=True)  # Ссылка на презентацию/материалы
    youtube_video_id = Column(String(100), nullable=True, index=True)  # ID YouTube видео (если есть)
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

    # Связь с просмотрами
    views = relationship("LectureView", back_populates="lecture", cascade="all, delete-orphan")

    @property
    def video_url(self):
        """Возвращает URL для воспроизведения видео"""
        if self.youtube_video_id:
            return f"https://www.youtube.com/embed/{self.youtube_video_id}"
        elif self.external_video_url:
            return self.external_video_url
        else:
            return None

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

        size = float(self.file_size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

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
            "duration": self.duration,
            "video_url": self.video_url,  # <-- ВАЖНО: добавляем здесь!
            "external_slides_url": self.external_slides_url,  # <-- и здесь!
            "thumbnail_url": f"/api/lectures/{self.id}/thumbnail" if self.thumbnail_path else None,
            "is_processed": self.is_processed,
            "is_public": self.is_public,
            "views_count": len(self.views) if self.views else 0
        }

        # Убери старые поля:
        # "file_name": self.file_name,
        # "file_size": self.human_file_size,
        # "file_type": self.file_type,

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
    lecture_id = Column(Integer, ForeignKey('lectures.id', ondelete='CASCADE'), index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=True)  # если есть пользователи
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    watched_at = Column(DateTime, default=datetime.utcnow)
    watch_duration = Column(Integer, default=0)  # сколько секунд посмотрел
    completed = Column(Boolean, default=False)  # досмотрел ли до конца

    # Связь с лекцией
    lecture = relationship("Lecture", back_populates="views")