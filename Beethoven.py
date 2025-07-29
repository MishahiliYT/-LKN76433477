import os import logging import random import string import sqlite3 from aiogram import Bot, Dispatcher, types, F, Router from aiogram.fsm.storage.memory import MemoryStorage from aiogram.fsm.context import FSMContext from aiogram.filters.state import State, StatesGroup from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton from aiogram.utils.keyboard import InlineKeyboardBuilder from dotenv import load_dotenv import asyncio

--- Загрузка .env ---

load_dotenv() BOT_TOKEN = os.getenv("BOT_TOKEN") if not BOT_TOKEN: raise ValueError("Отсутствует токен бота в переменных окружения")

--- Инициализация логов ---

logging.basicConfig(level=logging.INFO) logger = logging.getLogger(name)

--- Инициализация бота ---

bot = Bot(token=BOT_TOKEN) storage = MemoryStorage() dp = Dispatcher(storage=storage) router = Router()

--- Менеджеры ---

MANAGERS = [5546292835, 1789838272]

--- БД ---

conn = sqlite3.connect("tickets.db") cursor = conn.cursor() cursor.execute(""" CREATE TABLE IF NOT EXISTS tickets ( code TEXT PRIMARY KEY, user_id INTEGER, problem TEXT, status TEXT ) """) cursor.execute(""" CREATE TABLE IF NOT EXISTS problem_feedback ( id INTEGER PRIMARY KEY AUTOINCREMENT, description TEXT, count INTEGER DEFAULT 1 ) """) conn.commit()

--- Состояния ---

class Form(StatesGroup): waiting_for_device = State() waiting_for_server = State() waiting_for_country = State() waiting_for_resolve = State() waiting_for_problem_desc = State() waiting_for_idea = State() waiting_for_rating = State() waiting_for_manager_problem = State() waiting_for_admin_code = State() waiting_for_admin_code2 = State()

--- Фразы ---

FAREWELL_PHRASES = [ "Спасибо, что выбрали LKN VPN!", "Желаем вам отличного дня!", "Всегда рады помочь!", "VPN с любовью от LKN 💙", "Спасибо за использование нашего сервиса!" ]

--- Клавиатуры ---

def main_menu(): kb = InlineKeyboardBuilder() kb.row( InlineKeyboardButton(text="Как подключить VPN", callback_data="how_connect"), InlineKeyboardButton(text="Не работает VPN", callback_data="vpn_not_work") ) kb.row( InlineKeyboardButton(text="Сбор ip, логов", callback_data="logs"), InlineKeyboardButton(text="Когда платная подписка", callback_data="paid_subscription") ) kb.row( InlineKeyboardButton(text="Предложить инновации", callback_data="ideas"), InlineKeyboardButton(text="Как работает РФ сервер", callback_data="rf_server") ) return kb.as_markup()

def device_menu(): kb = InlineKeyboardBuilder() kb.row( InlineKeyboardButton(text="Android", callback_data="device_Android"), InlineKeyboardButton(text="MacOS", callback_data="device_MacOS") ) kb.row( InlineKeyboardButton(text="Windows", callback_data="device_Windows"), InlineKeyboardButton(text="IOS", callback_data="device_IOS") ) return kb.as_markup()

def server_menu(): kb = InlineKeyboardBuilder() kb.row( InlineKeyboardButton(text="Россия 🇷🇺", callback_data="server_Russia"), InlineKeyboardButton(text="Нидерланды 🇳🇱", callback_data="server_Netherlands") ) return kb.as_markup()

def countries_menu(): countries = ["Украина", "Россия", "США", "Великобритания", "Казахстан", "Беларусь", "Нет моей страны"] kb = InlineKeyboardBuilder() for c in countries: kb.button(text=c, callback_data=f"country_{c}") kb.adjust(2) return kb.as_markup()

def resolve_menu(): kb = InlineKeyboardBuilder() kb.row( InlineKeyboardButton(text="Решено", callback_data="resolved"), InlineKeyboardButton(text="Не решено", callback_data="not_resolved") ) return kb.as_markup()

def rating_keyboard(): kb = InlineKeyboardBuilder() for i in range(1,6): kb.button(text=str(i), callback_data=f"rating_{i}") kb.adjust(5) return kb.as_markup()

def admin_panel(): kb = InlineKeyboardBuilder() kb.button(text="Ответить на код", callback_data="admin_answer") return kb.as_markup()

--- Утилиты ---

def generate_ticket_code(): chars = string.ascii_uppercase + string.digits while True: code = ''.join(random.choice(chars) for _ in range(6)) cursor.execute("SELECT code FROM tickets WHERE code = ?", (code,)) if not cursor.fetchone(): return code

async def send_farewell(user_id): phrase = random.choice(FAREWELL_PHRASES) await bot.send_message(user_id, phrase, reply_markup=main_menu())

--- Обработчики ---

@dp.message(F.text.lower() == "симфония") async def admin_code1(message: types.Message, state: FSMContext): if message.from_user.id in MANAGERS: await state.set_state(Form.waiting_for_admin_code2) await message.answer("Введите второе кодовое слово:")

@dp.message(Form.waiting_for_admin_code2, F.text.lower() == "людвиг ван бетховен") async def admin_panel_access(message: types.Message, state: FSMContext): await message.answer("Добро пожаловать в админ-панель", reply_markup=admin_panel()) await state.clear()

@dp.callback_query(F.data == "admin_answer") async def admin_answer_prompt(callback: types.CallbackQuery): await callback.message.answer("Напиши: /answer <код> <текст ответа>")

