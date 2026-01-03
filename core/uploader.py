# core/uploader.py
import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, List
import mimetypes
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoUploader:
    """
    Минимальный аплоадер видео для админов/семинаристов
    Только ядро функционала без роутеров и зависимостей
    """

    # Поддерживаемые форматы видео
    ALLOWED_EXTENSIONS = {'.mp4', '.webm', '.mov', '.avi', '.mkv', '.flv'}

    # MIME-типы для проверки
    ALLOWED_MIME_TYPES = {
        'video/mp4', 'video/webm', 'video/quicktime',
        'video/x-msvideo', 'video/x-matroska', 'video/x-flv'
    }

    def __init__(
            self,
            upload_dir: str = "records",
            max_size_mb: int = 2048,  # 2GB по умолчанию
            chunk_size: int = 8192
    ):
        """
        Инициализация аплоадера

        Args:
            upload_dir: Папка для загрузки видео
            max_size_mb: Максимальный размер файла в MB
            chunk_size: Размер чанка для чтения/записи
        """
        self.upload_dir = Path(upload_dir).resolve()
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.chunk_size = chunk_size

        # Создаем папку если не существует
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Upload directory: {self.upload_dir}")

    def _generate_filename(self, original_filename: str) -> str:
        """
        Генерация безопасного уникального имени файла

        Пример: introduction.mp4 -> 20231215_093045_abc123de.mp4
        """
        ext = Path(original_filename).suffix.lower()

        # Проверяем расширение
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(f"Неподдерживаемое расширение: {ext}")

        # Генерируем уникальные компоненты
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]  # Первые 8 символов UUID

        return f"{timestamp}_{unique_id}{ext}"

    def _validate_file_type(self, file_path: str) -> bool:
        """
        Проверка MIME-типа файла (дополнительная безопасность)
        """
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type in self.ALLOWED_MIME_TYPES

    def _get_file_size(self, file_obj) -> int:
        """
        Определение размера файла разными способами
        """
        try:
            # Способ 1: Если есть атрибут size
            if hasattr(file_obj, 'size'):
                return file_obj.size

            # Способ 2: Если есть tell/seek (файловый объект)
            if hasattr(file_obj, 'tell') and hasattr(file_obj, 'seek'):
                current_pos = file_obj.tell()
                file_obj.seek(0, 2)  # Перемещаемся в конец
                size = file_obj.tell()
                file_obj.seek(current_pos)  # Возвращаемся обратно
                return size

            # Способ 3: Через os.path если это путь
            if isinstance(file_obj, (str, Path)):
                return os.path.getsize(file_obj)

        except Exception as e:
            logger.warning(f"Не удалось определить размер файла: {e}")

        return 0

    def save_from_stream(
            self,
            file_stream,
            original_filename: str,
            custom_filename: Optional[str] = None
    ) -> Dict:
        """
        Сохранение видео из файлового потока

        Args:
            file_stream: Файловый объект (io.BytesIO, UploadFile и т.д.)
            original_filename: Оригинальное имя файла
            custom_filename: Кастомное имя (если не указано - генерируется)

        Returns:
            Dict с информацией о сохраненном файле
        """
        try:
            # 1. Генерация имени файла
            if custom_filename:
                filename = custom_filename
            else:
                filename = self._generate_filename(original_filename)

            full_path = self.upload_dir / filename

            # 2. Проверка размера перед сохранением
            file_size = self._get_file_size(file_stream)
            if file_size > self.max_size_bytes:
                raise ValueError(
                    f"Файл слишком большой: {file_size / 1024 / 1024:.1f}MB "
                    f"(максимум: {self.max_size_bytes / 1024 / 1024:.1f}MB)"
                )

            # 3. Сохранение файла чанками (память-эффективно)
            bytes_written = 0
            with open(full_path, 'wb') as dest_file:
                while True:
                    chunk = file_stream.read(self.chunk_size)
                    if not chunk:
                        break
                    dest_file.write(chunk)
                    bytes_written += len(chunk)

            # 4. Проверка MIME-типа
            if not self._validate_file_type(str(full_path)):
                os.remove(full_path)
                raise ValueError("Файл не является допустимым видео")

            # 5. Сбор информации о файле
            file_info = self._collect_file_info(full_path, bytes_written)

            logger.info(f"Файл сохранен: {filename} ({bytes_written} bytes)")
            return file_info

        except Exception as e:
            logger.error(f"Ошибка сохранения файла: {e}")
            raise

    def save_from_path(
            self,
            source_path: str,
            custom_filename: Optional[str] = None
    ) -> Dict:
        """
        Сохранение видео из локального пути

        Args:
            source_path: Путь к исходному файлу
            custom_filename: Кастомное имя файла

        Returns:
            Dict с информацией о файле
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Файл не найден: {source_path}")

        # Используем save_from_stream с файловым объектом
        with open(source, 'rb') as file_stream:
            return self.save_from_stream(
                file_stream,
                source.name,
                custom_filename
            )

    def _collect_file_info(self, file_path: Path, file_size: int) -> Dict:
        """
        Сбор информации о сохраненном файле
        """
        stat = file_path.stat()

        return {
            'filename': file_path.name,
            'original_path': str(file_path),
            'relative_path': str(file_path.relative_to(self.upload_dir)),
            'size_bytes': file_size,
            'size_human': self._humanize_size(file_size),
            'created_at': datetime.fromtimestamp(stat.st_ctime),
            'modified_at': datetime.fromtimestamp(stat.st_mtime),
            'extension': file_path.suffix.lower(),
            'mime_type': mimetypes.guess_type(str(file_path))[0] or 'video/mp4',
            'checksum': self._calculate_checksum(file_path)
        }

    def _humanize_size(self, size_bytes: int) -> str:
        """Человеко-читаемый размер файла"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _calculate_checksum(self, file_path: Path, algorithm: str = 'md5') -> str:
        """
        Расчет контрольной суммы файла (для проверки целостности)
        """
        import hashlib

        hash_func = getattr(hashlib, algorithm)()

        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hash_func.update(chunk)

        return hash_func.hexdigest()

    def list_uploaded_files(self) -> List[Dict]:
        """
        Список всех загруженных видео
        """
        files = []
        for file_path in self.upload_dir.glob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.ALLOWED_EXTENSIONS:
                files.append(self._collect_file_info(file_path, file_path.stat().st_size))

        return files

    def delete_file(self, filename: str) -> bool:
        """
        Удаление файла по имени
        """
        file_path = self.upload_dir / filename
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Файл удален: {filename}")
            return True
        return False

    def get_storage_info(self) -> Dict:
        """
        Информация о хранилище
        """
        total_size = sum(f.stat().st_size for f in self.upload_dir.glob('*') if f.is_file())
        file_count = sum(1 for _ in self.upload_dir.glob('*') if _.is_file())

        try:
            disk_usage = shutil.disk_usage(self.upload_dir)
            free_space = disk_usage.free
        except:
            free_space = 0

        return {
            'upload_dir': str(self.upload_dir),
            'total_files': file_count,
            'total_size_bytes': total_size,
            'total_size_human': self._humanize_size(total_size),
            'free_space_bytes': free_space,
            'free_space_human': self._humanize_size(free_space),
            'max_file_size_bytes': self.max_size_bytes,
            'max_file_size_human': self._humanize_size(self.max_size_bytes),
            'allowed_extensions': list(self.ALLOWED_EXTENSIONS)
        }