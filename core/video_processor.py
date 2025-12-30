# core/video_processor.py
import subprocess
import os
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class SimpleVideoProcessor:
    """
    Простой процессор видео без тяжелых зависимостей
    Только самое необходимое
    """

    @staticmethod
    def get_basic_info(file_path: str) -> Dict:
        """
        Базовая информация о видео файле
        Без внешних зависимостей
        """
        path = Path(file_path)

        if not path.exists():
            return {}

        # Используем системные утилиты если они есть
        info = {
            'file_path': str(path),
            'file_size': path.stat().st_size,
            'file_name': path.name,
            'extension': path.suffix.lower(),
            'exists': True
        }

        # Пытаемся получить длину через ffprobe если установлен
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries',
                 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                 file_path],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                duration = float(result.stdout.strip())
                info['duration_seconds'] = duration
                info[
                    'duration_human'] = f"{int(duration // 3600):02d}:{int((duration % 3600) // 60):02d}:{int(duration % 60):02d}"

        except (subprocess.SubprocessError, FileNotFoundError):
            logger.debug("ffprobe не найден, пропускаем получение длительности")

        return info

    @staticmethod
    def create_thumbnail_simple(
            video_path: str,
            thumbnail_path: str,
            frame_time: int = 10
    ) -> bool:
        """
        Создание превью через ffmpeg (если установлен)
        """
        try:
            cmd = [
                'ffmpeg',
                '-ss', str(frame_time),  # Время в секундах
                '-i', video_path,
                '-vframes', '1',  # Только один кадр
                '-q:v', '2',  # Качество JPEG (2 = высокое)
                thumbnail_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # Таймаут 30 секунд
            )

            success = result.returncode == 0 and Path(thumbnail_path).exists()

            if success:
                logger.info(f"Превью создано: {thumbnail_path}")
            else:
                logger.error(f"Ошибка создания превью: {result.stderr}")

            return success

        except Exception as e:
            logger.error(f"Ошибка при создании превью: {e}")
            return False

    @staticmethod
    def check_video_integrity(file_path: str) -> bool:
        """
        Быстрая проверка целостности видео файла
        """
        try:
            # Простая проверка через ffmpeg
            result = subprocess.run(
                ['ffmpeg', '-v', 'error', '-i', file_path, '-f', 'null', '-'],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Если есть ошибки в выводе - файл поврежден
            return result.returncode == 0 and not result.stderr

        except:
            # Если ffmpeg нет, просто проверяем что файл не пустой
            return Path(file_path).stat().st_size > 1024