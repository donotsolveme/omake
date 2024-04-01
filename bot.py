import discord
import markovify
import yaml
from discord.ext import commands
import os

with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

initial_extensions = (
    "cogs.model",
    "cogs.generate",
)


class Omake(commands.Bot):
    model: markovify.text.NewlineText
    config: dict
    root_dir: str

    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=config["prefix"],
            intents=intents,
        )
        self.config = config
        self.root_dir = os.path.dirname(os.path.abspath(__file__))

    async def on_ready(self) -> None:
        print(f"Ready: {self.user} ({self.user.id})")
        # print(self.config)

    async def setup_hook(self) -> None:
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                # print(f"Loaded: {extension}")
            except Exception as e:
                print(e)
                print(f"{extension}の読み込みに失敗しました。")

        # jishaku for develop / debug
        try:
            await self.load_extension("jishaku")
        except:
            pass


bot = Omake()

bot.run(config["token"], log_handler=None)
