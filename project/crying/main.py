import asyncio
import logging

from aiogram import Bot, F, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommandScopeDefault, BotCommandScopeChat
from aiogram.webhook.aiohttp_server import setup_application, SimpleRequestHandler
from aiogram_admin import setup_admin_handlers
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fluent.runtime import FluentResourceLoader
from loguru import logger

from project.crying.apps.bot.commands.bot_commands import BaseCommands, AdminCommands, SuperAdminCommands
from project.crying.apps.bot.handlers import register_routers
from project.crying.apps.bot.middleware import UserMiddleware, L10nMiddleware
from project.crying.config.cli import CLIArgsSettings
from project.crying.config.config import Settings, LOCALES_DIR
from project.crying.config.logg_settings import init_logging, Level
from project.crying.db import init_db, close_db
from project.crying.db.models import ChannelForSubscription, User
from project.crying.db.utils.backup import making_backup


async def set_commands(bot: Bot, settings: Settings):
    """ Установка команд бота. """
    await bot.set_my_commands(BaseCommands, scope=BotCommandScopeDefault())
    for admin in settings.bot.admins:
        try:
            await bot.set_my_commands(AdminCommands, scope=BotCommandScopeChat(chat_id=admin))
        except TelegramBadRequest as e:
            logger.warning(f"Can't set admin commands for {admin}: {e}")
    for super_admin in settings.bot.super_admins:
        try:
            await bot.set_my_commands(SuperAdminCommands, scope=BotCommandScopeChat(chat_id=super_admin))
        except TelegramBadRequest as e:
            logger.warning(f"Can't set super admin commands for {super_admin}: {e}")


async def setup_routers(dp: Dispatcher, settings: Settings):
    """Регистрация обработчиков"""
    # Основные обработчики
    register_routers(dp)

    # Обработчики админки
    await setup_admin_handlers(
        dp=dp,
        admins=settings.bot.admins,
        super_admins=settings.bot.super_admins,
        SubsChat=ChannelForSubscription,
        User=User,
        admin_command="base_admin",
    )


def setup_middlewares(dp: Dispatcher, l10n_middleware: L10nMiddleware):
    """Регистрация middleware"""
    # dp.update.outer_middleware(ThrottlingMiddleware(ttl=0.5))
    user_middleware = UserMiddleware()
    dp.message.middleware(user_middleware)
    dp.callback_query.middleware(user_middleware)

    # Регистрация мидлвари i18n
    # dp.message.middleware(language_middleware)
    # dp.callback_query.middleware(language_middleware)

    # l10n_middleware = L10nMiddleware(
    #     loader=FluentResourceLoader(str(LOCALES_DIR / "{locale}")),
    #     default_locale="ru",
    #     locales=["en"],
    #     resource_ids=["common.ftl"]
    # )
    # logger.info("Загружены локали: " + ", ".join(l10n_middleware.locales))
    dp.message.middleware(l10n_middleware)
    dp.callback_query.middleware(l10n_middleware)


# Initializing and start Scheduler function
async def start_scheduler(l10n_middleware: L10nMiddleware):

    """Инициализация и запуск планировщика задач."""
    # Инициализация планировщика
    scheduler = AsyncIOScheduler()

    # Создание бекапа базы данных
    scheduler.add_job(making_backup, 'cron', hour=0, minute=0)

    # Запуск планировщика
    scheduler.start()


async def start_webhook(bot: Bot, dp: Dispatcher, settings: Settings):
    """Start webhook."""

    # Выключаем логи от aiohttp
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    # Установка вебхука
    await bot.set_webhook(
        certificate=settings.webhook.get_certfile(),
        url=settings.webhook.url,
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )

    # Создание запуска aiohttp
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(
        app, path=settings.webhook.path
    )
    # Конфигурация startup и shutdown процессов
    setup_application(app, dp)

    # Запуск aiohttp
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        host=settings.webhook.host,
        port=settings.webhook.port,
        ssl_context=settings.webhook.get_ssl_context(),
    )
    # web.run_app(app, host=config.webhook.host, port=config.webhook.port)
    await site.start()

    # Бесконечный цикл
    await asyncio.Event().wait()
    # todo L1 09.11.2022 1:32 taima: убрать этот костыль

def init_l10n():
    return L10nMiddleware(
        loader=FluentResourceLoader(str(LOCALES_DIR / "{locale}")),
        default_locale="ru",
        locales=["en"],
        resource_ids=["common.ftl"]
    )


async def main():
    # Парсинг аргументов командной строки
    cli_settings = CLIArgsSettings.parse_args()
    cli_settings.update_settings(Settings)
    cli_settings.log.stdout = Level.TRACE
    # cli_settings.log.file = Level.TRACE

    # Инициализация настроек
    settings = Settings()

    # Инициализация логирования
    init_logging(cli_settings.log)

    # Инициализация базы данных
    await init_db(settings.db)

    # Инициализация бота
    bot = Bot(token=settings.bot.token.get_secret_value(), parse_mode="html")
    storage = MemoryStorage()
    dp = Dispatcher(
        storage=storage,
        settings=settings
    )

    # Настройка фильтра только для приватных сообщений
    dp.message.filter(F.chat.type == "private")

    # Настройка роутеров обработчиков
    await setup_routers(dp, settings)

    # Инициализация мидлвари локализации
    l10n = init_l10n()

    # Настройка мидлварей
    setup_middlewares(dp, l10n)

    # Запуск планировщика
    await start_scheduler(l10n)

    # Установка команд бота
    await set_commands(bot, settings)

    # Запуск бота
    try:
        if not cli_settings.webhook:
            logger.info("Запуск бота в обычном режиме")
            await bot.delete_webhook()
            await dp.start_polling(
                bot,
                skip_updates=True,
                allowed_updates=dp.resolve_used_update_types(),
            )

        else:
            logger.info("Запуск бота в вебхук режиме")
            await start_webhook(bot, dp, settings)
    finally:
        await bot.session.close()
        await dp.storage.close()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())

