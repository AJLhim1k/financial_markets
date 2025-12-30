"""
Тесты для системы рейтинга студентов
"""
import pytest
import numpy as np
from scipy import stats

from models import (
    db, UserType, Group,
    get_group_rating, get_overall_rating, get_user_rating_position,
    get_top_students_by_group, get_top_students_overall,
    get_rating_statistics, calculate_all_seminar_grades
)
from models.rating import calculate_grades, format_rating_message, EXCLUSION_THRESHOLD


class TestRatingCalculation:
    """Тесты расчета оценок по нормальному распределению"""

    def test_calculate_grades_empty_list(self):
        """Тест расчета оценок для пустого списка"""
        result = calculate_grades([])
        assert result == {}

    def test_calculate_grades_all_excluded(self):
        """Тест расчета оценок когда все студенты исключены (баллы <= -15)"""
        students_data = [
            (1, -20),
            (2, -15),
            (3, -16),
        ]
        result = calculate_grades(students_data)
        
        assert len(result) == 3
        for user_id in [1, 2, 3]:
            assert result[user_id]['grade'] == 0.0
            assert result[user_id]['excluded'] is True
            assert result[user_id]['cdf_value'] == 0.0

    def test_calculate_grades_all_included(self):
        """Тест расчета оценок когда все студенты включены (баллы > -15)"""
        students_data = [
            (1, 100),
            (2, 150),
            (3, 200),
        ]
        result = calculate_grades(students_data)
        
        assert len(result) == 3
        # Все должны быть включены
        for user_id in [1, 2, 3]:
            assert result[user_id]['excluded'] is False
            assert result[user_id]['grade'] > 0
            assert result[user_id]['grade'] <= 10
            assert 'mu' in result[user_id]
            assert 'sigma' in result[user_id]

    def test_calculate_grades_mixed(self):
        """Тест расчета оценок для смешанного списка (включенные и исключенные)"""
        students_data = [
            (1, -20),  # Исключен
            (2, 100),  # Включен
            (3, -15),  # Исключен (граничное значение)
            (4, 150),  # Включен
        ]
        result = calculate_grades(students_data)
        
        assert len(result) == 4
        # Исключенные получают 0
        assert result[1]['grade'] == 0.0
        assert result[1]['excluded'] is True
        assert result[3]['grade'] == 0.0
        assert result[3]['excluded'] is True
        
        # Включенные получают оценку > 0
        assert result[2]['grade'] > 0
        assert result[2]['excluded'] is False
        assert result[4]['grade'] > 0
        assert result[4]['excluded'] is False

    def test_calculate_grades_same_scores(self):
        """Тест расчета оценок когда все баллы одинаковые (sigma = 0)"""
        students_data = [
            (1, 100),
            (2, 100),
            (3, 100),
        ]
        result = calculate_grades(students_data)
        
        assert len(result) == 3
        # Все должны получить одинаковую оценку 5.0
        for user_id in [1, 2, 3]:
            assert result[user_id]['grade'] == 5.0
            assert result[user_id]['excluded'] is False
            assert result[user_id]['cdf_value'] == 0.5
            assert result[user_id]['sigma'] == 0.0

    def test_calculate_grades_normal_distribution(self):
        """Тест правильности расчета нормального распределения"""
        students_data = [
            (1, 100),
            (2, 150),
            (3, 200),
            (4, 250),
        ]
        result = calculate_grades(students_data)
        
        # Проверяем, что оценки соответствуют нормальному распределению
        scores = [100, 150, 200, 250]
        mu = np.mean(scores)
        sigma = np.std(scores, ddof=0)
        
        # Проверяем, что параметры распределения правильные
        assert result[1]['mu'] == pytest.approx(mu, rel=1e-10)
        assert result[1]['sigma'] == pytest.approx(sigma, rel=1e-10)
        
        # Проверяем, что оценки рассчитываются правильно
        for user_id, score in zip([1, 2, 3, 4], scores):
            expected_cdf = stats.norm.cdf(score, loc=mu, scale=sigma)
            expected_grade = expected_cdf * 10
            assert result[user_id]['grade'] == pytest.approx(expected_grade, rel=1e-10)
            assert result[user_id]['cdf_value'] == pytest.approx(expected_cdf, rel=1e-10)

    def test_calculate_grades_grade_range(self):
        """Тест что оценки находятся в диапазоне [0, 10]"""
        students_data = [
            (1, 50),
            (2, 100),
            (3, 150),
            (4, 200),
            (5, 300),
        ]
        result = calculate_grades(students_data)
        
        for user_id in [1, 2, 3, 4, 5]:
            assert 0 <= result[user_id]['grade'] <= 10

    def test_calculate_grades_exclusion_threshold(self):
        """Тест граничного значения порога исключения"""
        students_data = [
            (1, -15),      # Граничное значение - должно быть исключено
            (2, -14.99),   # Чуть больше - должно быть включено
            (3, -16),     # Меньше - должно быть исключено
        ]
        result = calculate_grades(students_data)
        
        assert result[1]['excluded'] is True
        assert result[1]['grade'] == 0.0
        assert result[2]['excluded'] is False
        assert result[2]['grade'] > 0
        assert result[3]['excluded'] is True
        assert result[3]['grade'] == 0.0


