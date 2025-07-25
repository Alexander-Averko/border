# services.py
import aiohttp
import datetime
import pytz
import logging
from typing import Optional, Dict

from aiogram import Bot
from database import db
from config import config

logger = logging.getLogger(__name__)
TIMEZONE = pytz.timezone(config.timezone)

# ... (функция format_car_info остается без изменений) ...
def format_car_info(
    user_car_data: Dict,
    total_cars: int,
    first_car_overall: Optional[Dict] = None,
    first_waiting_car: Optional[Dict] = None
) -> str:
    status_map = {1: "Аннулирован", 2: "Прибыл в ЗО", 3: "Вызван в ПП"}
    date_format = "%H:%M:%S %d.%m.%Y"
    
    info_text = f"🚗 **Всего машин в очереди: {total_cars}**\n\n"

    user_status_text = status_map.get(user_car_data['status'], "Неизвестный статус")
    user_reg_time = datetime.datetime.strptime(user_car_data['registration_date'], date_format).astimezone()
    
    info_text += (
        f"🚙 **Ваш авто:** `{user_car_data['regnum']}`\n"
        f"🚦 **Статус:** *{user_status_text}*\n"
    )

    if user_car_data['status'] == 3:
        changed_time = datetime.datetime.strptime(user_car_data['changed_date'], date_format).astimezone()
        wait_time = changed_time - user_reg_time
        info_text += f"⏱ **Время ожидания (до вызова):** `{str(wait_time).split('.')[0]}`\n"
    else:
        current_time = datetime.datetime.now()
        wait_time = current_time - user_reg_time
        info_text += (
            f"📍 **Позиция в очереди:** `{user_car_data['order_id']}`\n"
            f"📅 **Зарегистрирован:** `{user_reg_time.strftime(date_format)}`\n"
            f"⏳ **В очереди уже:** `{str(wait_time).split('.')[0]}`\n"
        )

    if first_car_overall and first_car_overall.get('regnum') != user_car_data.get('regnum'):
        info_text += "\n---\n"
        reg_time = datetime.datetime.strptime(first_car_overall['registration_date'], date_format).astimezone()
        
        if first_car_overall['status'] == 3:
            title = "🔝 Вызван в ПП"
            changed_time = datetime.datetime.strptime(first_car_overall['changed_date'], date_format).astimezone()
            wait_time_str = str(changed_time - reg_time).split('.')[0]
            
            info_text += (
                f"**{title}:** `{first_car_overall['regnum']}`\n"
                f"⏱ **Время в очереди:** `{wait_time_str}`\n"
                f"📅 **Зарегистрирован:** `{reg_time.strftime(date_format)}`\n"
                f"🔔 **Вызван:** `{changed_time.strftime(date_format)}`\n"
            )
        else:
            title = "🔝 Первый в очереди"
            current_time = datetime.datetime.now()
            wait_time_str = str(current_time - reg_time).split('.')[0]
            
            info_text += (
                f"**{title}:** `{first_car_overall['regnum']}`\n"
                f"⏳ **Ожидает уже:** `{wait_time_str}`\n"
                f"📅 **Зарегистрирован:** `{reg_time.strftime(date_format)}`\n"
            )

    if first_waiting_car and first_waiting_car.get('regnum') != user_car_data.get('regnum'):
        info_text += "---\n"
        reg_time = datetime.datetime.strptime(first_waiting_car['registration_date'], date_format).astimezone()
        current_time = datetime.datetime.now()
        wait_time_str = str(current_time - reg_time).split('.')[0]
        
        info_text += (
            f"👑 **Следующий на вызов:** `{first_waiting_car['regnum']}`\n"
            f"⏳ **Ожидает уже:** `{wait_time_str}`\n"
            f"📅 **Зарегистрирован:** `{reg_time.strftime(date_format)}`\n"
        )

    return info_text


async def fetch_queue_data() -> Optional[Dict]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(config.api_url) as response:
                response.raise_for_status()
                return await response.json()
    except aiohttp.ClientError as e:
        logger.error(f"API request error: {e}")
        return None

