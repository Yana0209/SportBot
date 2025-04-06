import asyncio
import logging
from aiogram import Bot, Dispatcher
from handlers import basic

# Налаштування логування
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = '8148863430:AAEpi1HspDwadF1_KqoToIQ3S-0JnyMzD48'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

dp.include_router(basic.router)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())