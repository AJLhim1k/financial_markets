from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, aliased
from sqlalchemy.exc import IntegrityError
from .users import Base, User, UserType, AnswerStat
from .logs import ScoreChangeLog, OperationLog
from .groups import Group
from sqlalchemy.orm import relationship, configure_mappers


# Класс для управления базой данных
class DatabaseManager:
    def __init__(self, db_url="sqlite:///users.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    def get_session(self):
        """Контекстный менеджер для получения сессии базы данных"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def drop_tables(self):
        """Удаляет все таблицы (для тестирования)"""
        Base.metadata.drop_all(self.engine)

    def init_db(self):
        """Инициализирует базу данных (создает таблицы)"""
        Base.metadata.create_all(self.engine)

    # Методы для работы с логами (перенесены из logs.py)
    def log_operation(self, user_id, operation_type):
        """Записывает лог операции в базу данных"""
        with self.get_session() as session:
            log_entry = OperationLog(
                user_id=user_id,
                operation_type=operation_type
            )
            session.add(log_entry)

    def get_operation_logs(self, user_id=None, operation_type=None, limit=100):
        """Получает логи операций"""
        with self.get_session() as session:
            query = session.query(OperationLog).order_by(OperationLog.created_at.desc())

            if user_id:
                query = query.filter(OperationLog.user_id == user_id)

            if operation_type:
                query = query.filter(OperationLog.operation_type == operation_type)

            logs = query.limit(limit).all()

            return [{
                'id': log.id,
                'user_id': log.user_id,
                'operation_type': log.operation_type,
                'created_at': log.created_at,
                'username': log.user.username if log.user else None
            } for log in logs]

    def get_score_change_log(self, user_id=None, limit=50):
        """Получает логи изменений баллов"""
        with self.get_session() as session:
            UserAlias1 = aliased(User)
            UserAlias2 = aliased(User)

            query = session.query(
                ScoreChangeLog,
                UserAlias1.username.label('user_username'),
                UserAlias2.username.label('changer_username')
            ).join(
                UserAlias1, ScoreChangeLog.user_id == UserAlias1.id
            ).join(
                UserAlias2, ScoreChangeLog.changed_by_id == UserAlias2.id
            ).order_by(ScoreChangeLog.change_time.desc())

            if user_id:
                query = query.filter(ScoreChangeLog.user_id == user_id)

            results = query.limit(limit).all()

            logs = []
            for log_entry, user_username, changer_username in results:
                logs.append({
                    'id': log_entry.id,
                    'user_id': log_entry.user_id,
                    'changed_by_id': log_entry.changed_by_id,
                    'old_score': log_entry.old_score,
                    'new_score': log_entry.new_score,
                    'delta': log_entry.delta,
                    'change_time': log_entry.change_time,
                    'user_username': user_username,
                    'changer_username': changer_username
                })

            return logs

    # Методы для работы с пользователями (перенесены из users.py)
    def get_or_create_user(self, user_id, username, user_type=UserType.STUDENT):
        """Получает или создает пользователя"""
        with self.get_session() as session:
            user = session.get(User, user_id)
            if user:
                if user.username != username:
                    user.username = username
                if user.user_type != user_type and user_type != UserType.STUDENT:
                    user.user_type = user_type
                return user
            else:
                # 👇 ДОБАВЬ ЭТОТ КОД 👇
                # Проверяем, является ли пользователь админом из .env
                import os
                admin_ids_str = os.getenv("ADMIN_IDS", "")
                if admin_ids_str:
                    admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
                    if user_id in admin_ids:
                        user_type = UserType.ADMIN
                        print(f"✅ Пользователь {user_id} создан как АДМИН (из ADMIN_IDS)")
                # 👆 КОНЕЦ ДОБАВЛЕННОГО КОДА 👆

                user = User(
                    id=user_id,
                    username=username,
                    user_type=user_type,
                    last_request_date=datetime.now().date()
                )
                session.add(user)
                return user
    def register_user_request(self, user_id):
        """Регистрирует запрос пользователя"""
        today = datetime.now().date()
        with self.get_session() as session:
            user = session.get(User, user_id)
            if user:
                if user.last_request_date != today:
                    user.requests_today = 1
                    user.last_request_date = today
                else:
                    user.requests_today += 1

    def update_existing_admins(self):
        """Обновляет существующих пользователей из ADMIN_IDS в админы"""
        import os
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        if not admin_ids_str:
            return

        admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

        with self.get_session() as session:
            for admin_id in admin_ids:
                user = session.get(User, admin_id)
                if user and user.user_type != UserType.ADMIN:
                    print(f"🔄 Обновление пользователя {admin_id} до админа")
                    user.user_type = UserType.ADMIN

    def can_user_request(self, user_id, max_attempts=100):
        """Проверяет, может ли пользователь сделать запрос"""
        today = datetime.now().date()
        with self.get_session() as session:
            user = session.get(User, user_id)

            if not user:
                return max_attempts

            if user.last_request_date != today:
                return max_attempts

            remaining = max_attempts - user.requests_today
            return remaining if remaining > 0 else 0

    def update_score(self, user_id, delta, changed_by_id=None):
        """Обновляет баллы пользователя с логированием"""
        with self.get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise ValueError(f"User with id {user_id} not found")

            if changed_by_id:
                changer = session.get(User, changed_by_id)
                if not changer:
                    raise ValueError(f"Changer with id {changed_by_id} not found")

                # Логируем операцию изменения баллов
                self.log_operation(
                    user_id=changed_by_id,
                    operation_type='change_score'
                )

                old_score, new_score = changer.change_user_score(user, delta, session)
                return old_score, new_score
            else:
                old_score = user.score
                user.score += delta
                return old_score, user.score

    def get_score(self, user_id):
        """Получает баллы пользователя"""
        with self.get_session() as session:
            user = session.get(User, user_id)
            return user.score if user else 0

    def get_top_players(self, limit=3):
        """Получает топ игроков"""
        with self.get_session() as session:
            users = session.query(User) \
                .filter(User.user_type == UserType.STUDENT) \
                .order_by(User.score.desc()) \
                .limit(limit).all()
            return [{'username': user.username, 'score': user.score} for user in users]

    def get_user_position(self, user_id):
        """Получает позицию пользователя в рейтинге"""
        with self.get_session() as session:
            users = session.query(User) \
                .filter(User.user_type == UserType.STUDENT) \
                .order_by(User.score.desc()).all()

            for idx, user in enumerate(users, start=1):
                if user.id == user_id:
                    return idx, user.score

            return len(users) + 1, 0

    def get_full_rating(self):
        """Получает полный рейтинг"""
        with self.get_session() as session:
            users = session.query(User) \
                .filter(User.user_type == UserType.STUDENT) \
                .order_by(User.score.desc()).all()
            return [{'id': user.id, 'username': user.username, 'score': user.score}
                    for user in users]

    def get_user_requests_today(self, user_id):
        """Получает количество запросов пользователя сегодня"""
        with self.get_session() as session:
            user = session.get(User, user_id)
            return user.requests_today if user else 0

    def change_user_type(self, user_id, new_type, changed_by_id=None):
        """Изменяет тип пользователя"""
        with self.get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise ValueError(f"User with id {user_id} not found")

            old_type = user.user_type
            user.user_type = new_type

            # Логируем операцию изменения типа пользователя
            if changed_by_id:
                self.log_operation(
                    user_id=changed_by_id,
                    operation_type='change_user_type'
                )

            return old_type, new_type

    def get_user(self, user_id):
        """Получает пользователя по ID"""
        with self.get_session() as session:
            return session.get(User, user_id)

    def get_users_by_type(self, user_type):
        """Получает всех пользователей определенного типа"""
        with self.get_session() as session:
            return session.query(User).filter(User.user_type == user_type).all()

    # Методы для работы со статистикой ответов
    def increment_correct(self, name):
        """Увеличивает счетчик правильных ответов"""
        with self.get_session() as session:
            stat = session.query(AnswerStat).filter(AnswerStat.name == name).first()
            if not stat:
                stat = AnswerStat(name=name, correct_cnt=1)
                session.add(stat)
            else:
                stat.correct_cnt += 1

    def increment_wrong(self, name):
        """Увеличивает счетчик неправильных ответов"""
        with self.get_session() as session:
            stat = session.query(AnswerStat).filter(AnswerStat.name == name).first()
            if not stat:
                stat = AnswerStat(name=name, wrong_cnt=1)
                session.add(stat)
            else:
                stat.wrong_cnt += 1

    def get_stats(self, name):
        """Получает статистику по имени"""
        with self.get_session() as session:
            stat = session.query(AnswerStat).filter(AnswerStat.name == name).first()
            if stat:
                return {"correct_cnt": stat.correct_cnt, "wrong_cnt": stat.wrong_cnt}
            return {"correct_cnt": 0, "wrong_cnt": 0}

    def get_top_strategies(self, limit=4):
        """Получает топ стратегий"""
        with self.get_session() as session:
            stats = session.query(AnswerStat) \
                .filter(AnswerStat.name != 'none') \
                .order_by((AnswerStat.correct_cnt + AnswerStat.wrong_cnt).desc()) \
                .limit(limit).all()

            return [{
                'name': stat.name,
                'correct_cnt': stat.correct_cnt,
                'wrong_cnt': stat.wrong_cnt,
                'total': stat.correct_cnt + stat.wrong_cnt
            } for stat in stats]

    # Методы для работы с группами (перенесены из groups.py)
    def create_group(self, name, max_students=25, transfer_deadline=None):
        """Создает новую группу"""
        with self.get_session() as session:
            group = Group(name=name, max_students=max_students, transfer_deadline=transfer_deadline)
            session.add(group)
            return group

    def get_group(self, group_id):
        """Получает группу по ID"""
        with self.get_session() as session:
            return session.get(Group, group_id)

    def get_all_groups(self):
        """Получает все группы"""
        with self.get_session() as session:
            return session.query(Group).all()

    def set_user_group(self, user_id, group_id, changed_by_id=None):
        """Назначает пользователя в группу (админ может всегда, студент - с ограничениями)"""
        with self.get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise ValueError(f"User with id {user_id} not found")

            group = session.get(Group, group_id)
            if not group:
                raise ValueError(f"Group with id {group_id} not found")

            old_group = user.group

            # Проверяем права
            if changed_by_id:
                changer = session.get(User, changed_by_id)
                if changer and changer.user_type == UserType.ADMIN:
                    # Админ может всегда менять группу
                    user.group = group

                    # Логируем операцию
                    self.log_operation(
                        user_id=changed_by_id,
                        operation_type='admin_change_group'
                    )

                    return old_group, group
                elif changer and changer.id == user_id:
                    # Студент пытается сменить свою группу
                    return self._student_change_group(user, group, session)
                else:
                    raise PermissionError("Недостаточно прав для смены группы")
            else:
                # Системное изменение
                user.group = group
                return old_group, group

    def _student_change_group(self, user, new_group, session):
        """Обрабатывает смену группы студентом"""
        if user.user_type != UserType.STUDENT:
            raise PermissionError("Только студенты могут менять группы самостоятельно")

        # Проверяем ограничения
        can_join, message = new_group.can_join()
        if not can_join:
            raise ValueError(message)

        old_group = user.group
        user.group = new_group

        # Логируем операцию
        self.log_operation(
            user_id=user.id,
            operation_type='student_change_group'
        )

        return old_group, new_group

    def set_transfer_deadline(self, group_id, deadline, changed_by_id):
        """Устанавливает дедлайн для перехода в группу (только админ)"""
        with self.get_session() as session:
            group = session.get(Group, group_id)
            if not group:
                raise ValueError(f"Group with id {group_id} not found")

            changer = session.get(User, changed_by_id)
            if not changer or changer.user_type != UserType.ADMIN:
                raise PermissionError("Только админ может устанавливать дедлайн")

            old_deadline = group.transfer_deadline
            group.transfer_deadline = deadline

            # Логируем операцию
            self.log_operation(
                user_id=changed_by_id,
                operation_type='set_transfer_deadline'
            )

            return old_deadline, deadline

    def get_group_students(self, group_id):
        """Получает всех студентов в группе"""
        with self.get_session() as session:
            group = session.get(Group, group_id)
            if group:
                return [s for s in group.students if s.user_type == UserType.STUDENT]
            return []

    def get_available_groups_for_student(self, user_id):
        """Получает группы, в которые студент может перейти"""
        with self.get_session() as session:
            user = session.get(User, user_id)
            if not user or user.user_type != UserType.STUDENT:
                return []

            all_groups = session.query(Group).all()
            available_groups = []

            for group in all_groups:
                can_join, message = group.can_join()
                current_group_id = user.group.id if user.group else None
                if can_join and group.id != current_group_id:
                    student_count = len([s for s in group.students if s.user_type == UserType.STUDENT])
                    available_groups.append({
                        'id': group.id,
                        'name': group.name,
                        'current_students': student_count,
                        'max_students': group.max_students,
                        'transfer_deadline': group.transfer_deadline
                    })

            return available_groups

    # Методы для работы с рейтингом
    def save_rating(self, user_id, group_id=None, rating_type='group', rank=None, 
                    grade=None, score=None, excluded=False, cdf_value=None):
        """
        Сохраняет оценку за семинары для пользователя
        
        Args:
            user_id: ID пользователя
            group_id: ID группы (None для общего рейтинга)
            rating_type: Тип рейтинга ('group' или 'overall')
            rank: Позиция в рейтинге
            grade: Оценка за семинары (0-10)
            score: Баллы пользователя
            excluded: Исключен ли из расчета
            cdf_value: Значение CDF для нормального распределения
        """
        with self.get_session() as session:
            user = session.get(User, user_id)
            if user:
                # Сохраняем оценку за семинары в колонку пользователя
                if grade is not None:
                    user.seminar_grade = grade

    def get_ratings_from_db(self, group_id=None, rating_type='group'):
        """
        Получает рейтинг из БД (читает из колонки seminar_grade пользователей)
        
        Args:
            group_id: ID группы (None для общего рейтинга)
            rating_type: Тип рейтинга ('group' или 'overall')
            
        Returns:
            Список словарей с информацией о рейтинге или None, если рейтинг не рассчитан
        """
        with self.get_session() as session:
            # Проверяем, есть ли хотя бы один студент с рассчитанным рейтингом
            query = session.query(User).filter(User.user_type == UserType.STUDENT)
            
            if group_id:
                query = query.filter(User.group_id == group_id)
            
            # Проверяем, есть ли хотя бы один студент с рассчитанным рейтингом
            has_rating = query.filter(User.seminar_grade.isnot(None)).first()
            
            if not has_rating:
                return None
            
            # Получаем всех студентов
            students = query.all()
            
            if not students:
                return None
            
            # Формируем рейтинг
            rating = []
            EXCLUSION_THRESHOLD = -15  # Порог исключения из расчета
            for student in students:
                if student.seminar_grade is not None:
                    rating_entry = {
                        'user_id': student.id,
                        'username': student.username,
                        'score': student.score,
                        'grade': round(student.seminar_grade, 2),
                        'excluded': student.score <= EXCLUSION_THRESHOLD,
                        'group_id': student.group_id,
                        'group_name': student.group.name if student.group else 'Без группы'
                    }
                    rating.append(rating_entry)
            
            # Сортируем по убыванию оценки, затем по убыванию баллов
            rating.sort(key=lambda x: (x['grade'], x['score']), reverse=True)
            
            # Добавляем ранги
            for rank, entry in enumerate(rating, start=1):
                entry['rank'] = rank
            
            return rating if rating else None

    def clear_ratings(self, group_id=None, rating_type='group'):
        """
        Очищает рейтинги (устанавливает seminar_grade в None)
        
        Args:
            group_id: ID группы (None для всех групп)
            rating_type: Тип рейтинга ('group' или 'overall')
        """
        with self.get_session() as session:
            query = session.query(User).filter(User.user_type == UserType.STUDENT)
            
            if group_id:
                query = query.filter(User.group_id == group_id)
            
            students = query.all()
            for student in students:
                student.seminar_grade = None

    def update_user_seminar_grade(self, user_id, grade):
        """
        Обновляет оценку за семинары для конкретного пользователя
        
        Args:
            user_id: ID пользователя
            grade: Оценка за семинары (0-10)
        """
        with self.get_session() as session:
            user = session.get(User, user_id)
            if user:
                user.seminar_grade = grade

    def calculate_all_ratings(self):
        """
        Рассчитывает и сохраняет рейтинг для всех студентов.
        µ и σ рассчитываются по всем студентам с баллами > -15.
        """
        from .rating import calculate_grades
        
        with self.get_session() as session:
            # Получаем всех студентов
            all_students = session.query(User).filter(
                User.user_type == UserType.STUDENT
            ).all()
            
            if not all_students:
                return
            
            # Подготавливаем данные для расчета оценок
            students_data = [(student.id, student.score) for student in all_students]
            
            # Рассчитываем оценки
            grades_dict = calculate_grades(students_data)
            
            # Сохраняем оценки в БД
            for user_id, grade_info in grades_dict.items():
                user = session.get(User, user_id)
                if user:
                    grade = grade_info.get('grade', 0.0)
                    user.seminar_grade = grade

    def get_group_rating(self, group_id: int) -> List[Dict]:
        """
        Получает рейтинг студентов в группе из БД или рассчитывает если его нет.
        Оценки рассчитываются на основе всех студентов (µ и σ по всем студентам).
        
        Args:
            group_id: ID группы
            
        Returns:
            Список словарей с информацией о студентах и их рейтинге
        """
        # Пытаемся получить из БД
        cached_rating = self.get_ratings_from_db(group_id=group_id, rating_type='group')
        if cached_rating:
            return cached_rating
        
        # Если в БД нет, нужно сначала рассчитать оценки для всех студентов
        # Проверяем, есть ли уже рассчитанные оценки
        with self.get_session() as session:
            # Проверяем, есть ли хотя бы один студент с рассчитанной оценкой
            has_rating = session.query(User).filter(
                User.user_type == UserType.STUDENT,
                User.seminar_grade.isnot(None)
            ).first()
            
            if not has_rating:
                # Рассчитываем оценки для всех студентов
                self.calculate_all_ratings()
        
        # Теперь получаем студентов группы с их оценками
        with self.get_session() as session:
            group = session.get(Group, group_id)
            if not group:
                return []

            # Получаем всех студентов группы
            students = [s for s in group.students if s.user_type == UserType.STUDENT]
            if not students:
                return []

            # Создаем рейтинг (сортируем по убыванию оценки, затем по убыванию баллов)
            rating = []
            sorted_students = sorted(
                students,
                key=lambda s: (s.seminar_grade or 0, s.score),
                reverse=True
            )

            EXCLUSION_THRESHOLD = -15
            for rank, student in enumerate(sorted_students, start=1):
                grade = student.seminar_grade or 0.0
                excluded = student.score <= EXCLUSION_THRESHOLD

                rating_entry = {
                    'user_id': student.id,
                    'username': student.username,
                    'score': student.score,
                    'rank': rank,
                    'grade': round(grade, 2),  # Оценка в 10-балльной системе
                    'excluded': excluded,
                    'cdf_value': 0.0,
                    'group_id': group_id,
                    'group_name': group.name
                }
                rating.append(rating_entry)

            return rating

    def get_overall_rating(self) -> List[Dict]:
        """
        Получает общий рейтинг всех студентов по всем группам из БД или рассчитывает если его нет.
        Оценки рассчитываются на основе всех студентов (µ и σ по всем студентам).
        
        Returns:
            Список словарей с информацией о студентах и их рейтинге
        """
        # Пытаемся получить из БД
        cached_rating = self.get_ratings_from_db(group_id=None, rating_type='overall')
        if cached_rating:
            return cached_rating
        
        # Если в БД нет, рассчитываем и сохраняем
        self.calculate_all_ratings()
        
        # Теперь получаем всех студентов с их оценками
        with self.get_session() as session:
            # Получаем всех студентов
            students = session.query(User).filter(
                User.user_type == UserType.STUDENT
            ).all()

            if not students:
                return []

            # Создаем общий рейтинг (сортируем по убыванию оценки, затем по убыванию баллов)
            rating = []
            sorted_students = sorted(
                students,
                key=lambda s: (s.seminar_grade or 0, s.score),
                reverse=True
            )

            EXCLUSION_THRESHOLD = -15
            for rank, student in enumerate(sorted_students, start=1):
                grade = student.seminar_grade or 0.0
                excluded = student.score <= EXCLUSION_THRESHOLD

                rating_entry = {
                    'user_id': student.id,
                    'username': student.username,
                    'score': student.score,
                    'rank': rank,
                    'grade': round(grade, 2),  # Оценка в 10-балльной системе
                    'excluded': excluded,
                    'cdf_value': 0.0,
                    'group_id': student.group_id,
                    'group_name': student.group.name if student.group else 'Без группы'
                }
                rating.append(rating_entry)

            return rating

    def recalculate_all_ratings(self):
        """
        Пересчитывает все рейтинги (групповые и общий) и сохраняет в БД.
        µ и σ рассчитываются по всем студентам с баллами > -15.
        """
        # Очищаем старые рейтинги
        self.clear_ratings()
        
        # Рассчитываем и сохраняем оценки для всех студентов
        self.calculate_all_ratings()

    def recalculate_group_rating(self, group_id: int):
        """
        Пересчитывает рейтинг для конкретной группы.
        Поскольку µ и σ рассчитываются по всем студентам, нужно пересчитать все оценки.
        
        Args:
            group_id: ID группы
        """
        # Пересчитываем все оценки (т.к. µ и σ зависят от всех студентов)
        self.recalculate_all_ratings()

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
            with self.get_session() as session:
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
        import numpy as np
        
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


# Создаем глобальный экземпляр менеджера БД
db = DatabaseManager()


# Функции для обратной совместимости
def drop_db():
    db.drop_tables()


def init_db():
    db.init_db()


def get_or_create_user(user_id, username):
    return db.get_or_create_user(user_id, username)


def register_user_request(user_id):
    db.register_user_request(user_id)


def can_user_request(user_id, max_attempts=100):
    return db.can_user_request(user_id, max_attempts)


def update_score(user_id, delta):
    return db.update_score(user_id, delta)


def get_score(user_id):
    return db.get_score(user_id)


def get_top_players(limit=3):
    return db.get_top_players(limit)


def get_user_position(user_id):
    return db.get_user_position(user_id)


def get_full_rating():
    return db.get_full_rating()


def get_user_requests_today(user_id):
    return db.get_user_requests_today(user_id)


def increment_correct(name):
    db.increment_correct(name)


def increment_wrong(name):
    db.increment_wrong(name)


def get_stats(name):
    return db.get_stats(name)


def get_top_strategies(limit=4):
    return db.get_top_strategies(limit)


# Дополнительные утилиты
def make_seminarist(user_id):
    """Назначает пользователя семинаристом"""
    with db.get_session() as session:
        user = session.get(User, user_id)
        if user:
            user.user_type = UserType.SEMINARIAN
            return True
        return False


def make_admin(user_id):
    """Назначает пользователя администратором"""
    with db.get_session() as session:
        user = session.get(User, user_id)
        if user:
            user.user_type = UserType.ADMIN
            return True
        return False


def reset_to_student(user_id):
    """Сбрасывает пользователя до студента"""
    with db.get_session() as session:
        user = session.get(User, user_id)
        if user:
            user.user_type = UserType.STUDENT
            return True
        return False


def create_group(name, max_students=25):
    return db.create_group(name, max_students)


def set_user_group(user_id, group_id, changed_by_id=None):
    return db.set_user_group(user_id, group_id, changed_by_id)


def set_transfer_deadline(group_id, deadline, changed_by_id):
    return db.set_transfer_deadline(group_id, deadline, changed_by_id)


def get_available_groups_for_student(user_id):
    return db.get_available_groups_for_student(user_id)


# Устанавливаем связи между моделями после их создания
def setup_relationships():
    """Настраивает связи между моделями"""
    # Импортируем модели локально
    from .users import User
    from .logs import ScoreChangeLog, OperationLog
    from .groups import Group

    # Настраиваем связи User
    User.score_changes_made = relationship(
        "ScoreChangeLog",
        foreign_keys=[ScoreChangeLog.changed_by_id],
        back_populates="changed_by",
        cascade="all, delete-orphan"
    )

    User.score_changes_received = relationship(
        "ScoreChangeLog",
        foreign_keys=[ScoreChangeLog.user_id],
        back_populates="user",
        cascade="all, delete-orphan"
    )

    User.group = relationship("Group", back_populates="students")

    # Настраиваем связи ScoreChangeLog
    ScoreChangeLog.user = relationship(
        "User",
        foreign_keys=[ScoreChangeLog.user_id],
        back_populates="score_changes_received"
    )
    ScoreChangeLog.changed_by = relationship(
        "User",
        foreign_keys=[ScoreChangeLog.changed_by_id],
        back_populates="score_changes_made"
    )

    # Настраиваем связи OperationLog
    OperationLog.user = relationship("User", backref="operations")

    # Настраиваем связи Group
    Group.students = relationship("User", back_populates="group")

    # Применяем изменения
    configure_mappers()


# Вызываем функцию настройки связей
setup_relationships()


# Функции для работы с рейтингом (для обратной совместимости)
def get_group_rating(group_id: int) -> List[Dict]:
    """Получает рейтинг группы"""
    return db.get_group_rating(group_id)


def get_overall_rating() -> List[Dict]:
    """Получает общий рейтинг"""
    return db.get_overall_rating()


def get_user_rating_position(user_id: int, by_group: bool = False) -> Optional[Dict]:
    """Получает позицию пользователя в рейтинге"""
    return db.get_user_rating_position(user_id, by_group)


def get_top_students_by_group(group_id: int, limit: int = 10) -> List[Dict]:
    """Получает топ студентов в группе"""
    return db.get_top_students_by_group(group_id, limit)


def get_top_students_overall(limit: int = 10) -> List[Dict]:
    """Получает топ студентов по всем группам"""
    return db.get_top_students_overall(limit)


def get_rating_statistics(group_id: Optional[int] = None) -> Dict:
    """Получает статистику по рейтингу"""
    return db.get_rating_statistics(group_id)


def calculate_all_seminar_grades():
    """
    Рассчитывает оценки за семинары для всех студентов.
    Вызывается после завершения всех семинаров.
    
    Использует нормальное распределение:
    - Студенты с баллами <= -15 получают оценку 0
    - Для остальных: Norm.dist(x; µ; σ; true) * 10
    где µ и σ рассчитываются по всем студентам с баллами > -15
    """
    db.recalculate_all_ratings()