async def check_and_notify_user(bot: Bot, user_id: int, car_number: str, is_initial_check: bool = False):
    api_data = await fetch_queue_data()
    if not api_data or "carLiveQueue" not in api_data:
        logger.warning("Could not fetch or parse API data.")
        return

    queue = api_data["carLiveQueue"]
    total_cars = len(queue)
    user_car = next((car for car in queue if car["regnum"] == car_number), None)
    
    if not user_car:
        if is_initial_check:
            await bot.send_message(user_id, f"❌ Не удалось найти автомобиль с номером `{car_number}` в очереди.")
        await db.remove_car(car_number)
        await bot.send_message(user_id, f"ℹ️ Автомобиль `{car_number}` больше не отслеживается (пропал из списка очереди).")
        return

    first_car_overall = queue[0] if queue else None
    first_waiting_car = None
    if first_car_overall and first_car_overall.get('status') == 3:
        first_waiting_car = next((car for car in queue if car.get("status") != 3), None)

    current_pos = user_car.get("order_id")
    current_status = user_car["status"]

    if is_initial_check:
        message_text = format_car_info(user_car, total_cars, first_car_overall, first_waiting_car)
        await bot.send_message(user_id, message_text)
        # Сохраняем и позицию для уведомлений, и статус
        await db.update_car_state(car_number, current_pos, current_status)
        return

    last_state = await db.get_car_state(car_number)
    if not last_state: return

    notified_pos = last_state.get("notified_pos")
    last_status = last_state.get("last_status")
    
    notification_text = ""
    should_send_notification = False

    # 1. Проверка на вызов в ПП (высший приоритет)
    if current_status == 3 and last_status != 3:
        message_on_call = format_car_info(user_car, total_cars)
        full_message = f"🚨 **ВНИМАНИЕ! ВЫЗВАН В ПП!** 🚨\n\n{message_on_call}"
        for _ in range(3):
            await bot.send_message(user_id, full_message)
        await db.remove_car(car_number)
        return

    # 2. Проверка на продвижение в очереди
    if current_pos is not None and notified_pos is not None:
        pos_change = notified_pos - current_pos
        
        # Определяем порог для текущей позиции
        threshold = 0
        if 100 < current_pos <= 500: threshold = 20
        elif 40 < current_pos <= 100: threshold = 15
        elif 20 <= current_pos <= 40: threshold = 10
        elif current_pos < 20: threshold = 3

        # Проверяем, достигнут ли порог
        if threshold > 0 and pos_change >= threshold:
            should_send_notification = True
            notification_text = f"🔔 Очередь продвинулась! Ваша позиция: **{current_pos}**."
        
        # Отдельная проверка для важной отметки в 20
        if notified_pos > 20 and current_pos <= 20:
            should_send_notification = True
            notification_text = f"🔔 Очередь продвинулась! Ваша позиция: **{current_pos}**."

        # Отдельная проверка для важной отметки в 50
        if notified_pos > 50 and current_pos <= 50:
            should_send_notification = True
            notification_text = f"🔔 Очередь продвинулась! Ваша позиция: **{current_pos}**."

        # Отдельная проверка для важной отметки в 110
        if notified_pos > 110 and current_pos <= 110:
            should_send_notification = True
            notification_text = f"🔔 Очередь продвинулась! Ваша позиция: **{current_pos}**."

    if should_send_notification:
        full_message = f"{notification_text}\n\n{format_car_info(user_car, total_cars, first_car_overall, first_waiting_car)}"
        await bot.send_message(user_id, full_message)
        # Обновляем и позицию, и статус
        await db.update_car_state(car_number, current_pos, current_status)
    else:
        # Если уведомление не отправлено, обновляем ТОЛЬКО статус
        if current_status != last_status:
            await db.update_car_status_only(car_number, current_status)


async def scheduled_job(bot: Bot):
    logger.info("Scheduler running a check...")
    all_tracked_cars = await db.get_all_tracked_cars()
    for user_id, car_number in all_tracked_cars:
        await check_and_notify_user(bot, user_id, car_number)