@dp.message(F.text.startswith("/answer")) async def manager_answer(message: types.Message): parts = message.text.split(maxsplit=2) if len(parts) < 3: await message.answer("Формат: /answer <код> <текст ответа>") return code, answer = parts[1], parts[2] cursor.execute("SELECT user_id FROM tickets WHERE code = ?", (code,)) row = cursor.fetchone() if not row: await message.answer("Код не найден") return user_id = row[0] try: await bot.send_message(user_id, f"Ответ от менеджера:\n{answer}") await bot.send_message(user_id, "Решена ли ваша проблема?", reply_markup=resolve_menu()) await message.answer("Отправлено") except Exception as e: await message.answer(f"Ошибка: {e}")

@dp.message(F.text.startswith("/start")) async def cmd_start(message: types.Message, state: FSMContext): await message.answer( "🔐 Добро пожаловать в поддержку LKN VPN!\n\n" "Выберите раздел или опишите проблему.\n\n" "🛡 Быстро, бесплатно и 24/7.", reply_markup=main_menu() )

@dp.callback_query(F.data == "how_connect") async def how_connect(callback: types.CallbackQuery, state: FSMContext): await callback.answer() await callback.message.answer("Выберите ваше устройство:", reply_markup=device_menu()) await state.set_state(Form.waiting_for_device)

@dp.callback_query(Form.waiting_for_device, F.data.startswith("device_")) async def device_response(callback: types.CallbackQuery, state: FSMContext): device = callback.data.split("_")[1] await callback.answer() if device == "Windows": text = ( "Инструкция для Windows:\n1. Скачайте Hiddify.\n2. Нажмите + -> Ручной ввод.\n3. Вставьте ключ.\n4. Подключитесь.\n\nКлюч: {}'".format(BOT_TOKEN) ) else: text = ( "Инструкция:\n1. Скачайте v2RayTun.\n2. '+' -> Ручной ввод.\n3. Вставьте ключ.\n4. Подключитесь.\n\nКлюч: {}'".format(BOT_TOKEN) ) await callback.message.answer(text, parse_mode="Markdown", reply_markup=resolve_menu()) await state.set_state(Form.waiting_for_resolve)

@dp.callback_query(F.data == "vpn_not_work") async def vpn_not_work(callback: types.CallbackQuery, state: FSMContext): await callback.answer() await callback.message.answer("Какой сервер используете?", reply_markup=server_menu()) await state.set_state(Form.waiting_for_server)

@dp.callback_query(Form.waiting_for_server, F.data.startswith("server_")) async def server_chosen(callback: types.CallbackQuery, state: FSMContext): server = callback.data.split("_")[1] await state.update_data(chosen_server=server) await callback.answer() await callback.message.answer("В какой стране вы находитесь?", reply_markup=countries_menu()) await state.set_state(Form.waiting_for_country)

@dp.callback_query(Form.waiting_for_country, F.data.startswith("country_")) async def country_chosen(callback: types.CallbackQuery, state: FSMContext): country = callback.data.split("_")[1] data = await state.get_data() server = data.get("chosen_server") await callback.answer() if server == "Russia" and country == "Украина": await callback.message.answer("IP сервера блокируется в Украине. Используйте сервер Нидерланды.", reply_markup=resolve_menu()) else: await callback.message.answer("Попробуйте: включить режим полета на 5 сек, проверить интернет, перезапустить VPN.", reply_markup=resolve_menu()) await state.set_state(Form.waiting_for_resolve)

@dp.callback_query(Form.waiting_for_resolve, F.data == "resolved") async def resolved_ok(callback: types.CallbackQuery, state: FSMContext): await callback.answer() await callback.message.answer("Оцените обслуживание от 1 до 5", reply_markup=rating_keyboard()) await state.set_state(Form.waiting_for_rating)

@dp.callback_query(Form.waiting_for_resolve, F.data == "not_resolved") async def not_resolved(callback: types.CallbackQuery, state: FSMContext): await callback.answer() await callback.message.answer("Опишите проблему, менеджер получит её.") await state.set_state(Form.waiting_for_manager_problem)

@dp.message(Form.waiting_for_manager_problem) async def problem_desc(message: types.Message, state: FSMContext): code = generate_ticket_code() cursor.execute("INSERT INTO tickets (code, user_id, problem, status) VALUES (?, ?, ?, ?)", (code, message.from_user.id, message.text.strip(), "new")) conn.commit() for manager_id in MANAGERS: try: await bot.send_message(manager_id, f"Проблема от пользователя {message.from_user.id}\nКод: {code}\n{message.text.strip()}") except: pass await message.answer("Спасибо, проблема передана менеджеру. Ожидайте ответа. Оцените качество обслуживания:", reply_markup=rating_keyboard()) await state.set_state(Form.waiting_for_rating)

@dp.callback_query(Form.waiting_for_rating, F.data.startswith("rating_")) async def rate_user(callback: types.CallbackQuery, state: FSMContext): rating = int(callback.data.split("_")[1]) await callback.answer() if rating < 2: await callback.message.answer("Напишите, что именно не устроило") await state.set_state(Form.waiting_for_problem_desc) else: await send_farewell(callback.from_user.id) await state.clear()

@dp.message(Form.waiting_for_problem_desc) async def store_feedback(message: types.Message, state: FSMContext): desc = message.text.strip().lower() cursor.execute("SELECT id, count FROM problem_feedback WHERE description = ?", (desc,)) row = cursor.fetchone() if row: pid, cnt = row cursor.execute("UPDATE problem_feedback SET count = ? WHERE id = ?", (cnt + 1, pid)) else: cursor.execute("INSERT INTO problem_feedback(description, count) VALUES (?, 1)", (desc,)) conn.commit() await message.answer("Спасибо за обратную связь. Мы это учтём.") await send_farewell(message.from_user.id) await state.clear()

--- Запуск ---

async def main(): dp.include_router(router) await dp.start_polling(bot)

if name == "main": asyncio.run(main())

