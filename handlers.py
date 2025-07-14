# handlers.py
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database import db
from keyboards import get_main_menu_keyboard
from services import check_and_notify_user, fetch_queue_data, format_car_info
from config import config

router = Router()

class UserForm(StatesGroup):
    waiting_for_token = State()
    waiting_for_car_number = State()

# --- Обработчики команд и кнопок ---

@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    """
    Обработчик команды /start. Проверяет авторизацию и приветствует пользователя.
    """
    if await db.is_user_authorized(message.from_user.id):
        await message.answer(
            "С возвращением! 👋\n\n"
            "Используйте кнопки внизу или команды для управления.",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await message.answer("Добро пожаловать! Для начала работы, пожалуйста, введите ваш уникальный токен доступа.")
        await state.set_state(UserForm.waiting_for_token)


# 👇 ИСПРАВЛЕННЫЙ ДЕКОРАТОР: теперь их два для одной функции
@router.message(F.text == "🚗 Мои авто")
@router.message(Command("mycars"))
async def handle_my_cars(message: Message, bot: Bot):
    """
    Выводит детальную информацию по каждому отслеживаемому автомобилю.
    """
    user_id = message.from_user.id
    if not await db.is_user_authorized(user_id):
        await message.answer("Пожалуйста, сначала пройдите авторизацию. Отправьте команду /start.")
        return

    cars = await db.get_user_cars(user_id)
    if not cars:
        await message.answer("У вас нет отслеживаемых автомобилей. Добавьте первый с помощью команды `/add` или кнопки.")
        return

    await message.answer("🔍 Запрашиваю актуальную информацию о ваших авто...")
    api_data = await fetch_queue_data()
    if not api_data or "carLiveQueue" not in api_data:
        await message.answer("Не удалось получить данные об очереди. Пожалуйста, попробуйте позже.")
        return

    queue = api_data["carLiveQueue"]
    total_cars_in_queue = len(queue)
    found_any = False

    for car_number in cars:
        user_car_data = next((c for c in queue if c["regnum"] == car_number), None)
        
        if user_car_data:
            found_any = True
            first_car_overall = queue[0] if queue else None
            first_waiting_car = None
            if first_car_overall and first_car_overall.get('status') == 3:
                first_waiting_car = next((c for c in queue if c.get("status") != 3), None)
            
            info_text = format_car_info(user_car_data, total_cars_in_queue, first_car_overall, first_waiting_car)
            await message.answer(info_text)
        else:
            await message.answer(f"ℹ️ Автомобиль `{car_number}` не найден в текущей очереди. Возможно, он уже проехал границу. Удаляю его из вашего списка.")
            await db.remove_car(car_number)
        
        await asyncio.sleep(0.5)

    if not found_any and cars:
        await message.answer("Ни один из ваших автомобилей не найден в текущей очереди. Возможно, они все уже проехали.")


# 👇 ИСПРАВЛЕННЫЙ ДЕКОРАТОР
@router.message(F.text == "✅ Добавить авто")
@router.message(Command("add"))
async def handle_add_command(message: Message, state: FSMContext):
    """
    Начинает процесс добавления нового автомобиля.
    """
    if not await db.is_user_authorized(message.from_user.id):
        await message.answer("Пожалуйста, сначала пройдите авторизацию. Отправьте команду /start.")
        return
        
    await state.set_state(UserForm.waiting_for_car_number)
    await message.answer("Пожалуйста, введите гос. номер автомобиля (например, `1234AB7`).")


# 👇 ИСПРАВЛЕННЫЙ ДЕКОРАТОР
@router.message(F.text == "❌ Удалить все авто")
@router.message(Command("delete"))
async def handle_delete_command(message: Message):
    """
    Удаляет все автомобили пользователя из базы данных.
    """
    if not await db.is_user_authorized(message.from_user.id):
        await message.answer("Пожалуйста, сначала пройдите авторизацию. Отправьте команду /start.")
        return

    await db.delete_all_cars(message.from_user.id)
    await message.answer("✅ Все ваши автомобили были удалены из списка отслеживания.")


# --- Обработчики состояний (FSM) ---

@router.message(UserForm.waiting_for_token)
async def process_token(message: Message, state: FSMContext):
    """
    Обрабатывает введенный токен доступа.
    """
    if message.text in config.valid_user_tokens:
        await db.authorize_user(message.from_user.id)
        await state.clear()
        await message.answer(
            "✅ **Авторизация прошла успешно!**\n\n"
            "Теперь вы можете добавить свой первый автомобиль.",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await message.answer("❌ **Неверный токен.** Пожалуйста, попробуйте еще раз или запросите новый.")


# ... (весь код до process_car_number без изменений) ...
@router.message(UserForm.waiting_for_car_number)
async def process_car_number(message: Message, state: FSMContext, bot: Bot):
    """
    Обрабатывает введенный номер автомобиля, добавляет его в БД и запускает первую проверку.
    """
    car_number = message.text.upper().replace(" ", "")
    
    try:
        # Убрали IGNORE, чтобы отловить ошибку, если номер уже есть
        await db.add_car(message.from_user.id, car_number)
    except Exception:
        await message.answer(f"❌ Не удалось добавить номер `{car_number}`. Возможно, он уже отслеживается другим пользователем. Проверьте список командой `/mycars`.")
        await state.clear()
        return

    await message.answer(f"✅ Номер `{car_number}` добавлен. Начинаю отслеживание...")
    await state.clear()
    
    await check_and_notify_user(bot, message.from_user.id, car_number, is_initial_check=True)
    await message.answer("Вы можете посмотреть статус авто в любой момент.", reply_markup=get_main_menu_keyboard())
# ... (остальной код без изменений) ...

# --- "Всеядный" обработчик ---

@router.message()
async def handle_unknown_message(message: Message):
    """
    Отвечает на любые сообщения, которые не были обработаны ранее.
    """
    await message.answer("Я не понимаю эту команду. 😕\nВоспользуйтесь `/start` для просмотра доступных команд.")