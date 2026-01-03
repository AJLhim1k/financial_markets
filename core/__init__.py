# core/__init__.py
"""
Core модули для работы с лекциями
"""

from .uploader import VideoUploader
from .video_processor import SimpleVideoProcessor
from .lecture_manager import LectureManager

__all__ = ['VideoUploader', 'SimpleVideoProcessor', 'LectureManager']