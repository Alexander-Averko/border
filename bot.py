# bot.py
import asyncio
import logging
import pytz

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from database import db
from handlers import router as main_router
from services import scheduled_job

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # Инициализация базы данных
    await db.initialize()
    logger.info("База данных инициализирована.")

    # Инициализация бота и диспетчера
    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()
    dp.include_router(main_router)

    # Настройка и запуск планировщика
    scheduler = AsyncIOScheduler(timezone=pytz.timezone(config.timezone))
    scheduler.add_job(scheduled_job, "interval", minutes=2, args=[bot])
    scheduler.start()
    logger.info("Планировщик запущен.")

    logger.info("Бот запускается...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()
        logger.info("Бот остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен вручную.")