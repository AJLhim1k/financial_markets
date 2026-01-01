# bot.py
import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from urllib.parse import urlencode

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Загрузка переменных окружения
load_dotenv()

# Инициализация бота
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
        except:
            pass  # Игнорируем ошибки БД

        # URL для веб-приложения
        web_app_url = os.getenv("WEB_APP_URL", "https://localhost:8000")

        # Формируем параметры для сессии
        query_params = urlencode({
            "user_id": user.id,
            "username": user.first_name or user.username
        })
        full_url = f"{web_app_url}/api/init_session?{query_params}"

        # Клавиатура с кнопкой веб-приложения
        kb = types.ReplyKeyboardMarkup(
            keyboard=[
                [
                    types.KeyboardButton(
                        text="🌐 Открыть веб-приложение",
                        web_app=types.WebAppInfo(url=full_url)
                    )
                ],
                [
                    types.KeyboardButton(text="📊 Рейтинг"),
                    types.KeyboardButton(text="👤 Профиль")
                ]
            ],
            resize_keyboard=True
        )

        welcome_text = f"""🎓 Привет, {user.first_name}!

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
        # Пробуем получить реальный рейтинг
        try:
            from models.database_manager import db
            user_id = message.from_user.id

            # Получаем топ-5
            top_players = db.get_top_players(5)

            if top_players:
                response = "🏆 Топ-5 студентов:\n\n"
                for i, player in enumerate(top_players, 1):
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    response += f"{medal} {player['username']} - {player['score']} баллов\n"

                # Получаем позицию пользователя
                user_position, user_score = db.get_user_position(user_id)
                response += f"\n📊 Ваша позиция: {user_position}\n"
                response += f"🎯 Ваши баллы: {user_score}"
                await message.answer(response)
            else:
                await message.answer("📊 Рейтинг пока пуст. Данные в разработке.")

        except ImportError:
            await message.answer("📊 Модуль рейтинга в разработке. Откройте веб-приложение для просмотра.")
        except Exception as e:
            print(f"⚠️ Ошибка получения рейтинга: {e}")
            await message.answer("📊 Рейтинг временно недоступен. Откройте веб-приложение.")

    except Exception as e:
        print(f"❌ Ошибка показа рейтинга: {e}")
        await message.answer("Ошибка при получении рейтинга.")


@dp.message(lambda message: message.text == "👤 Профиль")
async def show_profile(message: types.Message):
    """Показать профиль пользователя"""
    try:
        user = message.from_user

        # Пробуем получить реальный профиль
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
                user_position = db.get_user_position(user.id)[0]

                response = f"""👤 Ваш профиль:

📛 Имя: {db_user.username}
👥 Текущая группа: {group_name}
🏆 Баллы: {db_user.score}
⭐ Оценка за семинары: {db_user.seminar_grade or 'еще не рассчитана'}

📈 Ваша позиция в рейтинге: {user_position}"""
                await message.answer(response)
            else:
                await message.answer("👤 Профиль не найден. Откройте веб-приложение для регистрации.")

        except ImportError:
            await message.answer("👤 Модуль профиля в разработке. Откройте веб-приложение.")
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

<b>Поддержка:</b> support@education-platform.ru
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
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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
        'version': '2.0.0'
    })


async def init_session(request):
    """Инициализация сессии из Telegram"""
    user_id = request.query.get('user_id')
    username = request.query.get('username')

    if user_id and username:
        # Пробуем зарегистрировать пользователя
        try:
            from models.database_manager import db
            db.get_or_create_user(int(user_id), username)
        except:
            pass  # Игнорируем ошибки БД

    # Редирект на главную страницу
    raise web.HTTPFound('/')


# ==================== ROUTES SETUP ====================

app = web.Application()

# API endpoints
app.router.add_get('/api/health', api_health)
app.router.add_get('/api/init_session', init_session)

# HTML страницы - статика
app.router.add_static('/', path=os.path.join(BASE_DIR, 'html_dir'))


# ==================== STARTUP ====================

async def on_startup(app):
    """Запуск при старте приложения"""
    print("🔧 Инициализация бота и веб-сервера...")

    print("🌐 Настройка веб-приложения...")
    print(f"   WEB_APP_URL: {os.getenv('WEB_APP_URL', 'https://localhost:8000')}")
    print("   Веб-приложение будет открываться прямо в Telegram")
    print("   Убедитесь, что используете HTTPS для production!")

    # Проверяем что есть html_dir с index.html
    html_dir = os.path.join(BASE_DIR, 'html_dir')
    index_file = os.path.join(html_dir, 'index.html')

    if not os.path.exists(html_dir):
        os.makedirs(html_dir)
        print(f"📁 Создана директория: {html_dir}")

    if not os.path.exists(index_file):
        print(f"⚠️  Файл {index_file} не найден!")
        print("   Создай html_dir/index.html или запусти create_html.py")

    # Запуск polling для бота
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        asyncio.create_task(dp.start_polling(bot, skip_updates=True))
        print("🤖 Бот запущен")
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")

    print(f"🚀 Веб-сервер запущен на https://0.0.0.0:8000")
    print("📱 Используйте /start в Telegram и нажмите кнопку для открытия веб-приложения")


app.on_startup.append(on_startup)

# ==================== ВАЖНОЕ ПРИМЕЧАНИЕ ====================
"""
Для корректной работы веб-приложения в Telegram:

1. В production должен быть HTTPS (Telegram требует безопасное соединение)
2. Можно использовать:
   - Облачные хостинги (Heroku, Render, Railway)
   - VPS с настроенным SSL (nginx + Let's Encrypt)
   - Cloudflare Tunnel
   - Ngrok для тестирования (ngrok http 8000 --host-header="localhost:8000")

3. Установите WEB_APP_URL в .env:
   Для теста через ngrok: WEB_APP_URL=https://ваш-домен.ngrok.io
   Для production: WEB_APP_URL=https://ваш-домен.com

4. Telegram Web Apps работают только в:
   - Мобильных приложениях Telegram (iOS/Android)
   - Telegram Desktop (последние версии)
   - НЕ работают в веб-версии Telegram
"""


# ==================== MAIN ====================

async def main():
    """Асинхронная функция запуска"""
    # Проверка переменных окружения
    if not os.getenv("TELEGRAM_API_KEY"):
        print("❌ TELEGRAM_API_KEY не установлен!")
        print("💡 Создай .env файл с токеном бота")
        return

    print("=" * 50)
    print("🎓 Образовательная платформа")
    print("🤖 Telegram бот + Веб-приложение внутри Telegram")
    print("=" * 50)

    # Создаем и запускаем runner
    runner = web.AppRunner(app)
    await runner.setup()

    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8000))

    site = web.TCPSite(runner, host, port)
    await site.start()

    print(f"🌐 Веб-сервер запущен на https://{host}:{port}")
    print("📱 Теперь веб-приложение будет открываться прямо в Telegram!")
    print("⚠️  Для production необходим HTTPS и правильный WEB_APP_URL в .env")

    # Ожидаем сигнала завершения
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n👋 Завершение работы по запросу пользователя")
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Приложение завершено")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()