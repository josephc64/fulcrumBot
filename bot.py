"""
Original Repository (Version: 6.1.0) Copyright © Krypton 2019-2023 - https://github.com/kkrypt0nn (https://krypton.ninja)
"""

import json, logging, os, platform, random, sys, aiosqlite, discord, csv, re, datetime
from plexapi.server import PlexServer
from discord.ext import commands, tasks
from discord.ext.commands import Context
from dotenv import load_dotenv

from database import DatabaseManager

if not os.path.isfile(f"{os.path.realpath(os.path.dirname(__file__))}/config.json"):
    sys.exit("'config.json' not found! Please add it and try again.")
else:
    with open(f"{os.path.realpath(os.path.dirname(__file__))}/config.json") as file:
        config = json.load(file)


intents = discord.Intents.default()

"""
Uncomment this if you want to use prefix (normal) commands.
It is recommended to use slash commands and therefore not use prefix commands.

If you want to use prefix commands, make sure to also enable the intent below in the Discord developer portal.
"""
intents.message_content = True

# Setup both of the loggers
class LoggingFormatter(logging.Formatter):
    # Colors
    black = "\x1b[30m"
    red = "\x1b[31m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    blue = "\x1b[34m"
    gray = "\x1b[38m"
    # Styles
    reset = "\x1b[0m"
    bold = "\x1b[1m"

    COLORS = {
        logging.DEBUG: gray + bold,
        logging.INFO: blue + bold,
        logging.WARNING: yellow + bold,
        logging.ERROR: red,
        logging.CRITICAL: red + bold,
    }

    def format(self, record):
        log_color = self.COLORS[record.levelno]
        format = "(black){asctime}(reset) (levelcolor){levelname:<8}(reset) (green){name}(reset) {message}"
        format = format.replace("(black)", self.black + self.bold)
        format = format.replace("(reset)", self.reset)
        format = format.replace("(levelcolor)", log_color)
        format = format.replace("(green)", self.green + self.bold)
        formatter = logging.Formatter(format, "%Y-%m-%d %H:%M:%S", style="{")
        return formatter.format(record)


logger = logging.getLogger("discord_bot")
logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(LoggingFormatter())
# File handler
file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
file_handler_formatter = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}", "%Y-%m-%d %H:%M:%S", style="{"
)
file_handler.setFormatter(file_handler_formatter)

# Add the handlers
logger.addHandler(console_handler)
logger.addHandler(file_handler)


class DiscordBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or(config["prefix"]),
            intents=intents,
            help_command=None,
        )
        """
        This creates custom bot variables so that we can access these variables in cogs more easily.

        For example, The config is available using the following code:
        - self.config # In this class
        - bot.config # In this file
        - self.bot.config # In cogs
        """
        self.logger = logger
        self.config = config
        self.database = None

    async def init_db(self) -> None:
        async with aiosqlite.connect(
            f"{os.path.realpath(os.path.dirname(__file__))}/database/database.db"
        ) as db:
            with open(
                f"{os.path.realpath(os.path.dirname(__file__))}/database/schema.sql"
            ) as file:
                await db.executescript(file.read())
            await db.commit()

    async def load_cogs(self) -> None:
        """
        The code in this function is executed whenever the bot will start.
        """
        for file in os.listdir(f"{os.path.realpath(os.path.dirname(__file__))}/cogs"):
            if file.endswith(".py"):
                extension = file[:-3]
                try:
                    await self.load_extension(f"cogs.{extension}")
                    self.logger.info(f"Loaded extension '{extension}'")
                except Exception as e:
                    exception = f"{type(e).__name__}: {e}"
                    self.logger.error(
                        f"Failed to load extension {extension}\n{exception}"
                    )

    @tasks.loop(minutes=1.0)
    async def plex_log(self) -> None:
        """
        Checks the date of the last Plex log, and makes another one if appropriate.
        """
        bigString = ""

        def format_numbers(arr):
            if not arr: return ""
            result = []
            start = arr[0]
            end = arr[0]
            for num in arr[1:]:
                if num == end + 1: end = num
                else:
                    if start == end: result.append(f"{start:02d}")
                    else: result.append(f"{start:02d}-{end:02d}")
                    start = num
                    end = num
            if start == end: result.append(f"{start:02d}")
            else: result.append(f"{start:02d}-{end:02d}")
            return ", ".join(result)

        dateFile = open('plexDate.txt', 'r')
        logDate = datetime.datetime.strptime(dateFile.read(), "%Y-%m-%d")
        dateFile.close()

        nowDate = datetime.datetime.now().strftime("%Y-%m-%d")
        dateDiff = datetime.datetime.strptime(nowDate, "%Y-%m-%d") - logDate


        if(dateDiff.days >= 7):
            baseurl = os.getenv("PLEX_URL")
            token = os.getenv("PLEX_TOKEN")
            plex = PlexServer(baseurl, token)
            movies = plex.library.section('Movies')
            series = plex.library.section('Series')
            allItems = [*movies.search(), *series.search()]

            bigString += "```\n"
            bigString += f"FULCRUM Automated Changelog // {logDate.strftime('%Y/%m/%d')} - {datetime.datetime.now().strftime('%Y/%m/%d')}\n\n"
            bigString += "Movies\n------\n"
            for m in movies.search():
                if (m.addedAt > logDate):
                    if (m.editionTitle == None):
                        bigString += f" + {m.title} ({m.year})\n"
                    else:
                        bigString += f" + {m.title} ({m.year}) - {m.editionTitle}\n"

            bigString += "\nShows\n-----\n"
            for s in series.search():
                if (s.addedAt > logDate):
                    showEpisodes = {}
                    for e in series.get(s.title).episodes():
                        for part in e.iterParts():
                            regexPattern = r"[sS](\d{1,4})[eE](\d{1,4})"
                            epTitle = re.search(regexPattern, part.file, re.IGNORECASE)
                            if epTitle:
                                season = epTitle.group(1)
                                episode = epTitle.group(2)
                                
                                if season not in showEpisodes:
                                    showEpisodes[season] = []
                                
                                if int(episode) not in showEpisodes[season]:
                                    showEpisodes[season].append(int(episode))
                                    
                    bigString += f" o {s.title} ({s.year})\n"
                    for season in showEpisodes:
                        bigString += f"    + S{season}E{format_numbers(showEpisodes[season])}\n"
            bigString += "```"

            dateFile = open('plexDate.txt', 'w')
            dateFile.write(nowDate)
            dateFile.close()

            channel = bot.get_channel(1223505800706789378)
            await channel.send(bigString)


    @plex_log.before_loop
    async def before_plex_log(self) -> None:
        """
        Before starting the status changing task, we make sure the bot is ready
        """
        await self.wait_until_ready()

    @tasks.loop(minutes=1.0)
    async def status_task(self) -> None:
        """
        Setup the game status task of the bot.
        """
        statuses = ["watching Plex", "gaming", "shmillin"]
        await self.change_presence(activity=discord.Game(random.choice(statuses)))

    @status_task.before_loop
    async def before_status_task(self) -> None:
        """
        Before starting the status changing task, we make sure the bot is ready
        """
        await self.wait_until_ready()

    async def setup_hook(self) -> None:
        """
        This will just be executed when the bot starts the first time.
        """
        self.logger.info(f"Logged in as {self.user.name}")
        self.logger.info(f"discord.py API version: {discord.__version__}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(
            f"Running on: {platform.system()} {platform.release()} ({os.name})"
        )
        self.logger.info("-------------------")
        await self.init_db()
        await self.load_cogs()
        self.status_task.start()
        self.plex_log.start()
        self.database = DatabaseManager(
            connection=await aiosqlite.connect(
                f"{os.path.realpath(os.path.dirname(__file__))}/database/database.db"
            )
        )

    async def on_message(self, message: discord.Message) -> None:
        """
        The code in this event is executed every time someone sends a message, with or without the prefix

        :param message: The message that was sent.
        """
        if message.author == self.user or message.author.bot:
            return
        await self.process_commands(message)

    async def on_command_completion(self, context: Context) -> None:
        """
        The code in this event is executed every time a normal command has been *successfully* executed.

        :param context: The context of the command that has been executed.
        """
        full_command_name = context.command.qualified_name
        split = full_command_name.split(" ")
        executed_command = str(split[0])
        if context.guild is not None:
            self.logger.info(
                f"Executed {executed_command} command in {context.guild.name} (ID: {context.guild.id}) by {context.author} (ID: {context.author.id})"
            )
        else:
            self.logger.info(
                f"Executed {executed_command} command by {context.author} (ID: {context.author.id}) in DMs"
            )

    async def on_command_error(self, context: Context, error) -> None:
        """
        The code in this event is executed every time a normal valid command catches an error.

        :param context: The context of the normal command that failed executing.
        :param error: The error that has been faced.
        """
        if isinstance(error, commands.CommandOnCooldown):
            minutes, seconds = divmod(error.retry_after, 60)
            hours, minutes = divmod(minutes, 60)
            hours = hours % 24
            embed = discord.Embed(
                description=f"**Please slow down** - You can use this command again in {f'{round(hours)} hours' if round(hours) > 0 else ''} {f'{round(minutes)} minutes' if round(minutes) > 0 else ''} {f'{round(seconds)} seconds' if round(seconds) > 0 else ''}.",
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                description="You are not the owner of the bot!", color=0xE02B2B
            )
            await context.send(embed=embed)
            if context.guild:
                self.logger.warning(
                    f"{context.author} (ID: {context.author.id}) tried to execute an owner only command in the guild {context.guild.name} (ID: {context.guild.id}), but the user is not an owner of the bot."
                )
            else:
                self.logger.warning(
                    f"{context.author} (ID: {context.author.id}) tried to execute an owner only command in the bot's DMs, but the user is not an owner of the bot."
                )
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                description="You are missing the permission(s) `"
                + ", ".join(error.missing_permissions)
                + "` to execute this command!",
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                description="I am missing the permission(s) `"
                + ", ".join(error.missing_permissions)
                + "` to fully perform this command!",
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="Error!",
                # We need to capitalize because the command arguments have no capital letter in the code and they are the first word in the error message.
                description=str(error).capitalize(),
                color=0xE02B2B,
            )
            await context.send(embed=embed)
        else:
            raise error


load_dotenv()

bot = DiscordBot()
bot.run(os.getenv("TOKEN"))
