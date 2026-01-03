# bot.py - ФИНАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ С ВСЕМИ ФУНКЦИЯМИ
import os
import asyncio
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from urllib.parse import urlencode

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv()


# ==================== CORS MIDDLEWARE ====================
@web.middleware
async def cors_middleware(request, handler):
    response = await handler(request)
    response.headers.update({
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PUT, DELETE",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, *",
        "Access-Control-Allow-Credentials": "true"
    })

    # Обработка preflight запросов
    if request.method == "OPTIONS":
        return response

    return response


# Создаём приложение с CORS
app = web.Application(middlewares=[cors_middleware])

# ==================== БОТ ====================
bot = Bot(
    token=os.getenv("TELEGRAM_API_KEY"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


# ==================== TELEGRAM BOT HANDLERS ====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    """Главное меню с веб-приложением"""
    try:
        user = message.from_user
        user_id = user.id

        # Пробуем получить или создать пользователя в БД
        is_admin = False
        try:
            from models.database_manager import db
            db_user = db.get_or_create_user(user_id, user.first_name or user.username)
            print(f"✅ Пользователь {user_id} зарегистрирован в БД")

            # Проверяем, является ли пользователь админом
            is_admin = db_user.user_type.value == "admin" if db_user else False
        except ImportError as e:
            print(f"⚠️ Модуль БД не найден: {e}")
        except Exception as e:
            print(f"⚠️ Ошибка БД: {e}")

        # URL для веб-приложения
        web_app_url = os.getenv("WEB_APP_URL", "https://moexbot.uk")

        # Формируем параметры для сессии
        query_params = urlencode({
            "user_id": user_id,
            "username": user.first_name or user.username,
            "is_admin": "true" if is_admin else "false"
        })
        full_url = f"{web_app_url}/?{query_params}"

        # Клавиатура с кнопкой веб-приложения
        keyboard_buttons = [
            [
                KeyboardButton(
                    text="🌐 Открыть веб-приложение",
                    web_app=WebAppInfo(url=full_url)
                )
            ],
            [
                KeyboardButton(text="📊 Рейтинг"),
                KeyboardButton(text="👤 Профиль")
            ]
        ]

        # Добавляем кнопку админ-панели только для админов
        if is_admin:
            keyboard_buttons.append([
                KeyboardButton(text="👑 Админ-панель")
            ])

        kb = ReplyKeyboardMarkup(
            keyboard=keyboard_buttons,
            resize_keyboard=True
        )

        welcome_text = f"""🎓 Привет, {user.first_name or user.username}!

Добро пожаловать в образовательную платформу!

📌 <b>Нажмите на кнопку ниже, чтобы открыть веб-приложение:</b>
• 📚 Просмотр и загрузка лекций
• 🎯 Прохождение семинаров
• 📊 Рейтинг и статистика

{'👑 <b>Вы имеете права администратора!</b>' if is_admin else ''}

💡 Веб-приложение откроется прямо в Telegram!
"""

        await message.answer(welcome_text, reply_markup=kb)
        print(f"✅ /start отправлен пользователю {user_id}, админ: {is_admin}")

    except Exception as e:
        print(f"❌ Ошибка в start_cmd: {e}")
        await message.answer("Привет! Используйте кнопки меню.")


@dp.message(lambda message: message.text == "👑 Админ-панель")
async def admin_panel_button(message: types.Message):
    """Открытие админ-панели"""
    try:
        user = message.from_user
        user_id = user.id

        # Проверяем права админа
        try:
            from models.database_manager import db
            db_user = db.get_user(user_id)
            is_admin = db_user and db_user.user_type.value == "admin" if db_user else False

            if not is_admin:
                await message.answer("❌ У вас нет прав для доступа к админ-панели!")
                return

        except ImportError as e:
            print(f"⚠️ Модуль БД не найден: {e}")
            await message.answer("❌ Ошибка проверки прав доступа!")
            return
        except Exception as e:
            print(f"⚠️ Ошибка проверки прав админа: {e}")
            await message.answer("❌ Ошибка проверки прав доступа!")
            return

        # URL для админ-панели
        web_app_url = os.getenv("WEB_APP_URL", "https://moexbot.uk")
        admin_url = f"{web_app_url}/?user_id={user_id}&username={user.first_name or user.username}&admin=true"

        # Создаем инлайн-кнопку для админ-панели
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👑 Открыть админ-панель",
                        web_app=WebAppInfo(url=admin_url)
                    )
                ]
            ]
        )

        await message.answer(
            "👑 <b>Админ-панель управления</b>\n\n"
            "Нажмите кнопку ниже, чтобы открыть панель администратора:",
            reply_markup=kb
        )

    except Exception as e:
        print(f"❌ Ошибка в admin_panel_button: {e}")
        await message.answer("Ошибка при открытии админ-панели.")


