from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .base import Base


# Модель для групп
class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    max_students = Column(Integer, default=25)  # Максимум 25 человек
    created_at = Column(DateTime, default=datetime.now)
    transfer_deadline = Column(DateTime, nullable=True)  # Дедлайн для перехода между группами

    # Связи будут установлены позже через relationship в database_manager.py

    def __repr__(self):
        return f"<Group(id={self.id}, name='{self.name}')>"


    def can_join(self, session=None):
        """Проверяет, можно ли присоединиться к группе"""
        from datetime import datetime

        if self.transfer_deadline and datetime.now() > self.transfer_deadline:
            return False, "Истек дедлайн для перехода в группу"

        # Проверка количества студентов
        if session is not None:
            # Используем сессию для точного подсчета
            try:
                # Импортируем здесь чтобы избежать циклических зависимостей
                from .users import User, UserType
                student_count = session.query(User).filter(
                    User.group_id == self.id,
                    User.user_type == UserType.STUDENT
                ).count()

                if student_count >= self.max_students:
                    return False, f"Группа заполнена ({student_count}/{self.max_students})"

                return True, f"Можно присоединиться ({student_count}/{self.max_students})"
            except Exception:
                # Если не удалось использовать сессию, используем fallback
                pass

        # Fallback: проверяем через связанные объекты или возвращаем приблизительный результат
        if not hasattr(self, 'students') or self.students is None:
            return True, "Предварительная проверка пройдена"

        try:
            student_count = 0
            for student in self.students:
                if hasattr(student, 'user_type') and student.user_type:
                    if student.user_type.value == "student":
                        student_count += 1
                else:
                    student_count += 1

            if student_count >= self.max_students:
                return False, f"Группа заполнена ({student_count}/{self.max_students})"

            return True, f"Можно присоединиться ({student_count}/{self.max_students})"
        except Exception:
            return True, "Предварительная проверка пройдена (ошибка доступа к данным)"