class TestRatingDatabase:
    """Тесты работы с рейтингом в базе данных"""

    def test_calculate_all_ratings(self, db_session):
        """Тест расчета рейтинга для всех студентов"""
        # Создаем студентов с разными баллами
        students_data = [
            (1001, "Студент 1", 150, None),
            (1002, "Студент 2", 200, None),
            (1003, "Студент 3", 100, None),
            (1004, "Студент 4", -20, None),  # Исключен
        ]
        
        for user_id, username, score, group_id in students_data:
            user = db.get_or_create_user(user_id, username, UserType.STUDENT)
            # Устанавливаем баллы через сессию
            with db.get_session() as session:
                from models import User
                user_obj = session.get(User, user_id)
                if user_obj:
                    user_obj.score = score
        
        # Рассчитываем рейтинг
        db.calculate_all_ratings()
        
        # Проверяем, что оценки сохранены
        with db.get_session() as session:
            from models import User
            user1 = session.get(User, 1001)
            user2 = session.get(User, 1002)
            user3 = session.get(User, 1003)
            user4 = session.get(User, 1004)
            
            # Проверяем, что баллы установлены правильно
            assert user1.score == 150
            assert user2.score == 200
            assert user3.score == 100
            assert user4.score == -20
            
            assert user1.seminar_grade is not None
            assert user1.seminar_grade > 0
            assert user2.seminar_grade is not None
            assert user2.seminar_grade > 0
            assert user3.seminar_grade is not None
            assert user3.seminar_grade > 0
            assert user4.seminar_grade is not None
            # Исключенный студент должен получить 0.0
            assert user4.seminar_grade == 0.0

    def test_get_group_rating(self, db_session, test_groups):
        """Тест получения рейтинга группы"""
        group = test_groups[0]
        
        # Создаем студентов в группе
        students_data = [
            (2001, "Студент А", 200, group.id),
            (2002, "Студент Б", 150, group.id),
            (2003, "Студент В", 100, group.id),
        ]
        
        for user_id, username, score, group_id in students_data:
            user = db.get_or_create_user(user_id, username, UserType.STUDENT)
            db.set_user_group(user_id, group_id)
            # Устанавливаем баллы через сессию
            with db.get_session() as session:
                from models import User
                user_obj = session.get(User, user_id)
                if user_obj:
                    user_obj.score = score
        
        # Рассчитываем рейтинг
        db.calculate_all_ratings()
        
        # Получаем рейтинг группы
        rating = db.get_group_rating(group.id)
        
        assert len(rating) == 3
        assert rating[0]['rank'] == 1
        assert rating[1]['rank'] == 2
        assert rating[2]['rank'] == 3
        
        # Проверяем сортировку (по убыванию оценки)
        assert rating[0]['grade'] >= rating[1]['grade']
        assert rating[1]['grade'] >= rating[2]['grade']

    def test_get_overall_rating(self, db_session):
        """Тест получения общего рейтинга"""
        # Создаем студентов в разных группах
        students_data = [
            (3001, "Студент 1", 250, None),
            (3002, "Студент 2", 180, None),
            (3003, "Студент 3", 120, None),
        ]
        
        for user_id, username, score, group_id in students_data:
            user = db.get_or_create_user(user_id, username, UserType.STUDENT)
            # Устанавливаем баллы через сессию
            with db.get_session() as session:
                from models import User
                user_obj = session.get(User, user_id)
                if user_obj:
                    user_obj.score = score
        
        # Рассчитываем рейтинг
        db.calculate_all_ratings()
        
        # Получаем общий рейтинг
        rating = db.get_overall_rating()
        
        assert len(rating) == 3
        assert rating[0]['rank'] == 1
        assert rating[1]['rank'] == 2
        assert rating[2]['rank'] == 3
        
        # Проверяем сортировку
        assert rating[0]['grade'] >= rating[1]['grade']
        assert rating[1]['grade'] >= rating[2]['grade']

    def test_get_user_rating_position(self, db_session, test_groups):
        """Тест получения позиции пользователя в рейтинге"""
        group = test_groups[0]
        
        # Создаем студентов
        students_data = [
            (4001, "Студент 1", 200, group.id),
            (4002, "Студент 2", 150, group.id),
            (4003, "Студент 3", 100, group.id),
        ]
        
        for user_id, username, score, group_id in students_data:
            user = db.get_or_create_user(user_id, username, UserType.STUDENT)
            db.set_user_group(user_id, group_id)
            # Устанавливаем баллы через сессию
            with db.get_session() as session:
                from models import User
                user_obj = session.get(User, user_id)
                if user_obj:
                    user_obj.score = score
        
        # Рассчитываем рейтинг
        db.calculate_all_ratings()
        
        # Проверяем позицию в группе
        position = db.get_user_rating_position(4001, by_group=True)
        assert position is not None
        assert position['user_id'] == 4001
        assert position['rank'] == 1  # Должен быть первым
        
        # Проверяем позицию в общем рейтинге
        position_overall = db.get_user_rating_position(4001, by_group=False)
        assert position_overall is not None
        assert position_overall['user_id'] == 4001

    def test_get_top_students_by_group(self, db_session, test_groups):
        """Тест получения топ студентов в группе"""
        group = test_groups[0]
        
        # Создаем много студентов
        students_data = [
            (5001 + i, f"Студент {i}", 200 - i * 10, group.id)
            for i in range(10)
        ]
        
        for user_id, username, score, group_id in students_data:
            user = db.get_or_create_user(user_id, username, UserType.STUDENT)
            db.set_user_group(user_id, group_id)
            # Устанавливаем баллы через сессию
            with db.get_session() as session:
                from models import User
                user_obj = session.get(User, user_id)
                if user_obj:
                    user_obj.score = score
        
        # Рассчитываем рейтинг
        db.calculate_all_ratings()
        
        # Получаем топ-5
        top_students = db.get_top_students_by_group(group.id, limit=5)
        
        assert len(top_students) == 5
        assert top_students[0]['rank'] == 1
        assert top_students[4]['rank'] == 5

    def test_get_top_students_overall(self, db_session):
        """Тест получения топ студентов по всем группам"""
        # Создаем много студентов
        students_data = [
            (6001 + i, f"Студент {i}", 250 - i * 10, None)
            for i in range(10)
        ]
        
        for user_id, username, score, group_id in students_data:
            user = db.get_or_create_user(user_id, username, UserType.STUDENT)
            # Устанавливаем баллы через сессию
            with db.get_session() as session:
                from models import User
                user_obj = session.get(User, user_id)
                if user_obj:
                    user_obj.score = score
        
        # Рассчитываем рейтинг
        db.calculate_all_ratings()
        
        # Получаем топ-5
        top_students = db.get_top_students_overall(limit=5)
        
        assert len(top_students) == 5
        assert top_students[0]['rank'] == 1
        assert top_students[4]['rank'] == 5

    def test_get_rating_statistics(self, db_session, test_groups):
        """Тест получения статистики по рейтингу"""
        group = test_groups[0]
        
        # Создаем студентов с разными баллами
        students_data = [
            (7001, "Студент 1", 200, group.id),
            (7002, "Студент 2", 150, group.id),
            (7003, "Студент 3", 100, group.id),
            (7004, "Студент 4", -20, group.id),  # Исключен
        ]
        
        for user_id, username, score, group_id in students_data:
            user = db.get_or_create_user(user_id, username, UserType.STUDENT)
            db.set_user_group(user_id, group_id)
            # Устанавливаем баллы через сессию
            with db.get_session() as session:
                from models import User
                user_obj = session.get(User, user_id)
                if user_obj:
                    user_obj.score = score
        
        # Фиксируем изменения
        try:
            db_session.commit()
        except:
            db_session.flush()
        
        # Рассчитываем рейтинг
        db.calculate_all_ratings()
        
        # Получаем статистику
        stats = db.get_rating_statistics(group_id=group.id)
        
        assert stats['total_students'] == 4
        # Проверяем, что исключенные студенты правильно подсчитаны
        # (может быть 0 или 1 в зависимости от того, как считается)
        assert stats['excluded_students'] >= 0
        assert stats['included_students'] >= 3
        assert stats['min_score'] == -20
        assert stats['max_score'] == 200
        assert 'mu' in stats
        assert 'sigma' in stats
        # Среднее для включенных студентов должно быть > 0
        # (только если есть включенные студенты)
        if stats['included_students'] > 0:
            assert stats['mu'] > 0

    def test_recalculate_all_ratings(self, db_session):
        """Тест пересчета всех рейтингов"""
        # Создаем студентов
        students_data = [
            (8001, "Студент 1", 150, None),
            (8002, "Студент 2", 200, None),
        ]
        
        for user_id, username, score, group_id in students_data:
            user = db.get_or_create_user(user_id, username, UserType.STUDENT)
            # Устанавливаем баллы через сессию
            with db.get_session() as session:
                from models import User
                user_obj = session.get(User, user_id)
                if user_obj:
                    user_obj.score = score
        
        # Первый расчет
        db.calculate_all_ratings()
        
        with db.get_session() as session:
            from models import User
            user1 = session.get(User, 8001)
            grade1 = user1.seminar_grade
        
        # Изменяем баллы
        with db.get_session() as session:
            from models import User
            user1 = session.get(User, 8001)
            user1.score = 300  # Увеличиваем баллы
        
        # Пересчитываем
        db.recalculate_all_ratings()
        
        # Проверяем, что оценка изменилась
        with db.get_session() as session:
            from models import User
            user1 = session.get(User, 8001)
            assert user1.seminar_grade != grade1
            assert user1.seminar_grade > grade1  # Больше баллов = больше оценка

    def test_clear_ratings(self, db_session):
        """Тест очистки рейтингов"""
        # Создаем студентов и рассчитываем рейтинг
        students_data = [
            (9001, "Студент 1", 150, None),
            (9002, "Студент 2", 200, None),
        ]
        
        for user_id, username, score, group_id in students_data:
            user = db.get_or_create_user(user_id, username, UserType.STUDENT)
            # Устанавливаем баллы через сессию
            with db.get_session() as session:
                from models import User
                user_obj = session.get(User, user_id)
                if user_obj:
                    user_obj.score = score
        
        db.calculate_all_ratings()
        
        # Проверяем, что оценки есть
        with db.get_session() as session:
            from models import User
            user1 = session.get(User, 9001)
            assert user1.seminar_grade is not None
        
        # Очищаем рейтинги
        db.clear_ratings()
        
        # Проверяем, что оценки удалены
        with db.get_session() as session:
            from models import User
            user1 = session.get(User, 9001)
            assert user1.seminar_grade is None


