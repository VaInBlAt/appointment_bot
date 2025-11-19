import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import settings
from handlers import calendar, doctor_search, profile, registration, schedule
 
async def main():
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        ParseMode='HTML',
        timeout=60)
    
    dp = Dispatcher()
    dp.include_router(schedule.router)
    dp.include_router(calendar.router)
    dp.include_router(doctor_search.router)
    dp.include_router(profile.router)
    dp.include_router(registration.router)


    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())  