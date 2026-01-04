# bot.py - ФИНАЛЬНАЯ РАБОЧАЯ ВЕРСИЯ
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
import uuid

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
    """Главная страница"""
    html_dir = os.path.join(BASE_DIR, 'html_dir')
    index_file = os.path.join(html_dir, 'index.html')

    if os.path.exists(index_file):
        # Читаем содержимое файла
        with open(index_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Добавляем проверку админских прав через JavaScript
        script_to_inject = """
        <script>
        // Проверяем админские права при загрузке страницы
        async function checkAdminOnLoad() {
            const urlParams = new URLSearchParams(window.location.search);
            const userId = urlParams.get('user_id');

            if (userId) {
                try {
                    const response = await fetch(`/api/check_admin?user_id=${userId}`);
                    const data = await response.json();

                    if (data.is_admin) {
                        console.log('✅ Пользователь является админом');
                        // Устанавливаем флаг админа в localStorage
                        localStorage.setItem('is_admin', 'true');
                        localStorage.setItem('admin_user_id', userId);

                        // Показываем админ-панель
                        const adminBtn = document.getElementById('admin-panel-btn');
                        if (adminBtn) {
                            adminBtn.style.display = 'flex';
                        }

                        // Показываем админ-секцию если она скрыта
                        const adminSection = document.getElementById('admin-section');
                        if (adminSection) {
                            adminSection.style.display = 'block';
                        }
                    } else {
                        localStorage.setItem('is_admin', 'false');
                    }
                } catch (error) {
                    console.log('Ошибка проверки прав админа:', error);
                }
            }
        }

        // Запускаем проверку при загрузке
        document.addEventListener('DOMContentLoaded', checkAdminOnLoad);
        </script>
        """

        # Вставляем скрипт перед закрывающим тегом </body>
        if '</body>' in content:
            content = content.replace('</body>', f'{script_to_inject}</body>')

        return web.Response(text=content, content_type='text/html')
    else:
        return web.Response(text='File index.html not found', status=404)


# ==================== ОБРАБОТЧИКИ ДЛЯ HTML ФАЙЛОВ ====================

async def admin_lectures_handler(request):
    """Обработчик для страницы добавления лекций"""
    try:
        html_dir = os.path.join(BASE_DIR, 'html_dir')
        file_path = os.path.join(html_dir, 'admin', 'lectures.html')

        if os.path.exists(file_path):
            # Читаем содержимое файла
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Добавляем JavaScript для проверки админских прав
            admin_check_script = """
            <script>
            // Проверяем админские права при загрузке страницы добавления лекций
            async function checkAdminForLecturePage() {
                const urlParams = new URLSearchParams(window.location.search);
                const userId = urlParams.get('user_id');
                const isAdminParam = urlParams.get('admin');

                if (userId) {
                    try {
                        const response = await fetch(`/api/check_admin?user_id=${userId}`);
                        const data = await response.json();

                        if (!data.is_admin && isAdminParam !== 'true') {
                            // Если не админ - показываем сообщение и редиректим
                            document.body.innerHTML = `
                                <div style="text-align: center; padding: 50px; color: white;">
                                    <h1 style="color: #e74c3c;">🔒 Доступ запрещен</h1>
                                    <p>Только администраторы могут добавлять лекции.</p>
                                    <a href="/" style="color: #3498db;">Вернуться на главную</a>
                                </div>
                            `;
                            return false;
                        }
                        return true;
                    } catch (error) {
                        console.log('Ошибка проверки прав админа:', error);
                        return false;
                    }
                }
                return false;
            }

            // Запускаем проверку при загрузке
            document.addEventListener('DOMContentLoaded', async () => {
                const isAdmin = await checkAdminForLecturePage();
                if (!isAdmin) {
                    return;
                }

                // Устанавливаем user_id из URL в форму
                const urlParams = new URLSearchParams(window.location.search);
                const userId = urlParams.get('user_id');
                if (userId) {
                    // Сохраняем в глобальную переменную
                    window.currentUserId = userId;
                }
            });
            </script>
            """

            # Вставляем скрипт перед закрывающим тегом </body>
            if '</body>' in content:
                content = content.replace('</body>', f'{admin_check_script}</body>')

            return web.Response(text=content, content_type='text/html')
        else:
            print(f"❌ Файл не найден: {file_path}")
            return web.Response(text='Страница добавления лекций не найдена', status=404)
    except Exception as e:
        print(f"❌ Ошибка загрузки страницы лекций: {e}")
        return web.Response(text='Ошибка сервера', status=500)


async def catch_all_handler(request):
    """Обработчик для всех остальных запросов"""
    try:
        html_dir = os.path.join(BASE_DIR, 'html_dir')
        path = request.path

        print(f"📥 Catch-all запрос: {path}")

        # Если это API - пропускаем
        if path.startswith('/api/'):
            return web.Response(text='Not found', status=404)

        # Если путь начинается с /static/ - обслуживаем как статику
        if path.startswith('/static/'):
            relative_path = path[7:]  # удаляем '/static'
            file_path = os.path.join(html_dir, relative_path.lstrip('/'))

            if os.path.exists(file_path) and os.path.isfile(file_path):
                return web.FileResponse(file_path)
            return web.Response(text='Static file not found', status=404)

        # Для HTML файлов
        if path == '/' or path == '':
            return await index_handler(request)
        elif path == '/admin/lectures.html':
            return await admin_lectures_handler(request)
        else:
            # Пробуем найти файл
            file_path = os.path.join(html_dir, path.lstrip('/'))

            # Проверяем расширение
            if not file_path.endswith('.html'):
                file_path += '.html'

            if os.path.exists(file_path) and os.path.isfile(file_path):
                return web.FileResponse(file_path)

            # Если файл не найден - показываем главную
            return await index_handler(request)

    except Exception as e:
        print(f"❌ Ошибка в catch_all_handler: {e}")
        return web.Response(text='Server error', status=500)


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
                    'active_seminars': 20,
                    'timestamp': asyncio.get_event_loop().time()
                })

        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)

    except Exception as e:
        print(f"❌ Ошибка в api_admin_stats: {e}")
        return web.json_response({'error': 'Server error'}, status=500)