@dp.message(lambda message: message.text == "🌐 Открыть веб-приложение")
async def open_web_app_button(message: types.Message):
    """Обработка нажатия на кнопку веб-приложения (fallback)"""
    try:
        user = message.from_user
        web_app_url = os.getenv("WEB_APP_URL", "https://moexbot.uk")
        web_app_full_url = f"{web_app_url}/?user_id={user.id}&username={user.first_name or user.username}&is_telegram=true"

        help_text = f"""🌐 <b>Открытие веб-приложения</b>

Нажмите на кнопку ниже, чтобы открыть веб-приложение:"""

        await message.answer(help_text, disable_web_page_preview=True)

        # Отправляем кнопку
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(
                    text="🌐 Открыть веб-приложение",
                    web_app=WebAppInfo(url=web_app_full_url)
                )]
            ],
            resize_keyboard=True
        )
        await message.answer("Нажмите здесь:", reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка открытия веб-приложения: {e}")
        await message.answer("Ошибка при открытии веб-приложения.")


@dp.message(lambda message: message.text == "📊 Рейтинг")
async def show_rating(message: types.Message):
    """Показать рейтинг"""
    try:
        user_id = message.from_user.id

        try:
            from models.database_manager import db

            # Получаем топ-5
            top_players = db.get_top_players(5)

            if top_players:
                response = "🏆 Топ-5 студентов:\n\n"
                for i, player in enumerate(top_players, 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    response += f"{medal} {player['username']} - {player['score']} баллов\n"

                # Получаем позицию пользователя
                try:
                    user_position, user_score = db.get_user_position(user_id)
                    response += f"\n📊 Ваша позиция: {user_position}\n"
                    response += f"🎯 Ваши баллы: {user_score}"
                except:
                    response += "\n📊 Ваша позиция: информация недоступна"

                await message.answer(response)
            else:
                await message.answer("📊 Рейтинг пока пуст. Будьте первым!")

        except ImportError:
            # Заглушка если БД не доступна
            await message.answer("📊 Рейтинг временно недоступен. Откройте веб-приложение для просмотра.")
        except Exception as e:
            print(f"⚠️ Ошибка получения рейтинга: {e}")
            await message.answer("📊 Рейтинг временно недоступен. Попробуйте позже.")

    except Exception as e:
        print(f"❌ Ошибка показа рейтинга: {e}")
        await message.answer("Ошибка при получении рейтинга.")


@dp.message(lambda message: message.text == "👤 Профиль")
async def show_profile(message: types.Message):
    """Показать профиль пользователя"""
    try:
        user = message.from_user

        try:
            from models.database_manager import db
            from models import Group

            db_user = db.get_user(user.id)
            if db_user:
                # Получаем группу
                group_name = "Без группы"
                if db_user.group_id:
                    with db.get_session() as session:
                        group = session.query(Group).filter(Group.id == db_user.group_id).first()
                        if group:
                            group_name = group.name

                # Получаем позицию
                try:
                    user_position, user_score = db.get_user_position(user.id)
                    position_text = f"📈 Ваша позиция в рейтинге: {user_position}"
                    score_text = f"🎯 Ваши баллы: {user_score}"
                except:
                    position_text = "📈 Ваша позиция в рейтинге: информация недоступна"
                    score_text = f"🎯 Ваши баллы: {db_user.score}"

                response = f"""👤 Ваш профиль:

📛 Имя: {db_user.username}
👥 Текущая группа: {group_name}
⭐ Оценка за семинары: {db_user.seminar_grade or 'еще не рассчитана'}

{score_text}
{position_text}"""
                await message.answer(response)
            else:
                await message.answer("👤 Профиль не найден. Откройте веб-приложение для регистрации.")

        except ImportError:
            # Информация из Telegram если БД недоступна
            response = f"""👤 Ваш профиль (базовая информация):

📛 Имя: {user.first_name or user.username}
🆔 ID: {user.id}

📊 Для полного профиля откройте веб-приложение."""
            await message.answer(response)
        except Exception as e:
            print(f"⚠️ Ошибка получения профиля: {e}")
            await message.answer("👤 Профиль временно недоступен. Откройте веб-приложение.")

    except Exception as e:
        print(f"❌ Ошибка показа профиля: {e}")
        await message.answer("Ошибка при получении профиля.")


@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    """Справка"""
    web_app_url = os.getenv("WEB_APP_URL", "https://moexbot.uk")

    help_text = f"""📚 <b>Помощь по боту:</b>

<b>Основные команды:</b>
/start - Главное меню
/help - Эта справка
/webapp - Быстрый доступ к веб-приложению

<b>Основные кнопки:</b>
🌐 <b>Открыть веб-приложение</b> - веб-приложение прямо в Telegram
📊 Рейтинг - таблица лидеров
👤 Профиль - ваша статистика
👑 Админ-панель - панель управления (для администраторов)

<b>Как пользоваться веб-приложением:</b>
1. Нажмите "🌐 Открыть веб-приложение" в меню
2. Веб-приложение загрузится прямо в Telegram
3. Войдите автоматически через Telegram

<b>Если веб-приложение не открывается:</b>
• Обновите Telegram до последней версии
• Используйте мобильное приложение Telegram
• Перейдите по ссылке: {web_app_url}

<b>Поддержка:</b> @ajlhimik
"""
    await message.answer(help_text, disable_web_page_preview=True)


@dp.message(Command("webapp"))
async def webapp_cmd(message: types.Message):
    """Быстрый доступ к веб-приложению"""
    try:
        user = message.from_user
        web_app_url = os.getenv("WEB_APP_URL", "https://moexbot.uk")
        web_app_full_url = f"{web_app_url}/?user_id={user.id}&username={user.first_name or user.username}&is_telegram=true"

        # Создаем инлайн-кнопку для веб-приложения
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="🌐 Открыть веб-приложение прямо сейчас",
                    web_app=WebAppInfo(url=web_app_full_url)
                )]
            ]
        )

        await message.answer(
            "Нажмите кнопку ниже, чтобы открыть веб-приложение:",
            reply_markup=kb
        )

    except Exception as e:
        print(f"❌ Ошибка в webapp_cmd: {e}")
        await message.answer("Ошибка при открытии веб-приложения.")


