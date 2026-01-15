from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from pathlib import Path

from kintsugi_learn_tgbot.config import ConfigurationManager

config = ConfigurationManager(Path("botconfig.toml")).config

bot = Bot(token=config.TOKEN)
dp = Dispatcher(storage=MemoryStorage())
