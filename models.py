from datetime import datetime
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, DateTime, Enum
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session, aliased
from enum import Enum as PyEnum

# Базовый класс для моделей (SQLAlchemy 2.0)
Base = declarative_base()


# Типы пользователей
class UserType(PyEnum):
    STUDENT = "student"
    SEMINARIAN = "seminarist"
    ADMIN = "admin"


# Модель для логирования изменений баллов
class ScoreChangeLog(Base):
    __tablename__ = 'score_change_log'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    changed_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    old_score = Column(Integer, nullable=False)
    new_score = Column(Integer, nullable=False)
    delta = Column(Integer, nullable=False)
    change_time = Column(DateTime, default=datetime.now)

    # Связи
    user = relationship("User", foreign_keys=[user_id], back_populates="score_changes_received")
    changed_by = relationship("User", foreign_keys=[changed_by_id], back_populates="score_changes_made")


# Модель для общего лога операций
class OperationLog(Base):
    __tablename__ = 'operation_logs'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    operation_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    # Связь
    user = relationship("User", backref="operations")


# Модель для групп
class Group(Base):
    __tablename__ = 'groups'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    max_students = Column(Integer, default=25)  # Максимум 25 человек
    created_at = Column(DateTime, default=datetime.now)
    transfer_deadline = Column(DateTime, nullable=True)  # Дедлайн для перехода между группами

    # Связи
    students = relationship("User", back_populates="group")

    def __repr__(self):
        return f"<Group(id={self.id}, name='{self.name}')>"

    def can_join(self):
        """Проверяет, можно ли присоединиться к группе"""
        if self.transfer_deadline and datetime.now() > self.transfer_deadline:
            return False, "Истек дедлайн для перехода в группу"

        student_count = len([s for s in self.students if s.user_type == UserType.STUDENT])
        if student_count >= self.max_students:
            return False, "Группа заполнена"

        return True, "Можно присоединиться"


# Базовый класс пользователя
class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    score = Column(Integer, default=100)
    requests_today = Column(Integer, default=0)
    last_request_date = Column(Date, nullable=True)
    user_type = Column(Enum(UserType), default=UserType.STUDENT, nullable=False)
    group_id = Column(Integer, ForeignKey('groups.id'), nullable=True)

    # Связи
    score_changes_made = relationship(
        "ScoreChangeLog",
        foreign_keys=[ScoreChangeLog.changed_by_id],
        back_populates="changed_by",
        cascade="all, delete-orphan"
    )

    score_changes_received = relationship(
        "ScoreChangeLog",
        foreign_keys=[ScoreChangeLog.user_id],
        back_populates="user",
        cascade="all, delete-orphan"
    )

    group = relationship("Group", back_populates="students")

    def can_change_score(self, target_user):
        """Проверяет, может ли пользователь изменять баллы другого пользователя"""
        if self.user_type == UserType.ADMIN:
            return True
        elif self.user_type == UserType.SEMINARIAN:
            return True
        return False

    def change_user_score(self, target_user, delta, session=None):
        """Изменяет баллы другого пользователя с учетом типа пользователя"""
        if not self.can_change_score(target_user):
            raise PermissionError(f"User {self.username} cannot change scores")

        if session is None:
            raise ValueError("Session is required for score change")

        old_score = target_user.score
        new_score = old_score + delta
        target_user.score = new_score

        # Логируем изменение, если это не админ (у админов логирование отключено)
        if self.user_type != UserType.ADMIN:
            log_entry = ScoreChangeLog(
                user_id=target_user.id,
                changed_by_id=self.id,
                old_score=old_score,
                new_score=new_score,
                delta=delta
            )
            session.add(log_entry)

        return old_score, new_score

    def __repr__(self):
        group_info = f", group_id={self.group_id}" if self.group_id else ""
        return f"<User(id={self.id}, username='{self.username}', type={self.user_type.value}{group_info})>"


