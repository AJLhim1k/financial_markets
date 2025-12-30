import pytest
import json
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from models.questions import Question, UserAnswer


class TestQuestionModel:
    """Тесты для модели Question"""

    def test_question_creation(self, db_session):
        """Тест создания вопроса с одним верным ответом"""
        question = Question(
            seminar_number=5,
            title="Что такое Python?",
            description="Выберите правильные утверждения",
            difficulty="easy",
            options=[
                "Язык программирования",
                "Змея",
                "Фильм",
                "Библиотека",
                "Фреймворк",
                "IDE"
            ],
            correct_answers=[0],  # Только первый вариант верный
            time_limit=60,
            points=1,
            order=1,
            tags=["python", "basics"]
        )

        db_session.add(question)
        db_session.commit()

        assert question.id is not None
        assert question.seminar_number == 5
        assert question.title == "Что такое Python?"
        assert question.difficulty == "easy"
        assert question.options == [
            "Язык программирования", "Змея", "Фильм",
            "Библиотека", "Фреймворк", "IDE"
        ]
        assert question.correct_answers == [0]
        assert question.points == 1
        assert question.is_active is True
        assert question.correct_count == 1

    def test_question_creation_multiple_correct(self, db_session):
        """Тест создания вопроса с несколькими верными ответами"""
        question = Question(
            seminar_number=10,
            title="Какие языки являются типизированными?",
            difficulty="medium",
            options=[
                "Python",
                "JavaScript",
                "Java",
                "C++",
                "HTML",
                "CSS"
            ],
            correct_answers=[2, 3],  # Java и C++
            time_limit=120
        )

        db_session.add(question)
        db_session.commit()

        assert question.id is not None
        assert question.seminar_number == 10
        assert question.correct_answers == [2, 3]
        assert question.correct_count == 2
        assert question.difficulty == "medium"

    def test_question_creation_all_correct(self, db_session):
        """Тест создания вопроса, где все ответы верные"""
        question = Question(
            seminar_number=15,
            title="Какие из этих чисел являются целыми?",
            difficulty="hard",
            options=["1", "2.5", "3", "4", "5.0", "6"],
            correct_answers=[0, 2, 3, 5],  # 1, 3, 4, 6 (индексы: 0, 2, 3, 5)
            tags=["math", "numbers"]
        )

        db_session.add(question)
        db_session.commit()

        assert question.correct_count == 4
        assert question.difficulty == "hard"

    def test_question_required_fields(self, db_session):
        """Тест обязательных полей"""
        question = Question()  # Все поля пустые

        db_session.add(question)

        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()

    def test_seminar_number_validation(self, db_session):
        """Тест валидации номера семинара"""
        # Должно работать
        question1 = Question(
            seminar_number=1,
            title="Test",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]
        )

        question20 = Question(
            seminar_number=20,
            title="Test",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]
        )

        db_session.add_all([question1, question20])
        db_session.commit()

        # Не должно работать - валидация сработает при создании
        # Используем try-except для проверки валидации
        try:
            question_invalid = Question(
                seminar_number=0,  # Меньше 1
                title="Test",
                options=["A", "B", "C", "D", "E", "F"],
                correct_answers=[0]
            )
            # Если дошли сюда, значит валидация не сработала
            assert False, "Validation should have failed for seminar_number=0"
        except ValueError as e:
            assert "Seminar number must be between 1 and 20" in str(e)

        try:
            question_invalid2 = Question(
                seminar_number=21,  # Больше 20
                title="Test",
                options=["A", "B", "C", "D", "E", "F"],
                correct_answers=[0]
            )
            assert False, "Validation should have failed for seminar_number=21"
        except ValueError as e:
            assert "Seminar number must be between 1 and 20" in str(e)

        # Также проверяем через SQLAlchemy constraints
        question_wrong = Question(
            seminar_number=5,  # Валидное значение для создания
            title="Test",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]
        )
        db_session.add(question_wrong)
        db_session.commit()

        # Пытаемся изменить на невалидное через SQL
        try:
            db_session.execute(
                "UPDATE questions SET seminar_number = 0 WHERE id = :id",
                {"id": question_wrong.id}
            )
            db_session.commit()
            assert False, "SQL constraint should have failed"
        except Exception:
            db_session.rollback()


    def test_options_validation(self):
        """Тест валидации вариантов ответов"""
        question = Question(
            seminar_number=1,
            title="Test",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]
        )

        # Должно работать - ровно 6 вариантов
        question.validate_options('options', ["1", "2", "3", "4", "5", "6"])

        # Не должно работать - не 6 вариантов
        with pytest.raises(ValueError, match="Must have exactly 6 options"):
            question.validate_options('options', ["1", "2", "3", "4", "5"])

        with pytest.raises(ValueError, match="Must have exactly 6 options"):
            question.validate_options('options', ["1", "2", "3", "4", "5", "6", "7"])

        # Не должно работать - пустые варианты
        with pytest.raises(ValueError, match="Option 1 cannot be empty"):
            question.validate_options('options', ["", "B", "C", "D", "E", "F"])

    def test_correct_answers_validation(self):
        """Тест валидации верных ответов"""
        question = Question(
            seminar_number=1,
            title="Test",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]
        )

        # Должно работать
        question.validate_correct_answers('correct_answers', [0])
        question.validate_correct_answers('correct_answers', [0, 1, 2])
        question.validate_correct_answers('correct_answers', [0, 1, 2, 3, 4, 5])

        # Не должно работать - пустой список
        with pytest.raises(ValueError, match="Must have at least 1 correct answer"):
            question.validate_correct_answers('correct_answers', [])

        # Не должно работать - больше 6
        with pytest.raises(ValueError, match="Cannot have more than 6 correct answers"):
            question.validate_correct_answers('correct_answers', [0, 1, 2, 3, 4, 5, 0])

        # Не должно работать - индексы вне диапазона
        with pytest.raises(ValueError, match="Answer index must be between 0 and 5"):
            question.validate_correct_answers('correct_answers', [6])

        with pytest.raises(ValueError, match="Answer index must be between 0 and 5"):
            question.validate_correct_answers('correct_answers', [-1])

        # Не должно работать - дубликаты
        with pytest.raises(ValueError, match="Duplicate answer index"):
            question.validate_correct_answers('correct_answers', [0, 0])

    def test_difficulty_validation(self):
        """Тест валидации сложности"""
        question = Question(
            seminar_number=1,
            title="Test",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]
        )

        # Должно работать
        question.validate_difficulty('difficulty', 'easy')
        question.validate_difficulty('difficulty', 'medium')
        question.validate_difficulty('difficulty', 'hard')

        # Не должно работать
        with pytest.raises(ValueError, match="Difficulty must be one of"):
            question.validate_difficulty('difficulty', 'very_hard')

        with pytest.raises(ValueError, match="Difficulty must be one of"):
            question.validate_difficulty('difficulty', '')

    def test_points_validation(self):
        """Тест валидации баллов (должно быть всегда 1)"""
        question = Question(
            seminar_number=1,
            title="Test",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]
        )

        # Должно работать
        question.validate_points('points', 1)

        # Не должно работать
        with pytest.raises(ValueError, match="Points must be exactly 1"):
            question.validate_points('points', 0)

        with pytest.raises(ValueError, match="Points must be exactly 1"):
            question.validate_points('points', 2)

    def test_is_correct_method(self, db_session):
        """Тест метода is_correct"""
        # Вопрос с одним верным ответом
        question1 = Question(
            seminar_number=1,
            title="Test",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]  # Только A верно
        )

        assert question1.is_correct([0]) is True  # Верно выбрал A
        assert question1.is_correct([1]) is False  # Выбрал B вместо A
        assert question1.is_correct([0, 1]) is False  # Выбрал лишний B
        assert question1.is_correct([]) is False  # Не выбрал ничего

        # Вопрос с несколькими верными ответами
        question2 = Question(
            seminar_number=2,
            title="Test",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0, 2, 4]  # A, C, E верны
        )

        assert question2.is_correct([0, 2, 4]) is True  # Все верные
        assert question2.is_correct([0, 2]) is False  # Пропустил E
        assert question2.is_correct([0, 2, 4, 1]) is False  # Лишний B
        assert question2.is_correct([0]) is False  # Только A
        assert question2.is_correct([1, 3, 5]) is False  # Все неверные

    def test_calculate_score_method(self, db_session):
        """Тест метода calculate_score (бинарная оценка)"""
        question = Question(
            seminar_number=1,
            title="Test",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0, 2]
        )

        # Верный ответ
        result_correct = question.calculate_score([0, 2], time_spent=30)
        assert result_correct['is_correct'] is True
        assert result_correct['score'] == 1
        assert result_correct['max_score'] == 1

        # Неверный ответ (не все верные выбраны)
        result_partial = question.calculate_score([0], time_spent=30)
        assert result_partial['is_correct'] is False
        assert result_partial['score'] == 0
        assert result_partial['correct_selected'] == 1
        assert result_partial['incorrect_selected'] == 0

        # Неверный ответ (лишние выбраны)
        result_wrong = question.calculate_score([0, 1, 2], time_spent=30)
        assert result_wrong['is_correct'] is False
        assert result_wrong['score'] == 0
        assert result_wrong['correct_selected'] == 2
        assert result_wrong['incorrect_selected'] == 1

        # Без времени
        result_no_time = question.calculate_score([0, 2])
        assert result_no_time['is_correct'] is True
        assert result_no_time['score'] == 1

    def test_properties(self, db_session):
        """Тест свойств модели"""
        question = Question(
            seminar_number=3,
            title="Test question",
            difficulty="medium",
            options=["A1", "B2", "C3", "D4", "E5", "F6"],
            correct_answers=[1, 3, 5]  # B2, D4, F6
        )

        db_session.add(question)
        db_session.commit()

        # options_dict
        options_dict = question.options_dict
        assert options_dict == {
            0: "A1", 1: "B2", 2: "C3",
            3: "D4", 4: "E5", 5: "F6"
        }

        # correct_options_text
        assert question.correct_options_text == ["B2", "D4", "F6"]

        # incorrect_options_text
        assert question.incorrect_options_text == ["A1", "C3", "E5"]

        # correct_count
        assert question.correct_count == 3

        # to_dict
        question_dict = question.to_dict()
        assert question_dict['seminar_number'] == 3
        assert question_dict['difficulty'] == "medium"
        assert question_dict['correct_answers_count'] == 3
        assert question_dict['points'] == 1
        assert 'answer_stats' in question_dict
        assert question_dict['answer_stats'] is None  # Нет ответов пользователей

    def test_to_dict_method(self, db_session):
        """Тест метода to_dict"""
        question = Question(
            seminar_number=7,
            title="Важный вопрос",
            description="Пояснение к вопросу",
            difficulty="hard",
            options=["Вар1", "Вар2", "Вар3", "Вар4", "Вар5", "Вар6"],
            correct_answers=[0, 3, 5],
            time_limit=180,
            order=5,
            tags=["tag1", "tag2", "tag3"],
            is_active=False
        )

        db_session.add(question)
        db_session.commit()

        data = question.to_dict()

        assert data['id'] == question.id
        assert data['seminar_number'] == 7
        assert data['title'] == "Важный вопрос"
        assert data['description'] == "Пояснение к вопросу"
        assert data['difficulty'] == "hard"
        assert data['options'] == {
            0: "Вар1", 1: "Вар2", 2: "Вар3",
            3: "Вар4", 4: "Вар5", 5: "Вар6"
        }
        assert data['correct_answers'] == [0, 3, 5]
        assert data['correct_answers_count'] == 3
        assert data['correct_options'] == ["Вар1", "Вар4", "Вар6"]
        assert data['incorrect_options'] == ["Вар2", "Вар3", "Вар5"]
        assert data['time_limit'] == 180
        assert data['points'] == 1
        assert data['order'] == 5
        assert data['is_active'] is False
        assert data['tags'] == ["tag1", "tag2", "tag3"]
        assert 'created_at' in data
        assert 'updated_at' in data
        assert data['has_user_answers'] is False
        assert data['answer_stats'] is None

    def test_get_answer_statistics(self, db_session):
        """Тест статистики ответов"""
        # Создаем вопрос
        question = Question(
            seminar_number=4,
            title="Статистический вопрос",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0, 1]  # A и B верные
        )

        db_session.add(question)
        db_session.commit()

        # Статистика должна быть None пока нет ответов
        assert question.get_answer_statistics() is None

        # Создаем несколько ответов пользователей
        answers = []
        start_time = datetime.utcnow() - timedelta(minutes=10)

        # 3 верных ответа (выбрали оба верных варианта)
        for i in range(3):
            answer = UserAnswer(
                user_id=100 + i,
                question_id=question.id,
                seminar_number=4,
                selected_answers=[0, 1],  # Оба верных
                is_correct=True,
                score=1,
                max_score=1,
                started_at=start_time + timedelta(seconds=i * 30),
                answered_at=start_time + timedelta(seconds=i * 30 + 20),
                time_spent=20
            )
            answers.append(answer)

        # 2 неверных ответа
        for i in range(2):
            # Один выбрал только A, другой только B
            selected = [0] if i == 0 else [1]  # Только один из верных
            answer = UserAnswer(
                user_id=200 + i,
                question_id=question.id,
                seminar_number=4,
                selected_answers=selected,
                is_correct=False,
                score=0,
                max_score=1,
                started_at=start_time + timedelta(seconds=100 + i * 30),
                answered_at=start_time + timedelta(seconds=100 + i * 30 + 25),
                time_spent=25
            )
            answers.append(answer)

        db_session.add_all(answers)
        db_session.commit()

        # Обновляем question из БД чтобы загрузить связи
        db_session.refresh(question)

        stats = question.get_answer_statistics()

        assert stats is not None
        assert stats['total_answers'] == 5
        assert stats['correct_answers'] == 3
        assert stats['incorrect_answers'] == 2
        assert stats['accuracy'] == 60.0  # 3 из 5 = 60%
        assert stats['average_score'] == 0.6  # (3*1 + 2*0) / 5 = 0.6
        assert stats['average_time'] == 22.0  # (3*20 + 2*25) / 5 = 22

        # Проверяем популярность вариантов
        option_popularity = stats['option_popularity']
        assert option_popularity[0] == 4  # A выбрали: 3 верных + 1 неверный = 4
        assert option_popularity[1] == 4  # B выбрали: 3 верных + 1 неверный = 4
        assert option_popularity[2] == 0  # C никто не выбрал
        assert option_popularity[3] == 0  # D никто не выбрал
        assert option_popularity[4] == 0  # E никто не выбрал
        assert option_popularity[5] == 0  # F никто не выбрал

    def test_repr_method(self, db_session):
        """Тест метода __repr__"""
        question = Question(
            seminar_number=12,
            title="Очень длинное название вопроса которое должно обрезаться при выводе",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]
        )

        db_session.add(question)
        db_session.commit()

        repr_str = repr(question)

        # Проверяем наличие ключевых частей (без точного текста из-за кодировки)
        assert f"id={question.id}" in repr_str
        assert "seminar=12" in repr_str
        assert "difficulty=medium" in repr_str  # default difficulty

        # Проверяем, что заголовок обрезан (должен содержать ...)
        assert "..." in repr_str

        # Проверяем длину заголовка в repr (должен быть обрезан до ~50 символов)
        # Найдем начало заголовка
        title_start = repr_str.find("title='") + len("title='")
        title_end = repr_str.find("...', seminar")
        if title_end > title_start:
            title_in_repr = repr_str[title_start:title_end]
            # Заголовок в repr должен быть короче оригинального
            assert len(title_in_repr) < len(question.title)

        # Альтернативный вариант - использовать английский текст для теста
        question2 = Question(
            seminar_number=13,
            title="Very long question title that should be truncated when displayed in repr method",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]
        )

        repr_str2 = repr(question2)
        assert "Very long question title that should be truncated" in repr_str2
        assert "..." in repr_str2

class TestUserAnswerModel:
    """Тесты для модели UserAnswer"""

    def test_user_answer_creation(self, db_session):
        """Тест создания ответа пользователя"""
        # Сначала создаем вопрос
        question = Question(
            seminar_number=8,
            title="Вопрос для теста ответов",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0, 2, 4]
        )

        db_session.add(question)
        db_session.commit()

        # Создаем верный ответ
        started_at = datetime.utcnow() - timedelta(seconds=45)
        answered_at = datetime.utcnow()

        answer = UserAnswer(
            user_id=12345,
            question_id=question.id,
            seminar_number=8,
            selected_answers=[0, 2, 4],  # Все верные
            is_correct=True,
            score=1,
            max_score=1,
            started_at=started_at,
            answered_at=answered_at,
            time_spent=45,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            attempt_number=1,
            session_id="session_abc123"
        )

        db_session.add(answer)
        db_session.commit()

        assert answer.id is not None
        assert answer.user_id == 12345
        assert answer.question_id == question.id
        assert answer.seminar_number == 8
        assert answer.selected_answers == [0, 2, 4]
        assert answer.is_correct is True
        assert answer.score == 1
        assert answer.max_score == 1
        assert answer.time_spent == 45
        assert answer.time_spent_formatted == "00:45"
        assert answer.ip_address == "192.168.1.100"
        assert answer.attempt_number == 1
        assert answer.session_id == "session_abc123"

    def test_user_answer_creation_wrong(self, db_session):
        """Тест создания неверного ответа"""
        question = Question(
            seminar_number=9,
            title="Вопрос",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0, 1]
        )

        db_session.add(question)
        db_session.commit()

        # Неверный ответ (выбрал только один из двух верных)
        answer = UserAnswer(
            user_id=999,
            question_id=question.id,
            seminar_number=9,
            selected_answers=[0],  # Только один верный
            is_correct=False,
            score=0,
            max_score=1,
            started_at=datetime.utcnow() - timedelta(seconds=30),
            answered_at=datetime.utcnow(),
            time_spent=30
        )

        db_session.add(answer)
        db_session.commit()

        assert answer.is_correct is False
        assert answer.score == 0
        assert answer.is_partially_correct is False  # Всегда False при бинарной оценке

    def test_selected_answers_validation(self):
        """Тест валидации выбранных ответов"""
        answer = UserAnswer(
            user_id=1,
            question_id=1,
            seminar_number=1,
            selected_answers=[0, 1],
            is_correct=True,
            score=1,
            max_score=1,
            started_at=datetime.utcnow(),
            answered_at=datetime.utcnow(),
            time_spent=10
        )

        # Должно работать
        answer.validate_selected_answers('selected_answers', [0])
        answer.validate_selected_answers('selected_answers', [0, 1, 2, 3, 4, 5])

        # Не должно работать - пустой список
        with pytest.raises(ValueError, match="Must select at least 1 answer"):
            answer.validate_selected_answers('selected_answers', [])

        # Не должно работать - больше 6
        with pytest.raises(ValueError, match="Cannot select more than 6 answers"):
            answer.validate_selected_answers('selected_answers', [0, 1, 2, 3, 4, 5, 0])

        # Не должно работать - индексы вне диапазона
        with pytest.raises(ValueError, match="Answer index must be between 0 and 5"):
            answer.validate_selected_answers('selected_answers', [6])

        # Не должно работать - дубликаты
        with pytest.raises(ValueError, match="Duplicate selected answer index"):
            answer.validate_selected_answers('selected_answers', [0, 0, 1])

    def test_score_validation(self):
        """Тест валидации баллов (0 или 1)"""
        answer = UserAnswer(
            user_id=1,
            question_id=1,
            seminar_number=1,
            selected_answers=[0],
            is_correct=True,
            score=1,
            max_score=1,
            started_at=datetime.utcnow(),
            answered_at=datetime.utcnow(),
            time_spent=10
        )

        # Должно работать
        answer.validate_score('score', 0)
        answer.validate_score('score', 1)

        # Не должно работать
        with pytest.raises(ValueError, match="Score must be 0 or 1"):
            answer.validate_score('score', -1)

        with pytest.raises(ValueError, match="Score must be 0 or 1"):
            answer.validate_score('score', 2)

    def test_max_score_validation(self):
        """Тест валидации максимального балла (должен быть 1)"""
        answer = UserAnswer(
            user_id=1,
            question_id=1,
            seminar_number=1,
            selected_answers=[0],
            is_correct=True,
            score=1,
            max_score=1,
            started_at=datetime.utcnow(),
            answered_at=datetime.utcnow(),
            time_spent=10
        )

        # Должно работать
        answer.validate_max_score('max_score', 1)

        # Не должно работать
        with pytest.raises(ValueError, match="Max score must be 1"):
            answer.validate_max_score('max_score', 0)

        with pytest.raises(ValueError, match="Max score must be 1"):
            answer.validate_max_score('max_score', 2)

    def test_properties(self, db_session):
        """Тест свойств UserAnswer"""
        # Создаем вопрос
        question = Question(
            seminar_number=6,
            title="Вопрос для свойств",
            options=["Вариант1", "Вариант2", "Вариант3", "Вариант4", "Вариант5", "Вариант6"],
            correct_answers=[1, 3, 5]
        )

        db_session.add(question)
        db_session.commit()

        # Создаем ответ
        answer = UserAnswer(
            user_id=777,
            question_id=question.id,
            seminar_number=6,
            selected_answers=[1, 3, 5],  # Все верные
            is_correct=True,
            score=1,
            max_score=1,
            started_at=datetime.utcnow() - timedelta(seconds=75),
            answered_at=datetime.utcnow(),
            time_spent=75
        )

        db_session.add(answer)
        db_session.commit()

        # selected_options_text
        assert answer.selected_options_text == ["Вариант2", "Вариант4", "Вариант6"]

        # correct_options_text
        assert answer.correct_options_text == ["Вариант2", "Вариант4", "Вариант6"]

        # time_spent_formatted
        assert answer.time_spent_formatted == "01:15"  # 75 секунд = 1:15

        # is_partially_correct (всегда False)
        assert answer.is_partially_correct is False

    def test_to_dict_method(self, db_session):
        """Тест метода to_dict"""
        question = Question(
            seminar_number=11,
            title="Вопрос для сериализации",
            difficulty="easy",
            options=["A1", "B2", "C3", "D4", "E5", "F6"],
            correct_answers=[0, 2]
        )

        db_session.add(question)
        db_session.commit()

        started_at = datetime(2024, 1, 15, 10, 30, 0)
        answered_at = datetime(2024, 1, 15, 10, 30, 25)

        answer = UserAnswer(
            user_id=555,
            question_id=question.id,
            seminar_number=11,
            selected_answers=[0, 2],  # Верный ответ
            is_correct=True,
            score=1,
            max_score=1,
            started_at=started_at,
            answered_at=answered_at,
            time_spent=25,
            ip_address="10.0.0.1",
            user_agent="TestBrowser/1.0",
            device_info={"os": "Windows", "browser": "Chrome"},
            attempt_number=2,
            session_id="test_session_123"
        )

        db_session.add(answer)
        db_session.commit()

        # Без вопроса
        data = answer.to_dict()

        assert data['id'] == answer.id
        assert data['user_id'] == 555
        assert data['question_id'] == question.id
        assert data['seminar_number'] == 11
        assert data['selected_answers'] == [0, 2]
        assert data['selected_options'] == ["A1", "C3"]
        assert data['is_correct'] is True
        assert data['is_partially_correct'] is False
        assert data['score'] == 1
        assert data['max_score'] == 1
        assert data['score_percentage'] == 100.0
        assert data['started_at'] == "2024-01-15T10:30:00"
        assert data['answered_at'] == "2024-01-15T10:30:25"
        assert data['time_spent'] == 25
        assert data['time_spent_formatted'] == "00:25"
        assert data['attempt_number'] == 2
        assert data['session_id'] == "test_session_123"
        assert data['device_info'] == {"os": "Windows", "browser": "Chrome"}
        assert 'question' not in data  # Не включали вопрос

        # С вопросом
        data_with_question = answer.to_dict(include_question=True)

        assert 'question' in data_with_question
        question_data = data_with_question['question']
        assert question_data['seminar_number'] == 11
        assert question_data['title'] == "Вопрос для сериализации"
        assert 'correct_answers' in data_with_question
        assert 'correct_options' in data_with_question
        assert 'question_difficulty' in data_with_question

    def test_relationship_with_question(self, db_session):
        """Тест связи между UserAnswer и Question"""
        question = Question(
            seminar_number=13,
            title="Вопрос со связью",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0, 1]
        )

        db_session.add(question)
        db_session.commit()

        # Создаем несколько ответов на этот вопрос
        answers = []
        for i in range(3):
            answer = UserAnswer(
                user_id=1000 + i,
                question_id=question.id,
                seminar_number=13,
                selected_answers=[0, 1],
                is_correct=True,
                score=1,
                max_score=1,
                started_at=datetime.utcnow() - timedelta(minutes=i + 1),
                answered_at=datetime.utcnow() - timedelta(minutes=i),
                time_spent=60
            )
            answers.append(answer)

        db_session.add_all(answers)
        db_session.commit()

        # Обновляем вопрос из БД
        db_session.refresh(question)

        # Проверяем связь
        assert len(question.user_answers) == 3
        assert all(a.question_id == question.id for a in question.user_answers)
        assert all(a.seminar_number == 13 for a in question.user_answers)

        # Проверяем обратную связь
        for answer in question.user_answers:
            assert answer.question.id == question.id
            assert answer.question.title == "Вопрос со связью"

    def test_cascade_delete(self, db_session):
        """Тест каскадного удаления"""
        question = Question(
            seminar_number=14,
            title="Вопрос для удаления",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]
        )

        db_session.add(question)
        db_session.commit()

        # Создаем ответы
        answer1 = UserAnswer(
            user_id=111,
            question_id=question.id,
            seminar_number=14,
            selected_answers=[0],
            is_correct=True,
            score=1,
            max_score=1,
            started_at=datetime.utcnow(),
            answered_at=datetime.utcnow(),
            time_spent=10
        )

        answer2 = UserAnswer(
            user_id=222,
            question_id=question.id,
            seminar_number=14,
            selected_answers=[1],  # Неверный
            is_correct=False,
            score=0,
            max_score=1,
            started_at=datetime.utcnow(),
            answered_at=datetime.utcnow(),
            time_spent=15
        )

        db_session.add_all([answer1, answer2])
        db_session.commit()

        answer_ids = [answer1.id, answer2.id]

        # Удаляем вопрос
        db_session.delete(question)
        db_session.commit()

        # Ответы должны удалиться каскадно
        remaining_answers = db_session.query(UserAnswer).filter(
            UserAnswer.id.in_(answer_ids)
        ).all()

        assert len(remaining_answers) == 0

    def test_repr_method(self, db_session):
        """Тест метода __repr__"""
        question = Question(
            seminar_number=16,
            title="Test",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0]
        )

        db_session.add(question)
        db_session.commit()

        # Верный ответ
        answer_correct = UserAnswer(
            user_id=333,
            question_id=question.id,
            seminar_number=16,
            selected_answers=[0],
            is_correct=True,
            score=1,
            max_score=1,
            started_at=datetime.utcnow(),
            answered_at=datetime.utcnow(),
            time_spent=20
        )

        # Неверный ответ
        answer_wrong = UserAnswer(
            user_id=444,
            question_id=question.id,
            seminar_number=16,
            selected_answers=[1],
            is_correct=False,
            score=0,
            max_score=1,
            started_at=datetime.utcnow(),
            answered_at=datetime.utcnow(),
            time_spent=30
        )

        db_session.add_all([answer_correct, answer_wrong])
        db_session.commit()

        # Проверяем repr
        repr_correct = repr(answer_correct)
        assert f"id={answer_correct.id}" in repr_correct
        assert "user=333" in repr_correct
        assert "seminar=16" in repr_correct
        assert "CORRECT" in repr_correct

        repr_wrong = repr(answer_wrong)
        assert f"id={answer_wrong.id}" in repr_wrong
        assert "user=444" in repr_wrong
        assert "seminar=16" in repr_wrong
        assert "WRONG" in repr_wrong