# ==================== ЛЕКЦИИ API ====================

try:
    from models.lectures import Lecture, LectureView

    LECTURES_AVAILABLE = True
except ImportError:
    LECTURES_AVAILABLE = False
    print("⚠️ Модуль лекций не доступен")


async def api_create_lecture(request):
    """Создать новую лекцию (только ссылки на внешние видеохостинги)"""
    if not LECTURES_AVAILABLE:
        return web.json_response({'error': 'Lectures module not available'}, status=500)

    try:
        data = await request.post()
        user_id = data.get('user_id')

        if not user_id:
            return web.json_response({'error': 'No user_id provided'}, status=400)

        # Проверяем права админа
        from models.database_manager import db
        db_user = db.get_user(int(user_id))
        is_admin = db_user and db_user.user_type.value == "admin" if db_user else False

        if not is_admin:
            return web.json_response({'error': 'Access denied'}, status=403)

        # Создаем лекцию с внешними ссылками
        with db.get_session() as session:
            from datetime import datetime

            # Основные поля лекции
            lecture_data = {
                'title': data.get('title', '').strip(),
                'author': data.get('author', '').strip() or 'Автор не указан',
                'description': data.get('description', '').strip(),
                'is_public': data.get('is_public', 'true').lower() == 'true',
                'is_processed': False,
                'category': data.get('category', '').strip()
            }

            # Обрабатываем дату лекции
            lecture_date_str = data.get('lecture_date')
            if lecture_date_str:
                try:
                    lecture_data['lecture_date'] = datetime.fromisoformat(lecture_date_str)
                except:
                    lecture_data['lecture_date'] = datetime.utcnow()
            else:
                lecture_data['lecture_date'] = datetime.utcnow()

            # Добавляем номер лекции в заголовок
            lecture_number = data.get('lecture_number')
            if lecture_number and lecture_data['title']:
                lecture_data['title'] = f"Лекция {lecture_number}: {lecture_data['title']}"

            # Обрабатываем ссылку на видео
            video_url = data.get('video_url', '').strip()
            if video_url:
                lecture_data['external_video_url'] = video_url

                # Извлекаем YouTube ID если это YouTube ссылка
                if 'youtube.com' in video_url or 'youtu.be' in video_url:
                    import re
                    youtube_id = None
                    patterns = [
                        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
                        r'youtu\.be/([a-zA-Z0-9_-]+)',
                        r'youtube\.com/embed/([a-zA-Z0-9_-]+)',
                        r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]+)'
                    ]

                    for pattern in patterns:
                        match = re.search(pattern, video_url)
                        if match:
                            youtube_id = match.group(1)
                            break

                    if youtube_id:
                        lecture_data['youtube_video_id'] = youtube_id
                        print(f"✅ Извлечен YouTube ID: {youtube_id}")

            # Обрабатываем ссылку на слайды/материалы
            slides_url = data.get('slides_url', '').strip()
            if slides_url:
                lecture_data['external_slides_url'] = slides_url

            # Устанавливаем пустые значения для устаревших полей файлов
            # (чтобы не было ошибок с NOT NULL, если эти поля еще есть в модели)
            if hasattr(Lecture, 'file_name'):
                lecture_data['file_name'] = ''
            if hasattr(Lecture, 'file_path'):
                lecture_data['file_path'] = ''
            if hasattr(Lecture, 'file_size'):
                lecture_data['file_size'] = 0
            if hasattr(Lecture, 'file_type'):
                lecture_data['file_type'] = ''

            # ВАЖНО: Проверяем, что указана хотя бы одна ссылка на видео
            if not video_url:
                return web.json_response({
                    'error': 'Укажите ссылку на видео (YouTube, Vimeo и др.)'
                }, status=400)

            # Создаем объект лекции
            try:
                lecture = Lecture(**lecture_data)
                session.add(lecture)
                session.commit()

                print(f"✅ Лекция создана: {lecture.title} (ID: {lecture.id})")

                return web.json_response({
                    'success': True,
                    'lecture_id': lecture.id,
                    'message': 'Лекция успешно создана',
                    'lecture': {
                        'id': lecture.id,
                        'title': lecture.title,
                        'author': lecture.author,
                        'video_url': lecture.video_url if hasattr(lecture, 'video_url') else video_url,
                        'description': lecture.description[:100] + '...' if lecture.description and len(
                            lecture.description) > 100 else lecture.description
                    }
                })

            except Exception as e:
                session.rollback()
                print(f"❌ Ошибка при создании лекции в БД: {e}")
                return web.json_response({
                    'error': f'Ошибка при сохранении лекции: {str(e)}'
                }, status=500)

    except Exception as e:
        print(f"❌ Ошибка создания лекции: {e}")
        import traceback
        traceback.print_exc()
        return web.json_response({'error': str(e)}, status=500)