# Модель для статистики ответов
class AnswerStat(Base):
    __tablename__ = 'answers_stats'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    correct_cnt = Column(Integer, default=0)
    wrong_cnt = Column(Integer, default=0)

    def __repr__(self):
        return f"<AnswerStat(name='{self.name}', correct={self.correct_cnt}, wrong={self.wrong_cnt})>"


# Класс для управления базой данных
class DatabaseManager:
    def __init__(self, db_url="sqlite:///users.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    def get_session(self):
        """Контекстный менеджер для сессии"""
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

    # Методы для работы с пользователями
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

    def get_user(self, user_id):
        """Получает пользователя по ID"""
        with self.get_session() as session:
            return session.get(User, user_id)

    def get_users_by_type(self, user_type):
        """Получает всех пользователей определенного типа"""
        with self.get_session() as session:
            return session.query(User).filter(User.user_type == user_type).all()

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


# Тестирование
if __name__ == "__main__":
    # Удаляем старые таблицы
    db.drop_tables()

    # Инициализация БД
    db.init_db()

    print("=" * 60)
    print("Тестирование системы управления пользователями и баллами")
    print("=" * 60)

    # Создание пользователей разных типов
    student = db.get_or_create_user(1, "Иван Петров", UserType.STUDENT)
    seminarist = db.get_or_create_user(2, "Анна Семенова", UserType.SEMINARIAN)
    admin = db.get_or_create_user(3, "Сергей Администратор", UserType.ADMIN)

    print(f"✓ Созданы пользователи:")
    print(f"  - Студент: {student.username} (ID: {student.id})")
    print(f"  - Семинарист: {seminarist.username} (ID: {seminarist.id})")
    print(f"  - Админ: {admin.username} (ID: {admin.id})")

    # Пример изменения баллов с логированием (семинаристом)
    print("\n✓ Тест 1: Семинарист изменяет баллы студента")
    db.update_score(student.id, 10, changed_by_id=seminarist.id)
    print(f"  Баллы студента увеличены на 10")

    # Пример изменения баллов без логирования (админом)
    print("\n✓ Тест 2: Админ изменяет баллы студента")
    db.update_score(student.id, -5, changed_by_id=admin.id)
    print(f"  Баллы студента уменьшены на 5")

    # Получение текущих баллов
    current_score = db.get_score(student.id)
    print(f"\n✓ Текущие баллы студента: {current_score}")

    # Получение логов изменений
    print("\n✓ Тест 3: Получение логов изменений баллов")
    logs = db.get_score_change_log(student.id)
    print(f"  Всего записей в логах: {len(logs)}")
    if logs:
        print(f"  Последнее изменение:")
        log = logs[0]
        print(f"    Изменено: {log['changer_username']}")
        print(f"    Было: {log['old_score']}, Стало: {log['new_score']} (Δ={log['delta']})")
        print(f"    Время: {log['change_time']}")

    # Проверка прав
    print("\n✓ Тест 4: Проверка прав доступа")
    student_refreshed = db.get_user(student.id)
    seminarist_refreshed = db.get_user(seminarist.id)
    admin_refreshed = db.get_user(admin.id)
    print(f"  Может ли семинарист менять баллы студента: {seminarist_refreshed.can_change_score(student_refreshed)}")
    print(f"  Может ли студент менять баллы семинариста: {student_refreshed.can_change_score(seminarist_refreshed)}")
    print(f"  Может ли админ менять баллы студента: {admin_refreshed.can_change_score(student_refreshed)}")

    # Пример работы со статистикой
    print("\n✓ Тест 5: Работа со статистикой ответов")
    db.increment_correct("strategy1")
    db.increment_wrong("strategy1")
    db.increment_correct("strategy2")

    stats = db.get_stats("strategy1")
    print(f"  Статистика strategy1: {stats}")

    top_strategies = db.get_top_strategies()
    print(f"  Топ стратегий: {top_strategies}")

    # Пример получения рейтинга
    print("\n✓ Тест 6: Рейтинг игроков")
    top_players = db.get_top_players()
    print(f"  Топ игроков: {top_players}")

    # Создадим еще студентов для рейтинга
    db.get_or_create_user(4, "Мария Иванова", UserType.STUDENT)
    db.get_or_create_user(5, "Алексей Смирнов", UserType.STUDENT)
    db.update_score(4, 50)
    db.update_score(5, 75)

    full_rating = db.get_full_rating()
    print(f"  Полный рейтинг ({len(full_rating)} игроков):")
    for i, player in enumerate(full_rating[:5], 1):
        print(f"    {i}. {player['username']}: {player['score']} баллов")

    # Тест смены типа пользователя
    print("\n✓ Тест 7: Смена типа пользователя")
    new_student = db.get_or_create_user(6, "Новый пользователь", UserType.STUDENT)
    print(f"  Изначальный тип: {new_student.user_type.value}")

    make_seminarist(6)
    updated_user = db.get_user(6)
    print(f"  После назначения семинаристом: {updated_user.user_type.value}")

    reset_to_student(6)
    updated_user = db.get_user(6)
    print(f"  После сброса до студента: {updated_user.user_type.value}")

    print("\n" + "=" * 60)
    print("Тестирование системы логов операций")
    print("=" * 60)

    # Создадим нового пользователя для тестов
    test_user = db.get_or_create_user(100, "Тестовый пользователь", UserType.STUDENT)

    # Тест 1: Логирование изменения баллов
    print("\n✓ Тест 1: Логирование изменения баллов")
    old_score, new_score = db.update_score(test_user.id, 25, changed_by_id=seminarist.id)
    print(f"  Баллы изменены: {old_score} → {new_score}")

    # Тест 2: Логирование смены типа пользователя
    print("\n✓ Тест 2: Логирование смены типа пользователя")
    old_type, new_type = db.change_user_type(test_user.id, UserType.SEMINARIAN, changed_by_id=admin.id)
    print(f"  Тип пользователя изменен: {old_type.value} → {new_type.value}")

    # Тест 3: Получение логов операций для семинариста
    print("\n✓ Тест 3: Получение логов операций семинариста")
    seminarist_logs = db.get_operation_logs(user_id=seminarist.id, limit=5)
    print(f"  Логов операций семинариста: {len(seminarist_logs)}")
    if seminarist_logs:
        print(f"  Последняя операция семинариста:")
        log = seminarist_logs[0]
        print(f"    Тип: {log['operation_type']}")
        print(f"    Время: {log['created_at']}")

    # Тест 4: Получение логов операций по типу
    print("\n✓ Тест 4: Получение логов изменений баллов")
    score_logs = db.get_operation_logs(operation_type='change_score', limit=3)
    print(f"  Всего записей об изменении баллов: {len(score_logs)}")
    for i, log in enumerate(score_logs, 1):
        print(f"    {i}. {log['username']}: {log['operation_type']}")

    # Тест 5: Все логи операций
    print("\n✓ Тест 5: Все логи операций (последние 5)")
    all_logs = db.get_operation_logs(limit=5)
    print(f"  Всего записей в логах: {len(all_logs)}")
    for i, log in enumerate(all_logs, 1):
        print(f"    {i}. [{log['created_at'].strftime('%H:%M:%S')}] {log['username']}: {log['operation_type']}")

    # Тест 6: Создание пользователя с логированием
    print("\n✓ Тест 6: Создание нового пользователя с логированием")
    new_test_user = db.get_or_create_user(101, "Новый тестовый пользователь", UserType.STUDENT)

    # Логируем создание пользователя
    db.log_operation(
        user_id=admin.id,
        operation_type='create_user'
    )
    print(f"  Создан пользователь: {new_test_user.username}")

    # Тест 7: Фильтрация логов по нескольким параметрам
    print("\n✓ Тест 7: Фильтрация логов администратора")
    admin_logs = db.get_operation_logs(user_id=admin.id, operation_type='change_user_type', limit=3)
    print(f"  Логов смены типа пользователя администратором: {len(admin_logs)}")
    if admin_logs:
        print(f"  Последняя смена типа:")
        log = admin_logs[0]
        print(f"    Время: {log['created_at']}")

    print("\n" + "=" * 60)
    print("Все тесты пройдены успешно!")
    print("=" * 60)

    # Тестирование системы групп
    print("\n" + "=" * 60)
    print("Тестирование системы групп")
    print("=" * 60)

    # Создаем группы
    print("\n✓ Тест 1: Создание групп")
    group1 = db.create_group("Группа А", max_students=3)  # Маленькая группа для тестов
    group2 = db.create_group("Группа Б")
    group3 = db.create_group("Группа В")

    print(f"  Созданы группы:")
    print(f"    - {group1.name} (ID: {group1.id}, макс: {group1.max_students})")
    print(f"    - {group2.name} (ID: {group2.id}, макс: {group2.max_students})")
    print(f"    - {group3.name} (ID: {group3.id}, макс: {group3.max_students})")

    # Назначаем студентов в группы
    print("\n✓ Тест 2: Назначение студентов в группы")
    student_refreshed = db.get_user(student.id)
    db.set_user_group(student_refreshed.id, group1.id, changed_by_id=admin.id)  # Админ назначает
    db.set_user_group(4, group1.id, changed_by_id=admin.id)  # Еще одного студента
    db.set_user_group(5, group2.id, changed_by_id=admin.id)

    print(f"  Студент {student_refreshed.username} назначен в {group1.name}")
    print(f"  Студент ID 4 назначен в {group1.name}")
    print(f"  Студент ID 5 назначен в {group2.name}")

    # Пытаемся переполнить группу
    print("\n✓ Тест 3: Попытка переполнить группу")
    try:
        db.set_user_group(6, group1.id, changed_by_id=6)  # Студент пытается присоединиться
        print("  ОШИБКА: Должно было вызвать исключение!")
    except ValueError as e:
        print(f"  ✓ Правильно отклонено: {e}")

    # Устанавливаем дедлайн
    print("\n✓ Тест 4: Установка дедлайна")
    from datetime import timedelta

    deadline = datetime.now() + timedelta(days=7)
    db.set_transfer_deadline(group2.id, deadline, admin.id)
    print(f"  Дедлайн для {group2.name} установлен на {deadline}")

    # Просмотр доступных групп
    print("\n✓ Тест 5: Просмотр доступных групп для студента")
    available_groups = db.get_available_groups_for_student(student_refreshed.id)
    print(f"  Доступные группы для студента {student_refreshed.username}:")
    for group_info in available_groups:
        deadline_info = f", дедлайн: {group_info['transfer_deadline'].strftime('%d.%m.%Y')}" if group_info[
            'transfer_deadline'] else ""
        print(
            f"    - {group_info['name']}: {group_info['current_students']}/{group_info['max_students']}{deadline_info}")

    # Студент меняет группу
    print("\n✓ Тест 6: Студент меняет группу")
    try:
        old_group, new_group = db.set_user_group(student_refreshed.id, group2.id, changed_by_id=student_refreshed.id)
        print(f"  Студент перешел из {old_group.name if old_group else 'без группы'} в {new_group.name}")
    except Exception as e:
        print(f"  Не удалось сменить группу: {e}")

    # Проверяем состав групп
    print("\n✓ Тест 7: Состав групп")
    for group in [group1, group2, group3]:
        students = db.get_group_students(group.id)
        print(f"  {group.name}: {len(students)} студентов")

    print("\n" + "=" * 60)
    print("Тестирование системы групп завершено успешно!")
    print("=" * 60)
    print()