# ==================== ВЕБ-СЕРВЕР И API ====================

async def api_health(request):
    """Проверка работоспособности API"""
    return web.json_response({
        'status': 'ok',
        'service': 'education-platform',
        'version': '2.0.0',
        'timestamp': asyncio.get_event_loop().time()
    })


async def init_session(request):
    """Инициализация сессии из Telegram"""
    try:
        user_id = request.query.get('user_id')
        username = request.query.get('username')

        if user_id and username:
            # Пробуем зарегистрировать пользователя
            try:
                from models.database_manager import db
                db.get_or_create_user(int(user_id), username)
                print(f"✅ Сессия инициализирована для {username} ({user_id})")
            except ImportError:
                print("⚠️ Модуль БД не найден при инициализации сессии")
            except Exception as e:
                print(f"⚠️ Ошибка БД при инициализации: {e}")

        # Редирект на главную страницу с параметрами
        redirect_url = '/'
        if user_id:
            redirect_url = f'/?user_id={user_id}&username={username}'
        return web.HTTPFound(redirect_url)

    except Exception as e:
        print(f"❌ Ошибка в init_session: {e}")
        return web.HTTPFound('/')


async def api_rating(request):
    """API для получения рейтинга"""
    try:
        rating_type = request.query.get('type', 'overall')

        try:
            from models.database_manager import db

            if rating_type == 'overall':
                # Общий рейтинг
                rating = db.get_overall_rating()
            else:
                # Групповой рейтинг
                group_id = request.query.get('group_id')
                if group_id:
                    rating = db.get_group_rating(int(group_id))
                else:
                    rating = []

            return web.json_response({
                'success': True,
                'rating': rating,
                'type': rating_type
            })

        except ImportError:
            return web.json_response({
                'success': False,
                'error': 'Database module not available'
            })
        except Exception as e:
            print(f"❌ Ошибка получения рейтинга: {e}")
            return web.json_response({
                'success': False,
                'error': str(e)
            })

    except Exception as e:
        print(f"❌ Ошибка в api_rating: {e}")
        return web.json_response({
            'success': False,
            'error': 'Server error'
        })


