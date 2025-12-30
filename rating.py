from datetime import datetime
from typing import List, Dict, Optional, Tuple
import numpy as np
from scipy import stats
from contextlib import contextmanager
from sqlalchemy.orm import Session

from models import db, User, Group, UserType


class RatingSystem:
    """
    Система расчета рейтинга через нормальное распределение.
    
    Оценка за семинары рассчитывается по формуле:
    Norm.dist(x; µ; σ; true) * 10
    
    где:
    - x - балл студента за семинары
    - µ - среднее арифметическое по студентам с баллами > -15
    - σ - стандартное отклонение по студентам с баллами > -15
    
    Студенты с баллами <= -15 получают оценку 0.
    """

    def __init__(self, db_manager=None):
        """Инициализация системы рейтинга"""
        self.db = db_manager or db
        self.EXCLUSION_THRESHOLD = -15  # Порог исключения из расчета

    def _calculate_grades(self, students_data: List[Tuple[int, float]]) -> Dict[int, Dict]:
        """
        Рассчитывает оценки для студентов по формуле нормального распределения
        
        Args:
            students_data: Список кортежей (user_id, score)
            
        Returns:
            Словарь {user_id: {'grade': оценка, 'excluded': bool, 'cdf_value': float}}
        """
        if not students_data:
            return {}

        # Разделяем студентов на включенных и исключенных
        included_students = [(uid, score) for uid, score in students_data if score > self.EXCLUSION_THRESHOLD]
        excluded_students = [(uid, score) for uid, score in students_data if score <= self.EXCLUSION_THRESHOLD]

        result = {}

        # Студентам с баллами <= -15 ставим оценку 0
        for user_id, score in excluded_students:
            result[user_id] = {
                'grade': 0.0,
                'excluded': True,
                'cdf_value': 0.0
            }

        if not included_students:
            return result

        # Вычисляем параметры нормального распределения только для включенных студентов
        included_scores = np.array([score for _, score in included_students])
        mu = np.mean(included_scores)  # Среднее арифметическое
        sigma = np.std(included_scores, ddof=0)  # Стандартное отклонение (как в Excel)

        # Если стандартное отклонение равно 0, все баллы одинаковые
        if sigma == 0:
            # Если все баллы одинаковые, всем ставим одинаковую оценку
            # Используем среднее значение для оценки
            for user_id, score in included_students:
                result[user_id] = {
                    'grade': 5.0,  # Средняя оценка в 10-балльной системе
                    'excluded': False,
                    'cdf_value': 0.5
                }
            return result

        # Рассчитываем оценки для включенных студентов
        # Norm.dist(x; µ; σ; true) * 10
        for user_id, score in included_students:
            # Вычисляем кумулятивную функцию распределения (CDF)
            cdf_value = stats.norm.cdf(score, loc=mu, scale=sigma)
            # Умножаем на 10 для перевода в 10-балльную систему
            grade = cdf_value * 10

            result[user_id] = {
                'grade': float(grade),
                'excluded': False,
                'cdf_value': float(cdf_value),
                'mu': float(mu),
                'sigma': float(sigma)
            }

        return result

    def get_group_rating(self, group_id: int) -> List[Dict]:
        """
        Получает рейтинг студентов в группе из БД или рассчитывает если его нет
        
        Args:
            group_id: ID группы
            
        Returns:
            Список словарей с информацией о студентах и их рейтинге
        """
        # Пытаемся получить из БД
        cached_rating = self.db.get_ratings_from_db(group_id=group_id, rating_type='group')
        if cached_rating:
            return cached_rating
        
        # Если в БД нет, рассчитываем и сохраняем
        with self.db.get_session() as session:
            group = session.get(Group, group_id)
            if not group:
                return []

            # Получаем всех студентов группы
            students = [s for s in group.students if s.user_type == UserType.STUDENT]
            if not students:
                return []

            # Подготавливаем данные для расчета оценок
            students_data = [(student.id, student.score) for student in students]

            # Рассчитываем оценки
            grades_dict = self._calculate_grades(students_data)

            # Создаем рейтинг (сортируем по убыванию оценки, затем по убыванию баллов)
            rating = []
            sorted_students = sorted(
                students,
                key=lambda s: (grades_dict.get(s.id, {}).get('grade', 0), s.score),
                reverse=True
            )

            for rank, student in enumerate(sorted_students, start=1):
                grade_info = grades_dict.get(student.id, {})
                grade = grade_info.get('grade', 0.0)
                excluded = grade_info.get('excluded', False)
                cdf_value = grade_info.get('cdf_value', 0.0)

                rating_entry = {
                    'user_id': student.id,
                    'username': student.username,
                    'score': student.score,
                    'rank': rank,
                    'grade': round(grade, 2),  # Оценка в 10-балльной системе
                    'excluded': excluded,
                    'cdf_value': round(cdf_value, 4),
                    'group_id': group_id,
                    'group_name': group.name
                }
                rating.append(rating_entry)
                
                # Сохраняем в БД
                self.db.save_rating(
                    user_id=student.id,
                    group_id=group_id,
                    rating_type='group',
                    rank=rank,
                    grade=grade,
                    score=student.score,
                    excluded=excluded,
                    cdf_value=cdf_value
                )

            return rating

    def get_overall_rating(self) -> List[Dict]:
        """
        Получает общий рейтинг всех студентов по всем группам из БД или рассчитывает если его нет
        
        Returns:
            Список словарей с информацией о студентах и их рейтинге
        """
        # Пытаемся получить из БД
        cached_rating = self.db.get_ratings_from_db(group_id=None, rating_type='overall')
        if cached_rating:
            return cached_rating
        
        # Если в БД нет, рассчитываем и сохраняем
        with self.db.get_session() as session:
            # Получаем всех студентов
            students = session.query(User).filter(
                User.user_type == UserType.STUDENT
            ).all()

            if not students:
                return []

            # Подготавливаем данные для расчета оценок
            students_data = [(student.id, student.score) for student in students]

            # Рассчитываем оценки для всех студентов
            grades_dict = self._calculate_grades(students_data)

            # Создаем общий рейтинг (сортируем по убыванию оценки, затем по убыванию баллов)
            rating = []
            sorted_students = sorted(
                students,
                key=lambda s: (grades_dict.get(s.id, {}).get('grade', 0), s.score),
                reverse=True
            )

            for rank, student in enumerate(sorted_students, start=1):
                grade_info = grades_dict.get(student.id, {})
                grade = grade_info.get('grade', 0.0)
                excluded = grade_info.get('excluded', False)
                cdf_value = grade_info.get('cdf_value', 0.0)

                rating_entry = {
                    'user_id': student.id,
                    'username': student.username,
                    'score': student.score,
                    'rank': rank,
                    'grade': round(grade, 2),  # Оценка в 10-балльной системе
                    'excluded': excluded,
                    'cdf_value': round(cdf_value, 4),
                    'group_id': student.group_id,
                    'group_name': student.group.name if student.group else 'Без группы'
                }
                rating.append(rating_entry)
                
                # Сохраняем в БД
                self.db.save_rating(
                    user_id=student.id,
                    group_id=None,  # Общий рейтинг
                    rating_type='overall',
                    rank=rank,
                    grade=grade,
                    score=student.score,
                    excluded=excluded,
                    cdf_value=cdf_value
                )

            return rating

    def recalculate_all_ratings(self):
        """
        Пересчитывает все рейтинги (групповые и общий) и сохраняет в БД
        """
        # Очищаем старые рейтинги
        self.db.clear_ratings()
        
        # Пересчитываем групповые рейтинги
        with self.db.get_session() as session:
            groups = session.query(Group).all()
            for group in groups:
                # Принудительно пересчитываем (очищаем и вызываем get_group_rating)
                self.db.clear_ratings(group_id=group.id, rating_type='group')
                self.get_group_rating(group.id)
        
        # Пересчитываем общий рейтинг
        self.db.clear_ratings(rating_type='overall')
        self.get_overall_rating()
    
    def recalculate_group_rating(self, group_id: int):
        """
        Пересчитывает рейтинг для конкретной группы
        
        Args:
            group_id: ID группы
        """
        # Очищаем рейтинг для этой группы
        self.db.clear_ratings(group_id=group_id, rating_type='group')
        
        # Пересчитываем
        self.get_group_rating(group_id)
        
        # Также нужно пересчитать общий рейтинг, т.к. он зависит от всех групп
        self.db.clear_ratings(rating_type='overall')
        self.get_overall_rating()

    def get_user_rating_position(self, user_id: int, by_group: bool = False) -> Optional[Dict]:
        """
        Получает позицию пользователя в рейтинге
        
        Args:
            user_id: ID пользователя
            by_group: Если True, возвращает позицию в группе, иначе в общем рейтинге
            
        Returns:
            Словарь с информацией о позиции пользователя или None
        """
        if by_group:
            with self.db.get_session() as session:
                user = session.get(User, user_id)
                if not user or not user.group_id:
                    return None

                group_rating = self.get_group_rating(user.group_id)
                for entry in group_rating:
                    if entry['user_id'] == user_id:
                        return entry
        else:
            overall_rating = self.get_overall_rating()
            for entry in overall_rating:
                if entry['user_id'] == user_id:
                    return entry

        return None

    def get_top_students_by_group(self, group_id: int, limit: int = 10) -> List[Dict]:
        """
        Получает топ студентов в группе
        
        Args:
            group_id: ID группы
            limit: Количество студентов в топе
            
        Returns:
            Список словарей с информацией о топ студентах
        """
        rating = self.get_group_rating(group_id)
        return rating[:limit]

    def get_top_students_overall(self, limit: int = 10) -> List[Dict]:
        """
        Получает топ студентов по всем группам
        
        Args:
            limit: Количество студентов в топе
            
        Returns:
            Список словарей с информацией о топ студентах
        """
        rating = self.get_overall_rating()
        return rating[:limit]

    def get_rating_statistics(self, group_id: Optional[int] = None) -> Dict:
        """
        Получает статистику по рейтингу
        
        Args:
            group_id: ID группы (если None, то статистика по всем группам)
            
        Returns:
            Словарь со статистикой
        """
        if group_id:
            rating = self.get_group_rating(group_id)
            group_name = rating[0]['group_name'] if rating else None
        else:
            rating = self.get_overall_rating()
            group_name = None

        if not rating:
            return {
                'group_id': group_id,
                'group_name': group_name,
                'total_students': 0,
                'excluded_students': 0,
                'mean_score': 0,
                'median_score': 0,
                'std_score': 0,
                'min_score': 0,
                'max_score': 0,
                'mean_grade': 0,
                'median_grade': 0
            }

        scores = [entry['score'] for entry in rating]
        grades = [entry['grade'] for entry in rating]
        excluded_count = sum(1 for entry in rating if entry.get('excluded', False))

        # Статистика только для включенных студентов (для расчета параметров распределения)
        included_scores = [entry['score'] for entry in rating if not entry.get('excluded', False)]
        mu = float(np.mean(included_scores)) if included_scores else 0.0
        sigma = float(np.std(included_scores, ddof=0)) if len(included_scores) > 1 else 0.0

        return {
            'group_id': group_id,
            'group_name': group_name,
            'total_students': len(rating),
            'excluded_students': excluded_count,
            'included_students': len(rating) - excluded_count,
            'mean_score': float(np.mean(scores)),
            'median_score': float(np.median(scores)),
            'std_score': float(np.std(scores)) if len(scores) > 1 else 0.0,
            'min_score': int(min(scores)),
            'max_score': int(max(scores)),
            'mean_grade': float(np.mean(grades)),
            'median_grade': float(np.median(grades)),
            'mu': mu,  # Среднее для нормального распределения
            'sigma': sigma  # Стандартное отклонение для нормального распределения
        }

    def format_rating_message(self, rating: List[Dict], title: str = "Рейтинг") -> str:
        """
        Форматирует рейтинг в текстовое сообщение для Telegram
        
        Args:
            rating: Список записей рейтинга
            title: Заголовок рейтинга
            
        Returns:
            Отформатированное текстовое сообщение
        """
        if not rating:
            return f"{title}\n\nРейтинг пуст."

        message = f"📊 {title}\n\n"
        
        for entry in rating[:20]:  # Ограничиваем до 20 записей
            medal = ""
            if entry['rank'] == 1:
                medal = "🥇"
            elif entry['rank'] == 2:
                medal = "🥈"
            elif entry['rank'] == 3:
                medal = "🥉"
            
            group_info = f" | {entry['group_name']}" if entry.get('group_name') else ""
            excluded_mark = " ⚠️" if entry.get('excluded', False) else ""
            message += f"{medal} {entry['rank']}. {entry['username']}{group_info}{excluded_mark}\n"
            message += f"   Баллы: {entry['score']} | Оценка: {entry['grade']:.2f}\n\n"

        if len(rating) > 20:
            message += f"... и еще {len(rating) - 20} студентов"

        return message


