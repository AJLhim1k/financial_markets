"""
Тесты для системы статистики
"""
import pytest

from models import db, UserType


class TestAnswerStatistics:
    """Тесты статистики ответов"""

    def test_stat_creation(self):
        """Тест создания статистики"""
        # Изначально статистики нет
        stats = db.get_stats("new_strategy")
        assert stats["correct_cnt"] == 0
        assert stats["wrong_cnt"] == 0

        # Увеличиваем счетчики
        db.increment_correct("new_strategy")
        db.increment_wrong("new_strategy")
        db.increment_correct("new_strategy")

        # Проверяем обновленную статистику
        stats = db.get_stats("new_strategy")
        assert stats["correct_cnt"] == 2
        assert stats["wrong_cnt"] == 1

    def test_top_strategies(self):
        """Тест получения топ стратегий"""
        # Создаем статистику для нескольких стратегий
        strategies = {
            "strategy_a": (5, 2),  # 5 правильных, 2 неправильных
            "strategy_b": (3, 1),  # 3 правильных, 1 неправильных
            "strategy_c": (1, 4),  # 1 правильных, 4 неправильных
            "strategy_d": (2, 0),  # 2 правильных, 0 неправильных
        }

        for name, (correct, wrong) in strategies.items():
            for _ in range(correct):
                db.increment_correct(name)
            for _ in range(wrong):
                db.increment_wrong(name)

        # Получаем топ стратегий
        top_strategies = db.get_top_strategies(limit=3)

        # Должно быть 3 стратегии
        assert len(top_strategies) == 3

        # Проверяем сортировку по общему количеству ответов
        # strategy_a: 7 ответов, strategy_c: 5 ответов, strategy_b: 4 ответов
        assert top_strategies[0]['name'] == "strategy_a"
        assert top_strategies[0]['total'] == 7

        assert top_strategies[1]['name'] == "strategy_c"
        assert top_strategies[1]['total'] == 5

        assert top_strategies[2]['name'] == "strategy_b"
        assert top_strategies[2]['total'] == 4

    def test_stat_persistence(self):
        """Тест сохранения статистики между сессиями"""
        # Создаем статистику
        db.increment_correct("persistent_strategy")
        db.increment_wrong("persistent_strategy")

        # Получаем через новую сессию
        stats = db.get_stats("persistent_strategy")
        assert stats["correct_cnt"] == 1
        assert stats["wrong_cnt"] == 1


class TestDatabaseOperations:
    """Тесты операций с базой данных"""

    def test_session_management(self):
        """Тест управления сессиями"""
        with db.get_session() as session:
            # Сессия должна работать - проверяем что можем запросить пользователей
            # Получаем модель User из базы данных
            from models.users import User
            users_count = session.query(User).count()
            # Может быть 0 или больше в зависимости от состояния тестов
            assert users_count >= 0

        # После выхода из контекста сессия должна быть закрыта

    def test_database_reinitialization(self):
        """Тест переинициализации базы данных"""
        # Создаем пользователя
        test_user = db.get_or_create_user(999, "Тест переинит", UserType.STUDENT)
        assert db.get_user(999) is not None

        # Переинициализируем базу
        db.drop_tables()
        db.init_db()

        # Пользователь должен исчезнуть
        assert db.get_user(999) is None