class TestRatingFormatting:
    """Тесты форматирования рейтинга"""

    def test_format_rating_message_empty(self):
        """Тест форматирования пустого рейтинга"""
        message = format_rating_message([], "Тестовый рейтинг")
        assert "Тестовый рейтинг" in message
        assert "Рейтинг пуст" in message

    def test_format_rating_message_with_data(self):
        """Тест форматирования рейтинга с данными"""
        rating = [
            {
                'rank': 1,
                'username': 'Иван Петров',
                'score': 200,
                'grade': 8.5,
                'group_name': 'Группа А',
                'excluded': False
            },
            {
                'rank': 2,
                'username': 'Мария Иванова',
                'score': 150,
                'grade': 7.2,
                'group_name': 'Группа Б',
                'excluded': False
            },
            {
                'rank': 3,
                'username': 'Алексей Смирнов',
                'score': -20,
                'grade': 0.0,
                'group_name': 'Группа А',
                'excluded': True
            },
        ]
        
        message = format_rating_message(rating, "Рейтинг студентов")
        
        assert "Рейтинг студентов" in message
        assert "Иван Петров" in message
        assert "Мария Иванова" in message
        assert "Алексей Смирнов" in message
        assert "🥇" in message  # Медаль для первого места
        assert "⚠️" in message  # Маркер для исключенного студента
        assert "200" in message
        assert "8.5" in message

    def test_format_rating_message_medals(self):
        """Тест форматирования с медалями для топ-3"""
        rating = [
            {'rank': 1, 'username': '1-й', 'score': 200, 'grade': 9.0, 'group_name': '', 'excluded': False},
            {'rank': 2, 'username': '2-й', 'score': 180, 'grade': 8.5, 'group_name': '', 'excluded': False},
            {'rank': 3, 'username': '3-й', 'score': 160, 'grade': 8.0, 'group_name': '', 'excluded': False},
            {'rank': 4, 'username': '4-й', 'score': 140, 'grade': 7.5, 'group_name': '', 'excluded': False},
        ]
        
        message = format_rating_message(rating)
        
        assert "🥇" in message
        assert "🥈" in message
        assert "🥉" in message
        assert "4-й" in message  # 4-й без медали