async def api_check_admin(request):
    """Проверка, является ли пользователь админом"""
    try:
        user_id = request.query.get('user_id')

        if not user_id:
            return web.json_response({'is_admin': False, 'error': 'No user_id provided'})

        try:
            from models.database_manager import db
            db_user = db.get_user(int(user_id))

            is_admin = False
            if db_user and hasattr(db_user, 'user_type'):
                is_admin = db_user.user_type.value == "admin"

            return web.json_response({
                'is_admin': is_admin,
                'user_id': user_id,
                'username': db_user.username if db_user else None
            })

        except ImportError:
            return web.json_response({'is_admin': False, 'error': 'DB module not found'})
        except Exception as e:
            print(f"❌ Ошибка в api_check_admin: {e}")
            return web.json_response({'is_admin': False, 'error': str(e)})

    except Exception as e:
        print(f"❌ Ошибка в api_check_admin: {e}")
        return web.json_response({'is_admin': False, 'error': 'Server error'})


async def index_handler(request):
    """Главная страница - просто отдаём файл"""
    html_dir = os.path.join(BASE_DIR, 'html_dir')
    index_file = os.path.join(html_dir, 'index.html')

    if os.path.exists(index_file):
        return web.FileResponse(index_file)
    else:
        # Если файла нет - ошибка 404
        return web.Response(text='File index.html not found', status=404)

async def api_debug_user(request):
    """Отладка: проверка пользователя в БД"""
    try:
        user_id = request.query.get('user_id')
        if not user_id:
            return web.json_response({'error': 'No user_id'})

        from models.database_manager import db

        with db.get_session() as session:
            from models.users import User, UserType
            user = session.query(User).filter(User.id == int(user_id)).first()

            if user:
                return web.json_response({
                    'user_id': user.id,
                    'username': user.username,
                    'user_type': user.user_type.value if user.user_type else None,
                    'user_type_raw': str(user.user_type),
                    'score': user.score,
                    'group_id': user.group_id,
                    'all_types': [t.value for t in UserType]
                })
            else:
                return web.json_response({'error': 'User not found'})

    except Exception as e:
        return web.json_response({'error': str(e)})


async def api_admin_stats(request):
    """API для получения статистики платформы (только для админов)"""
    try:
        user_id = request.query.get('user_id')

        if not user_id:
            return web.json_response({'error': 'No user_id'})

        # Проверяем права админа
        try:
            from models.database_manager import db
            db_user = db.get_user(int(user_id))
            is_admin = db_user and db_user.user_type.value == "admin" if db_user else False

            if not is_admin:
                return web.json_response({'error': 'Access denied'}, status=403)

        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

        # Получаем статистику
        try:
            with db.get_session() as session:
                from models.users import User, UserType
                from models.groups import Group
                from models.questions import Question

                total_users = session.query(User).count()
                total_students = session.query(User).filter(User.user_type == UserType.STUDENT).count()
                total_groups = session.query(Group).count()
                total_questions = session.query(Question).filter(Question.is_active == True).count()

                return web.json_response({
                    'total_users': total_users,
                    'total_students': total_students,
                    'total_groups': total_groups,
                    'total_questions': total_questions,
                    'active_seminars': 20,  # Фиксированное значение
                    'timestamp': asyncio.get_event_loop().time()
                })

        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    except Exception as e:
        print(f"❌ Ошибка в api_admin_stats: {e}")
        return web.json_response({'error': 'Server error'}, status=500)


# Добавляем роуты
app.router.add_get('/api/debug_user', api_debug_user)
app.router.add_get('/api/admin/stats', api_admin_stats)

# ==================== ROUTES SETUP ====================
app.router.add_get('/', index_handler)
app.router.add_get('/api/health', api_health)
app.router.add_get('/api/init_session', init_session)
app.router.add_get('/api/rating', api_rating)  # Новый endpoint
app.router.add_get('/api/check_admin', api_check_admin)  # Новый endpoint

# Статические файлы
html_dir = os.path.join(BASE_DIR, 'html_dir')
if os.path.exists(html_dir):
    app.router.add_static('/static', html_dir)
    print(f"✅ Статика подключена из {html_dir}")


