import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from .config import BOT_TOKEN
from .handlers import user_router, admin_router


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin_router)
    dp.include_router(user_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())