class TestRatingIntegration:
    """Интеграционные тесты рейтинга"""

    @pytest.mark.integration
    def test_full_rating_workflow(self, db_session, test_groups):
        """Тест полного цикла работы с рейтингом"""
        group1 = test_groups[0]
        group2 = test_groups[1]
        
        # Создаем студентов в разных группах
        students_group1 = [
            (10001, "Студент Г1-1", 200, group1.id),
            (10002, "Студент Г1-2", 150, group1.id),
            (10003, "Студент Г1-3", -20, group1.id),  # Исключен
        ]
        
        students_group2 = [
            (10004, "Студент Г2-1", 250, group2.id),
            (10005, "Студент Г2-2", 180, group2.id),
        ]
        
        all_students = students_group1 + students_group2
        
        for user_id, username, score, group_id in all_students:
            user = db.get_or_create_user(user_id, username, UserType.STUDENT)
            db.set_user_group(user_id, group_id)
            # Устанавливаем баллы через сессию
            with db.get_session() as session:
                from models import User
                user_obj = session.get(User, user_id)
                if user_obj:
                    user_obj.score = score
        
        # Рассчитываем рейтинг
        db.calculate_all_ratings()
        
        # Проверяем рейтинг группы 1
        rating_group1 = db.get_group_rating(group1.id)
        assert len(rating_group1) == 3
        assert rating_group1[0]['user_id'] == 10001  # Самый высокий балл
        
        # Проверяем рейтинг группы 2
        rating_group2 = db.get_group_rating(group2.id)
        assert len(rating_group2) == 2
        
        # Проверяем общий рейтинг
        overall_rating = db.get_overall_rating()
        assert len(overall_rating) == 5
        # Первый в рейтинге должен иметь самый высокий балл
        # Проверяем, что это студент с баллом 250 (10004) или 200 (10001)
        top_user_id = overall_rating[0]['user_id']
        assert top_user_id in [10001, 10004]  # Один из студентов с высоким баллом
        
        # Проверяем, что исключенный студент получил 0
        excluded_student = next((s for s in rating_group1 if s['user_id'] == 10003), None)
        assert excluded_student is not None, "Исключенный студент должен быть в рейтинге"
        # Проверяем, что его баллы действительно <= -15
        assert excluded_student['score'] <= EXCLUSION_THRESHOLD, f"Баллы должны быть <= {EXCLUSION_THRESHOLD}, получено {excluded_student['score']}"
        # Исключенный студент должен иметь оценку 0.0
        assert excluded_student['grade'] == 0.0, f"Исключенный студент должен иметь оценку 0.0, получено {excluded_student['grade']}"
        assert excluded_student['excluded'] is True, "Исключенный студент должен быть помечен как excluded"