# Создаем глобальный экземпляр системы рейтинга
rating_system = RatingSystem()


# Функции для обратной совместимости
def get_group_rating(group_id: int) -> List[Dict]:
    """Получает рейтинг группы"""
    return rating_system.get_group_rating(group_id)


def get_overall_rating() -> List[Dict]:
    """Получает общий рейтинг"""
    return rating_system.get_overall_rating()


def get_user_rating_position(user_id: int, by_group: bool = False) -> Optional[Dict]:
    """Получает позицию пользователя в рейтинге"""
    return rating_system.get_user_rating_position(user_id, by_group)


def get_top_students_by_group(group_id: int, limit: int = 10) -> List[Dict]:
    """Получает топ студентов в группе"""
    return rating_system.get_top_students_by_group(group_id, limit)


def get_top_students_overall(limit: int = 10) -> List[Dict]:
    """Получает топ студентов по всем группам"""
    return rating_system.get_top_students_overall(limit)


def get_rating_statistics(group_id: Optional[int] = None) -> Dict:
    """Получает статистику по рейтингу"""
    return rating_system.get_rating_statistics(group_id)


def format_rating_message(rating: List[Dict], title: str = "Рейтинг") -> str:
    """Форматирует рейтинг в текстовое сообщение"""
    return rating_system.format_rating_message(rating, title)