# ==================== STARTUP ====================
async def on_startup(app):
    """Запуск при старте приложения"""
    print("=" * 60)
    print("🚀 ЗАПУСК ОБРАЗОВАТЕЛЬНОЙ ПЛАТФОРМЫ")
    print("=" * 60)

    try:
        # Проверяем наличие html_dir
        html_dir_path = os.path.join(BASE_DIR, 'html_dir')
        if not os.path.exists(html_dir_path):
            os.makedirs(html_dir_path)
            print(f"📁 Создана директория: {html_dir_path}")

        index_file = os.path.join(html_dir_path, 'index.html')
        if not os.path.exists(index_file):
            print(f"⚠️  Внимание: index.html не найден в {html_dir_path}")
            print("   Создайте файл index.html или запустите create_html.py")

        # Инициализация админов из .env
        print("\n🔧 Инициализация админов...")
        admin_ids_str = os.getenv("ADMIN_IDS", "")

        if admin_ids_str:
            admin_ids = []
            for id_str in admin_ids_str.split(","):
                id_str = id_str.strip()
                if id_str:
                    try:
                        admin_ids.append(int(id_str))
                    except ValueError:
                        print(f"   ⚠️ Неверный ID в ADMIN_IDS: '{id_str}'")

            print(f"📋 ID админов из .env: {admin_ids}")

            if admin_ids:
                try:
                    from models.database_manager import db
                    from models.users import User, UserType

                    updated_count = 0
                    with db.get_session() as session:
                        # Создаем фейковых пользователей-админов если их нет
                        for admin_id in admin_ids:
                            try:
                                user = session.get(User, admin_id)
                                if user:
                                    # Если пользователь существует - обновляем до админа
                                    if user.user_type != UserType.ADMIN:
                                        user.user_type = UserType.ADMIN
                                        updated_count += 1
                                        print(f"   ✅ Пользователь {admin_id} назначен админом")
                                    else:
                                        print(f"   ℹ️  Пользователь {admin_id} уже админ")
                                else:
                                    # Создаем фейкового пользователя-админа
                                    fake_user = User(
                                        id=admin_id,
                                        username=f"admin_{admin_id}",
                                        user_type=UserType.ADMIN,
                                        score=0,
                                        requests_today=0,
                                        last_request_date=None
                                    )
                                    session.add(fake_user)
                                    print(f"   📝 Создан предзагруженный админ {admin_id}")
                                    updated_count += 1
                            except Exception as e:
                                print(f"   ❌ Ошибка обработки админа {admin_id}: {e}")

                        session.commit()

                    print(f"   📊 Итого: {updated_count} админов инициализировано")

                except ImportError as e:
                    print(f"⚠️ Ошибка импорта модулей БД: {e}")
                except Exception as e:
                    print(f"⚠️ Общая ошибка инициализации админов: {e}")
        else:
            print("⚠️ ADMIN_IDS не указаны в .env файле")

        # Запускаем бота
        await bot.delete_webhook(drop_pending_updates=True)
        asyncio.create_task(dp.start_polling(bot, skip_updates=True))
        print("✅ Telegram бот запущен")

        web_app_url = os.getenv("WEB_APP_URL", "https://moexbot.uk")
        print(f"🌐 Веб-приложение доступно по адресу: {web_app_url}")

    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()


app.on_startup.append(on_startup)


# ==================== MAIN ====================
async def main():
    """Главная функция запуска"""
    if not os.getenv("TELEGRAM_API_KEY"):
        print("❌ Ошибка: TELEGRAM_API_KEY не найден в .env файле!")
        print("   Создайте .env файл с переменными окружения")
        return

    # Запускаем веб-сервер
    runner = web.AppRunner(app)
    await runner.setup()

    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8000))

    site = web.TCPSite(runner, host, port)
    await site.start()

    print(f"\n🌐 Веб-сервер запущен на http://{host}:{port}")
    print(f"🌐 Внешний URL: {os.getenv('WEB_APP_URL', 'https://moexbot.uk')}")
    print("🤖 Telegram бот активен")
    print("📱 Используйте /start в Telegram для открытия веб-приложения")
    print("=" * 60)

    # Ожидаем завершения
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n👋 Завершение работы")
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Приложение завершено пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()