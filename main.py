import asyncio
import logging
import os

import discord
from discord.ext import commands, tasks


# ==========================================================
# НАСТРОЙКИ
# ==========================================================

# Токен бота берётся из переменной окружения
TOKEN = os.getenv("DISCORD_TOKEN")

# ID сервера
GUILD_ID = 1338880308514131998

# ID основного голосового канала
VOICE_CHANNEL_ID = 1548258709476474881


# ==========================================================
# ЛОГИРОВАНИЕ
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger("Bot")


# ==========================================================
# INTENTS
# ==========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.voice_states = True


# ==========================================================
# BOT
# ==========================================================

class Bot(commands.Bot):

    def __init__(self):

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

        # --------------------------------------------------
        # ID голосового канала, в котором бот находится
        # --------------------------------------------------

        self.last_voice_channel_id = None

        # --------------------------------------------------
        # Флаг запуска watchdog
        # --------------------------------------------------

        self.watchdog_started = False

    # ======================================================
    # SETUP HOOK
    # ======================================================

    async def setup_hook(self):

        logger.info(
            "[Bot] Выполняется setup_hook..."
        )

        # --------------------------------------------------
        # Загружаем Music Cog
        # --------------------------------------------------

        try:

            await self.load_extension(
                "cogs.music"
            )

            logger.info(
                "[Bot] ✅ Cog music успешно загружен."
            )

        except Exception as e:

            logger.exception(
                "[Bot] ❌ Ошибка загрузки cogs.music: %s",
                e
            )

        # --------------------------------------------------
        # Синхронизация slash-команд
        # --------------------------------------------------

        try:

            synced = await self.tree.sync()

            logger.info(
                "[Bot] ✅ Slash-команд синхронизировано: %s",
                len(synced)
            )

        except Exception as e:

            logger.exception(
                "[Bot] ❌ Ошибка синхронизации slash-команд: %s",
                e
            )

        # --------------------------------------------------
        # ВАЖНО
        #
        # Здесь event loop уже запущен.
        #
        # Поэтому tasks.loop можно запускать здесь.
        # --------------------------------------------------

        if not self.watchdog_started:

            self.voice_watchdog.start()

            self.watchdog_started = True

            logger.info(
                "[Voice] ✅ Voice watchdog запущен."
            )

    # ======================================================
    # READY
    # ======================================================

    async def on_ready(self):

        logger.info(
            "[Bot] ========================================"
        )

        logger.info(
            "[Bot] ✅ Бот авторизован:"
        )

        logger.info(
            "[Bot] %s (%s)",
            self.user,
            self.user.id
        )

        logger.info(
            "[Bot] ========================================"
        )

        # --------------------------------------------------
        # Получаем сервер
        # --------------------------------------------------

        guild = self.get_guild(
            GUILD_ID
        )

        if guild is None:

            logger.error(
                "[Bot] ❌ Сервер %s не найден.",
                GUILD_ID
            )

            return

        logger.info(
            "[Bot] Сервер найден: %s (%s)",
            guild.name,
            guild.id
        )

        # --------------------------------------------------
        # Получаем голосовой канал
        # --------------------------------------------------

        channel = guild.get_channel(
            VOICE_CHANNEL_ID
        )

        if channel is None:

            logger.error(
                "[Voice] ❌ Канал %s не найден.",
                VOICE_CHANNEL_ID
            )

            return

        # --------------------------------------------------
        # Проверяем тип канала
        # --------------------------------------------------

        logger.info(
            "[Voice] Тип канала: %s",
            type(channel).__name__
        )

        if not isinstance(
            channel,
            discord.VoiceChannel
        ):

            logger.error(
                "[Voice] ❌ Канал %s не является обычным голосовым каналом.",
                VOICE_CHANNEL_ID
            )

            return

        logger.info(
            "[Voice] Найден канал: %s (%s)",
            channel.name,
            channel.id
        )

        # --------------------------------------------------
        # Проверяем текущий VoiceClient
        # --------------------------------------------------

        voice_client = guild.voice_client

        if (
            voice_client is not None
            and voice_client.is_connected()
        ):

            logger.info(
                "[Voice] 🔊 Бот уже подключён к: %s",
                voice_client.channel.name
            )

            self.last_voice_channel_id = (
                voice_client.channel.id
            )

            return

        # --------------------------------------------------
        # Подключаемся
        # --------------------------------------------------

        await self.connect_to_main_channel(
            guild,
            channel
        )

    # ======================================================
    # ПОДКЛЮЧЕНИЕ К ОСНОВНОМУ КАНАЛУ
    # ======================================================

    async def connect_to_main_channel(
        self,
        guild: discord.Guild,
        channel: discord.VoiceChannel
    ):

        logger.info(
            "[Voice] ========================================"
        )

        logger.info(
            "[Voice] Попытка подключения к голосовому каналу"
        )

        logger.info(
            "[Voice] Guild: %s (%s)",
            guild.name,
            guild.id
        )

        logger.info(
            "[Voice] Channel: %s (%s)",
            channel.name,
            channel.id
        )

        # --------------------------------------------------
        # Проверяем участника бота
        # --------------------------------------------------

        if guild.me is None:

            logger.error(
                "[Voice] ❌ guild.me == None"
            )

            return

        # --------------------------------------------------
        # Проверяем права
        # --------------------------------------------------

        permissions = channel.permissions_for(
            guild.me
        )

        logger.info(
            "[Voice] Права бота:"
        )

        logger.info(
            "[Voice] View Channel = %s",
            permissions.view_channel
        )

        logger.info(
            "[Voice] Connect = %s",
            permissions.connect
        )

        logger.info(
            "[Voice] Speak = %s",
            permissions.speak
        )

        # --------------------------------------------------
        # View Channel
        # --------------------------------------------------

        if not permissions.view_channel:

            logger.error(
                "[Voice] ❌ У бота нет права View Channel."
            )

            return

        # --------------------------------------------------
        # Connect
        # --------------------------------------------------

        if not permissions.connect:

            logger.error(
                "[Voice] ❌ У бота нет права Connect."
            )

            return

        # --------------------------------------------------
        # Получаем существующий VoiceClient
        # --------------------------------------------------

        voice_client = guild.voice_client

        # --------------------------------------------------
        # Если уже подключён
        # --------------------------------------------------

        if (
            voice_client is not None
            and voice_client.is_connected()
        ):

            # --------------------------------------------------
            # Бот уже в основном канале
            # --------------------------------------------------

            if voice_client.channel.id == channel.id:

                self.last_voice_channel_id = (
                    channel.id
                )

                logger.info(
                    "[Voice] ✅ Бот уже находится в основном канале."
                )

                return

            # --------------------------------------------------
            # Бот находится в другом канале.
            #
            # НЕ возвращаем его обратно.
            #
            # Значит, пользователь его перетащил.
            # --------------------------------------------------

            self.last_voice_channel_id = (
                voice_client.channel.id
            )

            logger.info(
                "[Voice] 🔄 Бот находится в другом канале: %s",
                voice_client.channel.name
            )

            logger.info(
                "[Voice] Бот остаётся в этом канале."
            )

            return

        # --------------------------------------------------
        # Если остался старый VoiceClient
        # --------------------------------------------------

        if voice_client is not None:

            logger.warning(
                "[Voice] ⚠️ Обнаружен неактивный VoiceClient."
            )

            try:

                await voice_client.disconnect(
                    force=True
                )

            except Exception as e:

                logger.warning(
                    "[Voice] Не удалось закрыть старый VoiceClient: %s",
                    e
                )

            await asyncio.sleep(1)

        # --------------------------------------------------
        # Подключаемся
        # --------------------------------------------------

        try:

            logger.info(
                "[Voice] 🔊 Выполняю channel.connect()..."
            )

            voice_client = await channel.connect(
                timeout=30,
                reconnect=True
            )

            # --------------------------------------------------
            # Запоминаем канал
            # --------------------------------------------------

            self.last_voice_channel_id = (
                channel.id
            )

            logger.info(
                "[Voice] ========================================"
            )

            logger.info(
                "[Voice] ✅ УСПЕШНО ПОДКЛЮЧЁН К VOICE!"
            )

            logger.info(
                "[Voice] Канал: %s",
                voice_client.channel.name
            )

            logger.info(
                "[Voice] ID: %s",
                voice_client.channel.id
            )

            logger.info(
                "[Voice] ========================================"
            )

        except asyncio.TimeoutError:

            logger.error(
                "[Voice] ❌ Таймаут подключения к Discord Voice."
            )

        except discord.Forbidden as e:

            logger.error(
                "[Voice] ❌ Discord Forbidden: %s",
                e
            )

            logger.error(
                "[Voice] Проверь права Connect / View Channel."
            )

        except discord.ClientException as e:

            logger.error(
                "[Voice] ❌ Discord ClientException: %s",
                e
            )

        except Exception as e:

            logger.exception(
                "[Voice] ❌ Ошибка подключения к Voice: %s",
                e
            )

        logger.info(
            "[Voice] ========================================"
        )

    # ======================================================
    # VOICE STATE UPDATE
    # ======================================================

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):

        # --------------------------------------------------
        # Нас интересует только сам бот
        # --------------------------------------------------

        if self.user is None:

            return

        if member.id != self.user.id:

            return

        # --------------------------------------------------
        # БОТА ПОЛНОСТЬЮ ОТКЛЮЧИЛИ ОТ VOICE
        # --------------------------------------------------

        if (
            before.channel is not None
            and after.channel is None
        ):

            logger.warning(
                "[Voice] ⚠️ БОТ ОТКЛЮЧЁН ИЗ VOICE!"
            )

            logger.warning(
                "[Voice] Предыдущий канал: %s (%s)",
                before.channel.name,
                before.channel.id
            )

            # --------------------------------------------------
            # Небольшая задержка.
            #
            # Это позволяет Discord завершить
            # старое voice-соединение.
            # --------------------------------------------------

            await asyncio.sleep(2)

            # --------------------------------------------------
            # Получаем сервер
            # --------------------------------------------------

            guild = member.guild

            # --------------------------------------------------
            # Проверяем, не подключился ли бот уже сам
            # --------------------------------------------------

            voice_client = guild.voice_client

            if (
                voice_client is not None
                and voice_client.is_connected()
            ):

                logger.info(
                    "[Voice] Бот уже снова подключён."
                )

                self.last_voice_channel_id = (
                    voice_client.channel.id
                )

                return

            # --------------------------------------------------
            # Основной канал
            # --------------------------------------------------

            channel = guild.get_channel(
                VOICE_CHANNEL_ID
            )

            if channel is None:

                logger.error(
                    "[Voice] ❌ Основной голосовой канал не найден."
                )

                return

            # --------------------------------------------------
            # Возвращаемся
            # --------------------------------------------------

            logger.info(
                "[Voice] 🔙 Возвращаю бота в основной канал."
            )

            await self.connect_to_main_channel(
                guild,
                channel
            )

            return

        # ==================================================
        # БОТА ПЕРЕТАЩИЛИ В ДРУГОЙ КАНАЛ
        # ==================================================

        if (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        ):

            logger.info(
                "[Voice] 🔄 Бот перемещён:"
            )

            logger.info(
                "[Voice] %s (%s) -> %s (%s)",
                before.channel.name,
                before.channel.id,
                after.channel.name,
                after.channel.id
            )

            # --------------------------------------------------
            # Запоминаем новое положение
            # --------------------------------------------------

            self.last_voice_channel_id = (
                after.channel.id
            )

            logger.info(
                "[Voice] Бот остаётся в новом канале."
            )

    # ======================================================
    # VOICE WATCHDOG
    # ======================================================

    @tasks.loop(seconds=15)
    async def voice_watchdog(self):

        # --------------------------------------------------
        # Проверяем готовность
        # --------------------------------------------------

        if not self.is_ready():

            return

        # --------------------------------------------------
        # Получаем сервер
        # --------------------------------------------------

        guild = self.get_guild(
            GUILD_ID
        )

        if guild is None:

            logger.warning(
                "[Voice] Сервер ещё не найден."
            )

            return

        # --------------------------------------------------
        # Получаем VoiceClient
        # --------------------------------------------------

        voice_client = guild.voice_client

        # --------------------------------------------------
        # Бот не подключён
        # --------------------------------------------------

        if (
            voice_client is None
            or not voice_client.is_connected()
        ):

            logger.warning(
                "[Voice] ⚠️ Бот не подключён к голосовому каналу."
            )

            # --------------------------------------------------
            # Получаем основной канал
            # --------------------------------------------------

            channel = guild.get_channel(
                VOICE_CHANNEL_ID
            )

            if channel is None:

                logger.error(
                    "[Voice] ❌ Основной канал не найден."
                )

                return

            # --------------------------------------------------
            # Пытаемся подключиться
            # --------------------------------------------------

            await self.connect_to_main_channel(
                guild,
                channel
            )

            return

        # --------------------------------------------------
        # Бот подключён.
        #
        # НЕ проверяем, находится ли он именно
        # в VOICE_CHANNEL_ID.
        #
        # Пользователь может перетащить его куда угодно.
        # --------------------------------------------------

        self.last_voice_channel_id = (
            voice_client.channel.id
        )

    # ======================================================
    # WATCHDOG BEFORE LOOP
    # ======================================================

    @voice_watchdog.before_loop
    async def before_voice_watchdog(self):

        await self.wait_until_ready()

        logger.info(
            "[Voice] Watchdog готов к работе."
        )


# ==========================================================
# СОЗДАЁМ BOT
# ==========================================================

bot = Bot()


# ==========================================================
# ПРОВЕРКА TOKEN
# ==========================================================

if not TOKEN:

    raise RuntimeError(
        "Переменная окружения DISCORD_TOKEN не задана."
    )


# ==========================================================
# ЗАПУСК
# ==========================================================

bot.run(TOKEN)
