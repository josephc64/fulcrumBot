"""
Original Repository (Version: 6.1.0) Copyright © Krypton 2019-2023 - https://github.com/kkrypt0nn (https://krypton.ninja)
"""

import json, logging, os, platform, random, sys, aiosqlite, discord, csv, re, datetime, time, asyncio
from datetime import datetime, timedelta
from plexapi.server import PlexServer
from discord.ext import commands, tasks
from discord.ext.commands import Context
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Playwright

from database import DatabaseManager

if not os.path.isfile(f"{os.path.realpath(os.path.dirname(__file__))}/config.json"):
    sys.exit("'config.json' not found! Please add it and try again.")
else:
    with open(f"{os.path.realpath(os.path.dirname(__file__))}/config.json") as file:
        config = json.load(file)


intents = discord.Intents.default()

# This enables traditional prefix commands to work
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
        
        # This creates custom bot variables so that we can access these variables in cogs more easily.
        # For example, The config is available using the following code:
            # self.config # In this class
            # bot.config # In this file
            # self.bot.config # In cogs

        self.logger = logger
        self.config = config
        self.database = None


    # Initialize the database
    async def init_db(self) -> None:
        async with aiosqlite.connect(
            f"{os.path.realpath(os.path.dirname(__file__))}/database/database.db"
        ) as db:
            with open(
                f"{os.path.realpath(os.path.dirname(__file__))}/database/schema.sql"
            ) as file:
                await db.executescript(file.read())
            await db.commit()


    # This code is run during bot startup, and loads all cogs
    async def load_cogs(self) -> None:
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

    
    # Keep game library threads active
    @tasks.loop(minutes=1.0)
    async def games_active(self) -> None:
        print("Sorting task activated. 120 seconds to sort.")
        await asyncio.sleep(120)
        games = (bot.get_channel(1229215621875630151)).threads

        gameDict = {}
        for t in games:
            if t.name != "Game Library Index":
                gameDict[t.name] = t.id
        sortDict = {key: gameDict[key] for key in sorted(gameDict)}
        
        idListOrdered = list(sortDict.values())
        revListOrdered = reversed(idListOrdered)

        idListOrig = list(gameDict.values())
        
        with open('gameDate.txt', 'r') as dateFile:
            logDate = datetime.strptime(dateFile.read().strip(), "%Y-%m-%d")

        nowDate = datetime.now().strftime("%Y-%m-%d")
        dateDiff = datetime.strptime(nowDate, "%Y-%m-%d") - logDate

        if(gameDict != sortDict) or (dateDiff.days >=2):
            print("Sort condition met.")
            await asyncio.sleep(28)
            for id in revListOrdered:
                print(f"Sorting {id}")
                await asyncio.sleep(28)
                message = await (bot.get_channel(id)).send("Just checking to see if this thread is still active!")
                await asyncio.sleep(28)
                await message.delete()
                await (bot.get_channel(id)).edit(archived=False, auto_archive_duration=10080)
        
                newTime = (datetime.strptime(nowDate, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        
                with open('gameDate.txt', 'w') as dateFile:
                    dateFile.write(newTime)
        else:
            print("Sort condition not met.")


    # Keep game library threads active
    @tasks.loop(minutes=1.0)
    async def vid_stream(self) -> None:

        with open('schedule.csv', newline='') as schedFile:
            sched = csv.reader(schedFile, delimiter=' ', quotechar='|')
            nowDate = datetime.now()
            for row in sched:
                itemTime = (str(row[0]).split(",")[0]) + " " + (str(row[0]).split(",")[1])
                itemTime = datetime.strptime(itemTime, "%Y-%m-%d %H:%M:%S")
                itemCode = str(row[0]).split(",")[2]

                if(nowDate >= itemTime):
                    print("It's time!")
                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=False)
                        page = await browser.new_page()
                        await page.goto("http://www.youtube.com")
                        print(await page.title())
                        await page.pause()
                else:
                    print("It's not time yet!")


    # Check the date of the last Plex log, sending another one if enough time has passed.
    @tasks.loop(minutes=1.0)
    async def plex_log(self) -> None:
        bigString = ""

        def format_numbers(arr):
            if not arr: return ""
            
            result = []
            start = arr[0]
            end = arr[0]

            for num in arr[1:]:
                if num == end + 1:
                    end = num
                else:
                    if start == end:
                        result.append(f"{start:02d}")
                    else:
                        result.append(f"{start:02d}-{end:02d}")
                    start = num
                    end = num
            if start == end:
                result.append(f"{start:02d}")
            else:
                result.append(f"{start:02d}-{end:02d}")
            return ", ".join(result)

        # Read the last log date
        with open('plexDate.txt', 'r') as dateFile:
            logDate = datetime.strptime(dateFile.read().strip(), "%Y-%m-%d")

        nowDate = datetime.now().strftime("%Y-%m-%d")
        dateDiff = datetime.strptime(nowDate, "%Y-%m-%d") - logDate

        if dateDiff.days > 6:
            baseurl = os.getenv("PLEX_URL")
            token = os.getenv("PLEX_TOKEN")
            plex = PlexServer(baseurl, token)
            movies = plex.library.section('Movies')
            series = plex.library.section('Series')

            bigString += "```\n"
            bigString += f"FULCRUM Automated Changelog // {logDate.strftime('%Y/%m/%d')} - {datetime.now().strftime('%Y/%m/%d')}\n\n"
            bigString += "Movies\n------\n"
            for m in movies.search():
                if m.addedAt >= logDate:
                    if m.editionTitle is None:
                        bigString += f" + {m.title} ({m.year})\n"
                    else:
                        bigString += f" + {m.title} ({m.year}) - {m.editionTitle}\n"

            bigString += "\nShows\n-----\n"
            for s in series.search():
                showEpisodes = {}
                for e in s.episodes():
                    if e.addedAt >= logDate:
                        regexPattern = r"[sS](\d{1,4})[eE](\d{1,4})"
                        epTitle = re.search(regexPattern, e.locations[0], re.IGNORECASE)
                        if epTitle:
                            season = epTitle.group(1)
                            episode = epTitle.group(2)
                            
                            if season not in showEpisodes:
                                showEpisodes[season] = []
                            
                            if int(episode) not in showEpisodes[season]:
                                showEpisodes[season].append(int(episode))
                                
                if showEpisodes:
                    bigString += f" o {s.title} ({s.year})\n"
                    for season in sorted(showEpisodes.keys(), key=int):
                        bigString += f"    + S{season}E{format_numbers(sorted(showEpisodes[season]))}\n"

            bigString += "\nGames\n-----\n"
            gameCh = bot.get_channel(1229215621875630151)
            games = gameCh.threads
            gSort = []

            for g in games:
                if (((g.created_at).strftime('%Y/%m/%d') > logDate.strftime('%Y/%m/%d')) and (g.name != "Game Library Index")):
                    gSort.append(g.name)
                    gSort.sort()  
            for g2 in gSort: bigString += f" + {g2}\n"

            bigString += "```"

            newTime = (datetime.strptime(nowDate, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


            with open('plexDate.txt', 'w') as dateFile:
                dateFile.write(newTime)

            channel = bot.get_channel(1223505800706789378)
            await channel.send(bigString)
            #print(bigString)

    # Task to change bot status every minute
    @tasks.loop(minutes=1.0)
    async def status_task(self) -> None:
        statuses = ["Plex", "Team Fortress 2", "games", "Minecraft", "Mario Kart",
                    "Super Smash Bros.", "your mom", "Beeny", "Super Nintendo",
                    "Dreamcast", "GameCube", "Wii U", "PS1 games", "PS2 games",
                    "Toonami", "with dogs", "with Banjo", "the market", "chance",
                    "with rats", "with illegal fireworks"]
        await self.change_presence(activity=discord.Game(random.choice(statuses)))

    ### Necessary pre-checks to prevent loops from beginning before bot is ready ###

    # Pre-check for Plex logger
    @plex_log.before_loop
    async def before_plex_log(self) -> None:
        await self.wait_until_ready()

    # Pre-check for status loop
    @status_task.before_loop
    async def before_status_task(self) -> None:
        await self.wait_until_ready()

    # Pre-check for keeping threads active
    @games_active.before_loop
    async def before_games_active(self) -> None:
        await self.wait_until_ready()

    # Pre-check for video stream scheduling
    #@vid_stream.before_loop
    #async def before_vid_stream(self) -> None:
    #    await self.wait_until_ready()


    ### Startup sequence that runs whenever the bot boots ###
    async def setup_hook(self) -> None:
        self.logger.info(f"Logged in as {self.user.name}")
        self.logger.info(f"discord.py API version: {discord.__version__}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(f"Running on: {platform.system()} {platform.release()} ({os.name})")
        self.logger.info("-------------------")

        # Initialize databse and cogs
        await self.init_db()
        await self.load_cogs()

        # Initialize task loops
        self.status_task.start()
        self.plex_log.start()
        self.games_active.start()
        #self.vid_stream.start()

        # Start the database
        self.database = DatabaseManager(
            connection=await aiosqlite.connect(
                f"{os.path.realpath(os.path.dirname(__file__))}/database/database.db"
            )
        )

    # This code is run any time someone sends any message
    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user or message.author.bot: return
        await self.process_commands(message)

    # This code is run every time a command is successfully executed
    async def on_command_completion(self, context: Context) -> None:
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


    # This code is run every time a command errors out
    async def on_command_error(self, context: Context, error) -> None:
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


# Load dotenv values and run the bot
load_dotenv()
bot = DiscordBot()
bot.run(os.getenv("TOKEN"))