# ==================== ROUTES SETUP ====================

# 1. API маршруты (самые приоритетные)
app.router.add_get('/api/health', api_health)
app.router.add_get('/api/init_session', init_session)
app.router.add_get('/api/rating', api_rating)
app.router.add_get('/api/check_admin', api_check_admin)
app.router.add_get('/api/debug_user', api_debug_user)
app.router.add_get('/api/admin/stats', api_admin_stats)
app.router.add_post('/api/lectures/create', api_create_lecture)

# 2. Специальные маршруты для админ-панели
app.router.add_get('/admin/lectures.html', admin_lectures_handler)

# 3. Главная страница
app.router.add_get('/', index_handler)

# 4. Статика
html_dir = os.path.join(BASE_DIR, 'html_dir')
if os.path.exists(html_dir):
    app.router.add_static('/static', html_dir)
    print(f"✅ Статика подключена из {html_dir}")

# 5. Загрузки
uploads_dir = os.path.join(BASE_DIR, 'uploads')
if os.path.exists(uploads_dir):
    app.router.add_static('/uploads', uploads_dir)
    print(f"✅ Загрузки доступны из {uploads_dir}")

# 6. Catch-all маршрут (в самом конце!)
app.router.add_get('/{tail:.*}', catch_all_handler)


# ==================== STARTUP ====================
async def on_startup(app):
    """Запуск при старте приложения"""
    print("=" * 60)
    print("🚀 ЗАПУСК ОБРАЗОВАТЕЛЬНОЙ ПЛАТФОРМЫ")
    print("=" * 60)

    try:
        # Создаем необходимые директории
        directories = [
            os.path.join(BASE_DIR, 'html_dir'),
            os.path.join(BASE_DIR, 'html_dir', 'admin'),
            os.path.join(BASE_DIR, 'uploads'),
            os.path.join(BASE_DIR, 'uploads', 'lectures')
        ]

        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"📁 Создана директория: {directory}")

        # Проверяем наличие файлов
        index_file = os.path.join(BASE_DIR, 'html_dir', 'index.html')
        if os.path.exists(index_file):
            print(f"✅ index.html найден")
        else:
            print(f"⚠️  index.html не найден")

        admin_dir = os.path.join(BASE_DIR, 'html_dir', 'admin')
        if os.path.exists(admin_dir):
            print(f"✅ Папка admin найдена")
            lectures_file = os.path.join(admin_dir, 'lectures.html')
            if os.path.exists(lectures_file):
                print(f"✅ admin/lectures.html найден")
            else:
                print(f"⚠️  admin/lectures.html не найден")
        else:
            print(f"⚠️  Папка admin не найдена")

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

        # Проверка модуля лекций
        if LECTURES_AVAILABLE:
            print("✅ Модуль лекций доступен")
            # Выводим информацию о полях модели
            print("📋 Информация о модели Lecture:")
            import inspect
            lecture_fields = []
            for name, value in inspect.getmembers(Lecture):
                if not name.startswith('_') and not inspect.ismethod(value):
                    lecture_fields.append(name)
            print(f"   Поля: {lecture_fields}")
        else:
            print("⚠️ Модуль лекций не доступен")

        # Запускаем бота
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            asyncio.create_task(dp.start_polling(bot, skip_updates=True))
            print("✅ Telegram бот запущен")
        except Exception as e:
            print(f"⚠️ Ошибка запуска бота: {e}")
            print("⚠️ Будет работать только веб-сервер")

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