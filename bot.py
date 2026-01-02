# bot.py - РАБОЧАЯ ВЕРСИЯ С ВСЕМИ ФУНКЦИЯМИ
import os
import asyncio
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

        # Пробуем получить или создать пользователя в БД
        try:
            from models.database_manager import db
            db.get_or_create_user(user.id, user.first_name or user.username)
            print(f"✅ Пользователь {user.id} зарегистрирован в БД")
        except ImportError as e:
            print(f"⚠️ Модуль БД не найден: {e}")
        except Exception as e:
            print(f"⚠️ Ошибка БД: {e}")

        # URL для веб-приложения
        web_app_url = os.getenv("WEB_APP_URL", "https://localhost:8000")

        # Формируем параметры для сессии
        query_params = urlencode({
            "user_id": user.id,
            "username": user.first_name or user.username
        })
        full_url = f"{web_app_url}/api/init_session?{query_params}"

        # Клавиатура с кнопкой веб-приложения
        kb = ReplyKeyboardMarkup(
            keyboard=[
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
            ],
            resize_keyboard=True
        )

        welcome_text = f"""🎓 Привет, {user.first_name or user.username}!

Добро пожаловать в образовательную платформу!

📌 <b>Нажмите на кнопку ниже, чтобы открыть веб-приложение:</b>
• 📚 Просмотр и загрузка лекций
• 🎯 Прохождение семинаров
• 👨‍🏫 Управление пользователями (для админов)

💡 Веб-приложение откроется прямо в Telegram!
"""

        await message.answer(welcome_text, reply_markup=kb)
        print(f"✅ /start отправлен пользователю {user.id}")

    except Exception as e:
        print(f"❌ Ошибка в start_cmd: {e}")
        await message.answer("Привет! Используйте кнопки меню.")


@dp.message(lambda message: message.text == "🌐 Открыть веб-приложение")
async def open_web_app_button(message: types.Message):
    """Обработка нажатия на кнопку веб-приложения (fallback)"""
    try:
        user = message.from_user
        web_app_url = os.getenv("WEB_APP_URL", "https://localhost:8000")
        web_app_full_url = f"{web_app_url}/api/init_session?user_id={user.id}&username={user.first_name or user.username}&is_telegram=true"

        # Если кнопка не работает, показываем инструкцию
        help_text = f"""🌐 <b>Как открыть веб-приложение:</b>

1. Нажмите на кнопку <b>"🌐 Открыть веб-приложение"</b> в меню
2. Веб-приложение откроется прямо в Telegram

📱 <b>Если кнопка не работает:</b>
• Обновите Telegram до последней версии
• Используйте Telegram на телефоне (веб-приложения лучше работают в мобильной версии)
• Или перейдите по ссылке: {web_app_full_url}

💡 <b>Важно:</b> В браузере функция входа через Telegram будет недоступна."""

        await message.answer(help_text, disable_web_page_preview=True)

        # Также отправляем кнопку отдельно для удобства
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(
                    text="🌐 Открыть веб-приложение",
                    web_app=WebAppInfo(url=web_app_full_url)
                )]
            ],
            resize_keyboard=True
        )
        await message.answer("Попробуйте нажать здесь:", reply_markup=kb)

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
    web_app_url = os.getenv("WEB_APP_URL", "https://localhost:8000")

    help_text = f"""📚 <b>Помощь по боту:</b>

<b>Основные команды:</b>
/start - Главное меню
/help - Эта справка
/webapp - Быстрый доступ к веб-приложению

<b>Основные кнопки:</b>
🌐 <b>Открыть веб-приложение</b> - веб-приложение прямо в Telegram
📊 Рейтинг - таблица лидеров
👤 Профиль - ваша статистика

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
        web_app_url = os.getenv("WEB_APP_URL", "https://localhost:8000")
        web_app_full_url = f"{web_app_url}/api/init_session?user_id={user.id}&username={user.first_name or user.username}&is_telegram=true"

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

        # Редирект на главную страницу
        raise web.HTTPFound('/')
    except Exception as e:
        print(f"❌ Ошибка в init_session: {e}")
        raise web.HTTPFound('/')


async def index_handler(request):
    """Главная страница - просто отдаём файл"""
    html_dir = os.path.join(BASE_DIR, 'html_dir')
    index_file = os.path.join(html_dir, 'index.html')

    if os.path.exists(index_file):
        return web.FileResponse(index_file)
    else:
        # Если файла нет - ошибка 404
        return web.Response(text='File index.html not found', status=404)


# ==================== ROUTES SETUP ====================
app.router.add_get('/', index_handler)
app.router.add_get('/api/health', api_health)
app.router.add_get('/api/init_session', init_session)

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

        # Запускаем бота
        await bot.delete_webhook(drop_pending_updates=True)
        asyncio.create_task(dp.start_polling(bot, skip_updates=True))
        print("✅ Telegram бот запущен")

        web_app_url = os.getenv("WEB_APP_URL", "https://localhost:8000")
        print(f"🌐 Веб-приложение доступно по адресу: {web_app_url}")

    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")


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

    print(f"🌐 Веб-сервер запущен на http://{host}:{port}")
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