# Тестирование
if __name__ == "__main__":
    from models import db, UserType, User, Group
    from datetime import datetime
    
    print("=" * 60)
    print("Тестирование системы рейтинга")
    print("=" * 60)

    # Создаем тестовые данные
    print("\n✓ Создание тестовых данных...")
    
    # Получаем или создаем группы (избегаем конфликта с существующими)
    def get_or_create_group(name, max_students=25):
        """Получает существующую группу или создает новую"""
        with db.get_session() as session:
            group = session.query(Group).filter(Group.name == name).first()
            if group:
                return group
        
        # Если группа не найдена, пытаемся создать
        try:
            return db.create_group(name, max_students=max_students)
        except Exception:
            # Если произошла ошибка (например, группа создалась в другом процессе),
            # получаем существующую
            with db.get_session() as session:
                return session.query(Group).filter(Group.name == name).first()
    
    group1 = get_or_create_group("Группа А", max_students=25)
    group2 = get_or_create_group("Группа Б", max_students=25)
    
    print(f"  Используем группы: {group1.name} (ID: {group1.id}), {group2.name} (ID: {group2.id})")
    
    # Создаем студентов с разными баллами (включая отрицательные для теста исключения)
    students_data = [
        (1, "Иван Петров", 150, group1.id),
        (2, "Мария Иванова", 200, group1.id),
        (3, "Алексей Смирнов", 120, group1.id),
        (4, "Анна Козлова", 180, group1.id),
        (5, "Дмитрий Волков", 100, group1.id),
        (6, "Елена Новикова", 250, group2.id),
        (7, "Сергей Лебедев", 190, group2.id),
        (8, "Ольга Соколова", 140, group2.id),
        (9, "Павел Морозов", 110, group2.id),
        (10, "Татьяна Орлова", 160, group2.id),
        (11, "Тест Исключенный", -20, group1.id),  # Должен получить оценку 0
        (12, "Тест Граничный", -15, group1.id),  # Должен получить оценку 0
    ]
    
    for user_id, username, score, group_id in students_data:
        user = db.get_or_create_user(user_id, username, UserType.STUDENT)
        db.set_user_group(user_id, group_id)
        # Устанавливаем баллы напрямую
        with db.get_session() as session:
            user = session.get(User, user_id)
            user.score = score
    
    print(f"  Создано {len(students_data)} студентов в 2 группах")

    # Тест 1: Рейтинг по группе
    print("\n✓ Тест 1: Рейтинг группы А")
    group_rating = rating_system.get_group_rating(group1.id)
    print(f"  Студентов в группе: {len(group_rating)}")
    for entry in group_rating:
        excluded_mark = " (исключен)" if entry.get('excluded') else ""
        print(f"    {entry['rank']}. {entry['username']}: баллы={entry['score']}, "
              f"оценка={entry['grade']:.2f}{excluded_mark}")

    # Тест 2: Общий рейтинг
    print("\n✓ Тест 2: Общий рейтинг")
    overall_rating = rating_system.get_overall_rating()
    print(f"  Всего студентов: {len(overall_rating)}")
    for entry in overall_rating:
        excluded_mark = " (исключен)" if entry.get('excluded') else ""
        print(f"    {entry['rank']}. {entry['username']} ({entry['group_name']}): "
              f"баллы={entry['score']}, оценка={entry['grade']:.2f}{excluded_mark}")

    # Тест 3: Позиция пользователя
    print("\n✓ Тест 3: Позиция пользователя")
    user_position = rating_system.get_user_rating_position(1, by_group=True)
    if user_position:
        print(f"  Позиция в группе: {user_position['rank']}")
        print(f"  Баллы: {user_position['score']}, Оценка: {user_position['grade']:.2f}")
    
    user_position_overall = rating_system.get_user_rating_position(1, by_group=False)
    if user_position_overall:
        print(f"  Позиция в общем рейтинге: {user_position_overall['rank']}")
        print(f"  Оценка: {user_position_overall['grade']:.2f}")

    # Тест 4: Статистика
    print("\n✓ Тест 4: Статистика по группе")
    stats_group = rating_system.get_rating_statistics(group_id=group1.id)
    print(f"  Группа: {stats_group['group_name']}")
    print(f"  Всего студентов: {stats_group['total_students']}")
    print(f"  Исключено студентов: {stats_group['excluded_students']}")
    print(f"  Включено в расчет: {stats_group['included_students']}")
    print(f"  Средний балл: {stats_group['mean_score']:.2f}")
    print(f"  Медианный балл: {stats_group['median_score']:.2f}")
    print(f"  Мин/Макс: {stats_group['min_score']}/{stats_group['max_score']}")
    print(f"  Средняя оценка: {stats_group['mean_grade']:.2f}")
    print(f"  µ (среднее для распределения): {stats_group['mu']:.2f}")
    print(f"  σ (стандартное отклонение): {stats_group['sigma']:.2f}")

    # Тест 5: Форматирование сообщения
    print("\n✓ Тест 5: Форматирование рейтинга")
    message = rating_system.format_rating_message(group_rating, "Рейтинг группы А")
    print(message)

    print("\n" + "=" * 60)
    print("Тестирование завершено успешно!")
    print("=" * 60)

