import os
import logging
import random
import string
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
import asyncio

# --- Загрузка токена из .env ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("В .env отсутствует BOT_TOKEN")

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    filename="bot.log",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

# --- Инициализация бота и диспетчера с памятью состояний ---
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot=bot, storage=storage)

# --- Временная зона ---
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

# --- Менеджеры (ID) ---
MANAGERS = {5546292835, 1789838272}

# --- Кодовые слова ---
CODEWORD_STEP1 = "Симфония"
CODEWORD_STEP2 = "Людвиг Ван Бетховен"

# --- Поддерживаемые языки ---
LANGUAGES = {
    "ru": "Русский",
    "ua": "Українська",
    "kz": "Қазақша",
    "by": "Беларуская",
    "en": "English",
    "pl": "Polski"
}

# --- Подключение к SQLite ---
conn = sqlite3.connect("lknvpn_bot.db", check_same_thread=False)
cursor = conn.cursor()

# --- Создание таблиц ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    code TEXT PRIMARY KEY,
    user_id INTEGER,
    problem TEXT,
    status TEXT,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS problem_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT UNIQUE,
    count INTEGER DEFAULT 1
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    idea TEXT,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    rating INTEGER,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    language TEXT DEFAULT 'ru',
    last_interaction TEXT
)
""")

conn.commit()

# --- Состояния ---
class Form(StatesGroup):
    codeword_wait1 = State()
    codeword_wait2 = State()
    language_select = State()
    waiting_for_device = State()
    waiting_for_server = State()
    waiting_for_country = State()
    waiting_for_resolve = State()
    waiting_for_problem_desc = State()
    waiting_for_idea = State()
    waiting_for_rating = State()
    waiting_for_manager_problem = State()

# --- Вспомогательные функции ---

def now_moscow():
    return datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M:%S")

def generate_ticket_code(length=6):
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choice(chars) for _ in range(length))
        cursor.execute("SELECT code FROM tickets WHERE code = ?", (code,))
        if not cursor.fetchone():
            return code

async def notify_managers(text: str):
    for manager_id in MANAGERS:
        try:
            await bot.send_message(manager_id, text)
        except Exception as e:
            logger.error(f"Ошибка при отправке менеджеру {manager_id}: {e}")

async def send_farewell(user_id: int):
    phrases = [
        "Спасибо за обращение! Всегда рады помочь.",
        "Будьте на связи и безопасного интернета!",
        "Если что — обращайтесь, LKN VPN 24/7.",
        "Желаем вам отличного дня и стабильного VPN.",
    ]
    phrase = random.choice(phrases)
    try:
        await bot.send_message(user_id, phrase, reply_markup=main_menu())
    except Exception as e:
        logger.error(f"Ошибка при отправке прощального сообщения пользователю {user_id}: {e}")

def user_language(user_id: int):
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else "ru"

def save_user_language(user_id: int, lang: str):
    cursor.execute(
        "INSERT INTO users (user_id, language, last_interaction) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET language=?, last_interaction=?",
        (user_id, lang, now_moscow(), lang, now_moscow())
    )
    conn.commit()

# --- Клавиатуры ---

def main_menu():
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="Как подключить VPN", callback_data="how_connect"),
        types.InlineKeyboardButton(text="Не работает VPN", callback_data="vpn_not_work"),
    )
    kb.row(
        types.InlineKeyboardButton(text="Сбор IP и логов", callback_data="logs"),
        types.InlineKeyboardButton(text="Подписка (актуально)", callback_data="paid_subscription"),
    )
    kb.row(
        types.InlineKeyboardButton(text="Предложить идею", callback_data="ideas"),
        types.InlineKeyboardButton(text="Сервер РФ — особенности", callback_data="rf_server"),
    )
    kb.row(
        types.InlineKeyboardButton(text="Админ-панель", callback_data="admin_panel"),
    )
    return kb.as_markup()

def device_menu():
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="Android", callback_data="device_Android"),
        types.InlineKeyboardButton(text="iOS", callback_data="device_iOS"),
    )
    kb.row(
        types.InlineKeyboardButton(text="Windows", callback_data="device_Windows"),
        types.InlineKeyboardButton(text="MacOS", callback_data="device_MacOS"),
    )
    return kb.as_markup()

def server_menu():
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="Россия 🇷🇺", callback_data="server_Russia"),
        types.InlineKeyboardButton(text="Нидерланды 🇳🇱", callback_data="server_Netherlands"),
    )
    return kb.as_markup()

def countries_menu():
    countries = ["Украина", "Россия", "США", "Великобритания", "Казахстан", "Беларусь", "Другая страна"]
    kb = InlineKeyboardBuilder()
    for c in countries:
        kb.button(text=c, callback_data=f"country_{c}")
    kb.adjust(2)
    return kb.as_markup()

def resolve_menu():
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="Решено", callback_data="resolved"),
        types.InlineKeyboardButton(text="Не решено", callback_data="not_resolved"),
    )
    return kb.as_markup()

def rating_keyboard():
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text=str(i), callback_data=f"rating_{i}")
    kb.adjust(5)
    return kb.as_markup()

def admin_menu():
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="Просмотр обращений", callback_data="admin_tickets"),
        types.InlineKeyboardButton(text="Статистика", callback_data="admin_stats"),
    )
    return kb.as_markup()

def language_menu():
    kb = InlineKeyboardBuilder()
    for code, name in LANGUAGES.items():
        kb.button(text=name, callback_data=f"lang_{code}")
    kb.adjust(2)
    return kb.as_markup()

# --- Обработчики команд и состояний ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer(
        "🔐 Добро пожаловать в поддержку LKN VPN!\n\n"
        "Для начала введите первое кодовое слово.",
    )
    await state.set_state(Form.codeword_wait1)

@dp.message(Form.codeword_wait1)
async def process_codeword1(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == CODEWORD_STEP1.lower():
        await message.answer("Отлично! Теперь введите второе кодовое слово.")
        await state.set_state(Form.codeword_wait2)
    else:
        await message.answer("Неверное кодовое слово. Попробуйте снова.")

@dp.message(Form.codeword_wait2)
async def process_codeword2(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == CODEWORD_STEP2.lower():
        await message.answer("Кодовые слова подтверждены. Выберите язык / Choose language:", reply_markup=language_menu())
        await state.set_state(Form.language_select)
    else:
        await message.answer("Неверное кодовое слово. Попробуйте снова.")

@dp.callback_query(Form.language_select, F.data.startswith("lang_"))
async def process_language(callback: types.CallbackQuery, state: FSMContext):
    lang_code = callback.data.split("_")[1]
    save_user_language(callback.from_user.id, lang_code)
    await callback.answer()
    await callback.message.answer("Язык установлен. Вот главное меню:", reply_markup=main_menu())
    await state.clear()

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Команды:\n"
        "/start — Запуск бота\n"
        "/help — Помощь\n"
        "Используйте кнопки меню для навигации."
    )

# --- Обработка кнопок главного меню ---

@dp.callback_query(F.data == "how_connect")
async def cb_how_connect(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Выберите устройство:", reply_markup=device_menu())
    await state.set_state(Form.waiting_for_device)

@dp.callback_query(F.data == "vpn_not_work")
async def cb_vpn_not_work(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Выберите сервер:", reply_markup=server_menu())
    await state.set_state(Form.waiting_for_server)

@dp.callback_query(F.data == "logs")
async def cb_logs(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Мы не собираем личные данные, кроме даты регистрации.\n"
        "Ваш VPN абсолютно анонимен.",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "paid_subscription")
async def cb_paid_subscription(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "В данный момент VPN бесплатен.\n"
        "Платная подписка планируется не раньше конца 2025.",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "ideas")
async def cb_ideas(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Пожалуйста, напишите свои идеи и предложения.")
    await state.set_state(Form.waiting_for_idea)

@dp.callback_query(F.data == "rf_server")
async def cb_rf_server(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Серверы РФ работают стабильно и не блокируются РКН.\n"
        "Вы можете смотреть YouTube и другие сервисы без ограничений.",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in MANAGERS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer("Админ-панель", reply_markup=admin_menu())

# --- Обработка выбора устройства ---

@dp.callback_query(Form.waiting_for_device, F.data.startswith("device_"))
async def cb_device(callback: types.CallbackQuery, state: FSMContext):
    device = callback.data.split("_")[1]
    await callback.answer()
    # В реальном коде нужно вытягивать ключи/инструкции из базы или конфигурации
    key_text = "vless://examplekey"  # заглушка ключа

    instructions = {
        "Android": (
            "Инструкция для Android:\n"
            "1. Скачайте приложение v2RayTun.\n"
            "2. Нажмите '+' и выберите 'Ручной ввод'.\n"
            f"3. Вставьте ключ:\n`{key_text}`\n"
            "4. Подключитесь и пользуйтесь.\n\n"
            "Статус VPN: Активно (VLESS)"
        ),
        "iOS": (
            "Инструкция для iOS:\n"
            "1. Скачайте ShadowRay.\n"
            f"2. Добавьте конфигурацию с ключом:\n`{key_text}`\n"
            "3. Подключитесь.\n\n"
            "Статус VPN: Активно (VLESS)"
        ),
        "Windows": (
            "Инструкция для Windows:\n"
            "1. Скачайте приложение hiddify.\n"
            "2. Нажмите '+' → 'Ручной ввод'.\n"
            f"3. Вставьте ключ:\n`{key_text}`\n"
            "4. Включите VPN.\n\n"
            "Статус VPN: Активно (VLESS)"
        ),
        "MacOS": (
            "Инструкция для MacOS:\n"
            "1. Скачайте ShadowRay или аналог.\n"
            f"2. Вставьте ключ:\n`{key_text}`\n"
            "3. Подключитесь.\n\n"
            "Статус VPN: Активно (VLESS)"
        ),
    }

    text = instructions.get(device, "Выберите устройство из списка.")
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=resolve_menu())
    await state.set_state(Form.waiting_for_resolve)

# --- Обработка выбора сервера ---

@dp.callback_query(Form.waiting_for_server, F.data.startswith("server_"))
async def cb_server(callback: types.CallbackQuery, state: FSMContext):
    server = callback.data.split("_")[1]
    await state.update_data(chosen_server=server)
    await callback.answer()
    await callback.message.answer("В какой стране вы находитесь?", reply_markup=countries_menu())
    await state.set_state(Form.waiting_for_country)

# --- Обработка выбора страны ---

@dp.callback_query(Form.waiting_for_country, F.data.startswith("country_"))
async def cb_country(callback: types.CallbackQuery, state: FSMContext):
    country = callback.data.split("_")[1]
    data = await state.get_data()
    server = data.get("chosen_server")
    await callback.answer()

    if server == "Russia" and country == "Украина":
        await callback.message.answer(
            "Внимание: Украинские операторы блокируют IP серверов РФ.\n"
            "Рекомендуем использовать сервер Нидерланды 🇳🇱.",
            reply_markup=resolve_menu(),
        )
    else:
        await callback.message.answer(
            "Рекомендации:\n"
            "• Проверьте интернет\n"
            "• Перезапустите приложение\n"
            "• Включите/выключите VPN\n"
            "• Проверьте настройки\n\n"
            "Статус VPN: Активно (VLESS)",
            reply_markup=resolve_menu(),
        )
    await state.set_state(Form.waiting_for_resolve)

# --- Решено/Не решено ---

@dp.callback_query(Form.waiting_for_resolve, F.data.in_({"resolved", "not_resolved"}))
async def cb_resolve(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data == "resolved":
        await callback.message.answer("Рад помочь! Оцените качество от 1 до 5:", reply_markup=rating_keyboard())
        await state.set_state(Form.waiting_for_rating)
    else:
        await callback.message.answer("Опишите проблему подробно, мы свяжемся с вами.")
        await state.set_state(Form.waiting_for_manager_problem)

# --- Оценка качества ---

@dp.callback_query(Form.waiting_for_rating, F.data.startswith("rating_"))
async def cb_rating(callback: types.CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    await callback.answer()
    cursor.execute(
        "INSERT INTO ratings (user_id, rating, created_at) VALUES (?, ?, ?)",
        (callback.from_user.id, rating, now_moscow())
    )
    conn.commit()

    if rating < 2:
        await callback.message.answer("Жаль, что не всё понравилось. Пожалуйста, расскажите, что не устроило.")
        await state.set_state(Form.waiting_for_problem_desc)
    else:
        await send_farewell(callback.from_user.id)
        await state.clear()

# --- Подробности проблемы ---

@dp.message(Form.waiting_for_problem_desc)
async def msg_problem_desc(message: types.Message, state: FSMContext):
    desc = message.text.strip()
    cursor.execute("SELECT id, count FROM problem_feedback WHERE description = ?", (desc,))
    row = cursor.fetchone()
    if row:
        pid, count = row
        cursor.execute("UPDATE problem_feedback SET count = ? WHERE id = ?", (count + 1, pid))
    else:
        cursor.execute("INSERT INTO problem_feedback(description, count) VALUES (?, 1)", (desc,))
    conn.commit()
    await message.answer("Спасибо за обратную связь! Мы работаем над улучшением.")
    await send_farewell(message.from_user.id)
    await state.clear()

# --- Проблема менеджеру ---
@dp.message(Form.waiting_for_manager_problem)
async def msg_manager_problem(message: types.Message, state: FSMContext):
    problem = message.text.strip()
    code = generate_ticket_code()
    cursor.execute(
        "INSERT INTO tickets (code, user_id, problem, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (code, message.from_user.id, problem, "new", now_moscow())
    )
    conn.commit()
    await message.answer(
        f"Спасибо! Ваша заявка принята.\nКод обращения: {code}\nМенеджер свяжется с вами в ближайшее время.\nПожалуйста, оцените сервис от 1 до 5.",
        reply_markup=rating_keyboard()
    )
    await state.set_state(Form.waiting_for_rating)

    # Отправка менеджерам
    text = (f"Новая заявка #{code} от @{message.from_user.username or message.from_user.full_name}:\n"
            f"{problem}\n"
            f"Время: {now_moscow()}")
    await notify_managers(text)

# --- Идеи ---
@dp.message(Form.waiting_for_idea)
async def msg_idea(message: types.Message, state: FSMContext):
    idea = message.text.strip()
    cursor.execute(
        "INSERT INTO ideas (user_id, idea, created_at) VALUES (?, ?, ?)",
        (message.from_user.id, idea, now_moscow())
    )
    conn.commit()
    await message.answer("Спасибо за вашу идею! Мы обязательно её рассмотрим.", reply_markup=main_menu())
    await state.clear()

# --- Админ — просмотр заявок ---
@dp.callback_query(F.data == "admin_tickets")
async def cb_admin_tickets(callback: types.CallbackQuery):
    if callback.from_user.id not in MANAGERS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    cursor.execute("SELECT code, user_id, problem, status, created_at FROM tickets ORDER BY created_at DESC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        await callback.message.answer("Нет заявок для отображения.")
        await callback.answer()
        return

    text = "Последние обращения:\n\n"
    for code, user_id, problem, status, created_at in rows:
        text += (f"Код: {code}\nПользователь: {user_id}\nПроблема: {problem}\n"
                 f"Статус: {status}\nДата: {created_at}\n\n")
    await callback.message.answer(text)

# --- Админ — статистика ---
@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in MANAGERS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    cursor.execute("SELECT COUNT(*) FROM tickets")
    total_tickets = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(rating) FROM ratings")
    avg_rating = cursor.fetchone()[0]
    avg_rating = round(avg_rating, 2) if avg_rating else "Нет оценок"

    cursor.execute("SELECT description, count FROM problem_feedback ORDER BY count DESC LIMIT 5")
    problems = cursor.fetchall()

    text = (f"📊 Статистика бота:\n"
            f"Общее количество заявок: {total_tickets}\n"
            f"Средний рейтинг обслуживания: {avg_rating}\n\n"
            f"Частые проблемы:\n")

    if problems:
        for desc, count in problems:
            text += f"- {desc} ({count} раз)\n"
    else:
        text += "Пока проблем не зарегистрировано."

    await callback.message.answer(text)

# --- Обработка неизвестных сообщений ---
@dp.message()
async def unknown_message(message: types.Message):
    await message.answer("Используйте команды /start или кнопки меню для навигации.")

# --- Запуск бота ---
if __name__ == "__main__":
    import asyncio
    print("Бот запускается...")
    asyncio.run(dp.start_polling())