from datetime import datetime
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