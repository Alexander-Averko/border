# keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает Reply-клавиатуру с основными командами.
    """
    buttons = [
        [
            KeyboardButton(text="🚗 Мои авто"),
            KeyboardButton(text="✅ Добавить авто")
        ],
        [
            KeyboardButton(text="❌ Удалить все авто")
        ]
    ]
    # resize_keyboard=True делает кнопки более компактными
    # one_time_keyboard=False оставляет клавиатуру видимой после нажатия
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )