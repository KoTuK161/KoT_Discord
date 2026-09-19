import asyncio
import logging
import os

import discord
from discord.ext import commands, tasks


# ==========================================================
# НАСТРОЙКИ
# ==========================================================

# Discord Bot Token
TOKEN = os.getenv("DISCORD_TOKEN")

# Сервер
GUILD_ID = 1338880308514131998

# Основной голосовой канал
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
        # Флаг запуска
        # --------------------------------------------------

        self.ready_once = False

        # --------------------------------------------------
        # Запоминаем голосовой канал,
        # в котором бот находится
        #
        # Это позволяет понять:
        #
        # бот был перетащен
        # или
        # бот был отключён
        # --------------------------------------------------

        self.last_voice_channel_id = None

        # --------------------------------------------------
        # Запускаем проверку голосового соединения
        # --------------------------------------------------

        self.voice_watchdog.start()

    # ======================================================
    # SETUP HOOK
    # ======================================================

    async def setup_hook(self):

        # --------------------------------------------------
        # Загружаем Music Cog
        # --------------------------------------------------

        try:

            await self.load_extension(
                "cogs.music"
            )

            logger.info(
                "[Bot] Cog Music успешно загружен."
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
                "[Bot] Slash-команд синхронизировано: %s",
                len(synced)
            )

        except Exception as e:

            logger.exception(
                "[Bot] ❌ Ошибка синхронизации команд: %s",
                e
            )

    # ======================================================
    # READY
    # ======================================================

    async def on_ready(self):

        logger.info(
            "[Bot] ✅ Авторизован как %s (%s)",
            self.user,
            self.user.id
        )

        # --------------------------------------------------
        # Не выполняем повторную инициализацию
        # --------------------------------------------------

        if self.ready_once:

            logger.info(
                "[Bot] Повторное подключение."
            )

        else:

            self.ready_once = True

            logger.info(
                "[Bot] Первый запуск."
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
            "[Bot] Сервер: %s (%s)",
            guild.name,
            guild.id
        )

        # --------------------------------------------------
        # Проверяем основной голосовой канал
        # --------------------------------------------------

        channel = guild.get_channel(
            VOICE_CHANNEL_ID
        )

        if channel is None:

            logger.error(
                "[Bot] ❌ Голосовой канал %s не найден.",
                VOICE_CHANNEL_ID
            )

            return

        if not isinstance(
            channel,
            discord.VoiceChannel
        ):

            logger.error(
                "[Bot] ❌ Канал %s не является голосовым.",
                VOICE_CHANNEL_ID
            )

            return

        # --------------------------------------------------
        # Проверяем текущее подключение
        # --------------------------------------------------

        voice_client = guild.voice_client

        if (
            voice_client is not None
            and voice_client.is_connected()
        ):

            logger.info(
                "[Voice] Уже подключён к: %s",
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
    # ПОДКЛЮЧЕНИЕ К ГОЛОСОВОМУ КАНАЛУ
    # ======================================================

    async def connect_to_main_channel(
        self,
        guild: discord.Guild,
        channel: discord.VoiceChannel
    ):

        try:

            voice_client = guild.voice_client

            # --------------------------------------------------
            # Уже подключён
            # --------------------------------------------------

            if (
                voice_client is not None
                and voice_client.is_connected()
            ):

                # Если уже в нужном канале
                if voice_client.channel.id == channel.id:

                    self.last_voice_channel_id = (
                        channel.id
                    )

                    return

                # --------------------------------------------------
                # Если находится в другом канале,
                # НЕ перетаскиваем обратно.
                #
                # Пользователь имеет право перемещать бота.
                # --------------------------------------------------

                logger.info(
                    "[Voice] Бот находится в другом канале: %s",
                    voice_client.channel.name
                )

                self.last_voice_channel_id = (
                    voice_client.channel.id
                )

                return

            # --------------------------------------------------
            # Подключаемся
            # --------------------------------------------------

            logger.info(
                "[Voice] Подключение к: %s",
                channel.name
            )

            voice_client = await channel.connect(
                reconnect=True
            )

            self.last_voice_channel_id = (
                channel.id
            )

            logger.info(
                "[Voice] ✅ Подключён к: %s",
                channel.name
            )

        except asyncio.CancelledError:

            raise

        except Exception as e:

            logger.exception(
                "[Voice] ❌ Ошибка подключения: %s",
                e
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
        # Бот был отключён от голосового канала
        # --------------------------------------------------

        if (
            before.channel is not None
            and after.channel is None
        ):

            logger.warning(
                "[Voice] ⚠️ Бот отключён из канала: %s",
                before.channel.name
            )

            # Небольшая задержка.
            #
            # Discord иногда присылает несколько
            # voice state событий подряд.
            await asyncio.sleep(2)

            guild = member.guild

            channel = guild.get_channel(
                VOICE_CHANNEL_ID
            )

            if channel is None:

                logger.error(
                    "[Voice] ❌ Основной канал не найден."
                )

                return

            await self.connect_to_main_channel(
                guild,
                channel
            )

            return

        # --------------------------------------------------
        # Бота переместили в другой канал
        # --------------------------------------------------

        if (
            before.channel is not None
            and after.channel is not None
            and before.channel.id != after.channel.id
        ):

            logger.info(
                "[Voice] 🔄 Бот перемещён: "
                "%s -> %s",
                before.channel.name,
                after.channel.name
            )

            # --------------------------------------------------
            # Запоминаем новое положение.
            #
            # Бот остаётся там, куда его перетащили.
            # --------------------------------------------------

            self.last_voice_channel_id = (
                after.channel.id
            )

    # ======================================================
    # WATCHDOG
    # ======================================================

    @tasks.loop(seconds=15)
    async def voice_watchdog(self):

        # --------------------------------------------------
        # Бот ещё не готов
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

            return

        # --------------------------------------------------
        # VoiceClient
        # --------------------------------------------------

        voice_client = guild.voice_client

        # --------------------------------------------------
        # Бот полностью отключён
        # --------------------------------------------------

        if (
            voice_client is None
            or not voice_client.is_connected()
        ):

            logger.warning(
                "[Voice] ⚠️ Бот не подключён к голосовому каналу."
            )

            channel = guild.get_channel(
                VOICE_CHANNEL_ID
            )

            if channel is None:

                logger.error(
                    "[Voice] ❌ Основной канал не найден."
                )

                return

            await self.connect_to_main_channel(
                guild,
                channel
            )

            return

        # --------------------------------------------------
        # Бот находится в каком-то голосовом канале
        # --------------------------------------------------

        current_channel = voice_client.channel

        self.last_voice_channel_id = (
            current_channel.id
        )

    # ======================================================
    # WAIT UNTIL READY
    # ======================================================

    @voice_watchdog.before_loop
    async def before_voice_watchdog(self):

        await self.wait_until_ready()


# ==========================================================
# ЗАПУСК
# ==========================================================

bot = Bot()


if not TOKEN:

    raise RuntimeError(
        "Переменная окружения DISCORD_TOKEN не задана."
    )


bot.run(TOKEN)
