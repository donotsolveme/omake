from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context

if TYPE_CHECKING:
    from bot import Omake

class Generate(commands.Cog):
    def __init__(self, bot: Omake) -> None:
        self.bot = bot
        if self.hasModel():
            if self.bot.config["auto"]["enabled"]:
                interval = self.bot.config["auto"]["interval"]
                self.auto_make.change_interval(minutes=interval)
                self.auto_make.start()

    def cog_unload(self):
        self.auto_make.cancel()

    def hasModel(self) -> bool:
        try:
            self.bot.model
            return True
        except:
            return False  

    async def make_sentence(self, with_start: Optional[str] = None) -> str | None:
        sentence = None

        if with_start:
            sentence = self.bot.model.make_sentence_with_start(with_start, tries=250)
        else:
            sentence = self.bot.model.make_sentence(tries=250, test_output=False)

        if sentence is not None:
            sentence = sentence.replace(" ", "")

        return sentence

    @commands.command()
    async def make(self, ctx: Context, with_start: Optional[str] = None):
        if not self.hasModel(): return
        if with_start:
            sentence = await self.make_sentence(with_start)
            await ctx.send(sentence)
        else:
            sentence = await self.make_sentence()
            await ctx.send(sentence)

    @make.error
    async def make_error(self, ctx: Context, error):
        if error is KeyError:
            await ctx.send(f"{ctx.command.with_start}から始まる文字列が存在しません。")
        elif error is discord.HTTPException:
            await ctx.send(f"生成に失敗しました！メッセージの数が少ない可能性があります。")
        else:
            await ctx.send(f"生成に失敗しました！ログを確認してください。")

        print(error)

    @tasks.loop()
    async def auto_make(self):
        channel: discord.abc.Messaeable = await self.bot.fetch_channel(self.bot.config["auto"]["channel"])  # type: ignore
        min = self.bot.config["auto"]["min"]
        max = self.bot.config["auto"]["max"]
        for _ in range(random.randint(min, max)):
            sentence = await self.make_sentence()
            await channel.send(sentence)


async def setup(bot: Omake):
    await bot.add_cog(Generate(bot))