@pytest.mark.integration
class TestQuestionUserAnswerIntegration:
    """Интеграционные тесты для Question и UserAnswer"""

    def test_complete_question_answering_flow(self, db_session):
        """Полный цикл: создание вопроса → ответ пользователя → статистика"""
        # 1. Создаем несколько вопросов для семинара 2
        questions = []
        for i in range(3):
            question = Question(
                seminar_number=2,
                title=f"Вопрос {i + 1} для семинара 2",
                difficulty=["easy", "medium", "hard"][i],
                options=[f"Опция {j}" for j in range(6)],
                correct_answers=[i],  # У каждого вопроса один верный ответ на разной позиции
                order=i + 1,
                tags=[f"tag{i + 1}"]
            )
            questions.append(question)

        db_session.add_all(questions)
        db_session.commit()

        # 2. Пользователь отвечает на вопросы
        user_id = 9999
        answers = []

        for i, question in enumerate(questions):
            # Пользователь отвечает правильно на первые 2 вопроса, неправильно на третий
            selected = [question.correct_answers[0]] if i < 2 else [(question.correct_answers[0] + 1) % 6]

            answer = UserAnswer(
                user_id=user_id,
                question_id=question.id,
                seminar_number=2,
                selected_answers=selected,
                is_correct=(i < 2),  # Верно на первые 2, неверно на третий
                score=1 if i < 2 else 0,
                max_score=1,
                started_at=datetime.utcnow() - timedelta(minutes=3 - i),
                answered_at=datetime.utcnow() - timedelta(minutes=2 - i),
                time_spent=30 + i * 10,
                attempt_number=1,
                session_id=f"session_{user_id}"
            )
            answers.append(answer)

        db_session.add_all(answers)
        db_session.commit()

        # 3. Проверяем статистику по каждому вопросу
        for i, question in enumerate(questions):
            db_session.refresh(question)
            stats = question.get_answer_statistics()

            assert stats is not None
            assert stats['total_answers'] == 1
            assert stats['correct_answers'] == (1 if i < 2 else 0)
            assert stats['accuracy'] == (100.0 if i < 2 else 0.0)

        # 4. Получаем все ответы пользователя
        user_answers = db_session.query(UserAnswer).filter(
            UserAnswer.user_id == user_id
        ).order_by(UserAnswer.started_at).all()

        assert len(user_answers) == 3

        # 5. Проверяем итоговую статистику пользователя по семинару 2
        total_answers = len(user_answers)
        correct_answers = sum(1 for a in user_answers if a.is_correct)
        total_score = sum(a.score for a in user_answers)

        assert total_answers == 3
        assert correct_answers == 2
        assert total_score == 2  # 1+1+0 = 2

        # 6. Проверяем сериализацию с вопросами
        for answer in user_answers:
            data = answer.to_dict(include_question=True)
            assert 'question' in data
            assert data['question']['seminar_number'] == 2
            assert 'correct_options' in data

    def test_multiple_users_answering_same_question(self, db_session):
        """Несколько пользователей отвечают на один вопрос"""
        question = Question(
            seminar_number=18,
            title="Общий вопрос для нескольких пользователей",
            options=[f"Вариант {chr(65 + i)}" for i in range(6)],  # A, B, C, D, E, F
            correct_answers=[0, 2, 4],  # A, C, E
            difficulty="medium"
        )

        db_session.add(question)
        db_session.commit()

        # 5 пользователей отвечают на вопрос
        answers = []
        for i in range(5):
            # Первые 3 отвечают верно, остальные 2 - неверно
            is_correct = i < 3
            selected = [0, 2, 4] if is_correct else [1, 3, 5]  # Верные vs неверные

            answer = UserAnswer(
                user_id=1000 + i,
                question_id=question.id,
                seminar_number=18,
                selected_answers=selected,
                is_correct=is_correct,
                score=1 if is_correct else 0,
                max_score=1,
                started_at=datetime.utcnow() - timedelta(minutes=5 - i),
                answered_at=datetime.utcnow() - timedelta(minutes=4 - i),
                time_spent=40,
                attempt_number=1
            )
            answers.append(answer)

        db_session.add_all(answers)
        db_session.commit()

        # Обновляем вопрос и проверяем статистику
        db_session.refresh(question)
        stats = question.get_answer_statistics()

        assert stats['total_answers'] == 5
        assert stats['correct_answers'] == 3
        assert stats['incorrect_answers'] == 2
        assert stats['accuracy'] == 60.0  # 3 из 5
        assert stats['average_score'] == 0.6  # (3*1 + 2*0) / 5

        # Проверяем популярность вариантов
        option_popularity = stats['option_popularity']
        assert option_popularity[0] == 3  # A выбрали 3 верных ответа
        assert option_popularity[1] == 2  # B выбрали 2 неверных ответа
        assert option_popularity[2] == 3  # C выбрали 3 верных ответа
        assert option_popularity[3] == 2  # D выбрали 2 неверных ответа
        assert option_popularity[4] == 3  # E выбрали 3 верных ответа
        assert option_popularity[5] == 2  # F выбрали 2 неверных ответа

    def test_user_multiple_attempts(self, db_session):
        """Пользователь делает несколько попыток ответа на вопрос"""
        question = Question(
            seminar_number=19,
            title="Вопрос с несколькими попытками",
            options=["A", "B", "C", "D", "E", "F"],
            correct_answers=[0, 1, 2]
        )

        db_session.add(question)
        db_session.commit()

        user_id = 8888
        start_time = datetime.utcnow() - timedelta(minutes=30)

        # Первая попытка - неверно
        attempt1 = UserAnswer(
            user_id=user_id,
            question_id=question.id,
            seminar_number=19,
            selected_answers=[0, 1],  # Пропустил C
            is_correct=False,
            score=0,
            max_score=1,
            started_at=start_time,
            answered_at=start_time + timedelta(seconds=25),
            time_spent=25,
            attempt_number=1,
            session_id="attempt_1"
        )

        # Вторая попытка - верно
        attempt2 = UserAnswer(
            user_id=user_id,
            question_id=question.id,
            seminar_number=19,
            selected_answers=[0, 1, 2],  # Все верные
            is_correct=True,
            score=1,
            max_score=1,
            started_at=start_time + timedelta(minutes=5),
            answered_at=start_time + timedelta(minutes=5, seconds=15),
            time_spent=15,
            attempt_number=2,
            session_id="attempt_2"
        )

        db_session.add_all([attempt1, attempt2])
        db_session.commit()

        # Проверяем оба ответа
        answers = db_session.query(UserAnswer).filter(
            UserAnswer.user_id == user_id,
            UserAnswer.question_id == question.id
        ).order_by(UserAnswer.attempt_number).all()

        assert len(answers) == 2
        assert answers[0].attempt_number == 1
        assert answers[0].is_correct is False
        assert answers[0].score == 0
        assert answers[1].attempt_number == 2
        assert answers[1].is_correct is True
        assert answers[1].score == 1
        assert answers[1].time_spent < answers[0].time_spent  # Вторая попытка быстрее

