from __future__ import annotations

import asyncio
import datetime
import os
import re
import time
import zoneinfo
from typing import TYPE_CHECKING

import discord
import fugashi
import markovify
from discord.ext import commands, tasks
from discord.ext.commands import Context

if TYPE_CHECKING:
    from bot import Omake

pattern_url = r"https?://[\w/:%#\$&\?\(\)~\.=\+\-]+"
pattern_emoji = r"<(a)?:\w+:\d+>"

tagger = fugashi.Tagger("-Owakati")


class Model(commands.Cog):
    def __init__(self, bot: Omake) -> None:
        self.bot: Omake = bot

        timezone = zoneinfo.ZoneInfo(self.bot.config["regenerate"]["timezone"])

        # init model
        dir = os.path.dirname(os.path.abspath(__file__))
        if os.path.isfile(f"{dir}/data.txt"):
            with open("./data.txt", "r", encoding="utf-8") as data:
                self.bot.model = markovify.NewlineText(data.read())
        else:
            print(
                f"メッセージのデータが見つかりませんでした！\nメッセージを収集するサーバーで{self.bot.command_prefix}setupと送信してください。"
            )

        regen_time = datetime.time(hour=0, tzinfo=timezone)
        self.regenerate.change_interval(time=regen_time)
        self.regenerate.start()

    def check_message(self, message: discord.Message):
        if re.search(pattern_url, message.content):
            print("Message include URL:", message.content)
            return False
        elif re.search(pattern_emoji, message.content):
            print("Message include emoji:", message.content)
            return False
        elif "discord.gg" in message.content:
            print("Message include invite:", message.content)
            return False
        elif "<@" in message.content:
            print("Message include user mention:", message.content)
            return False
        elif "<#" in message.content:
            print("Message include channel mention:", message.content)
            return False
        elif "</" in message.content:
            print("Message include slash command mention:", message.content)
            return False
        elif "<t:" in message.content:
            print("Message include timestamp:", message.content)
            return False
        elif message.content.startswith(self.bot.config["exclude"]["prefixes"]):
            print("Message starts with prefix:", message.content)
            return False
        elif message.content == "":
            print("Message is empty")
            return False
        elif message.content.isdecimal():
            print("Message is decimal:", message.content)
            return False
        elif message.author.bot:
            print("Message author is bot:", message.content)
            return False
        else:
            print(message.content)
            return True

    @commands.command()
    @commands.is_owner()
    @commands.guild_only()
    async def setup(self, ctx: Context):
        await ctx.message.add_reaction("🔄")

        exclude_channels_text = ", ".join(
            [f"<#{id}>" for id in self.bot.config["exclude"]["channels"]]
        )

        exclude_prefixes_text = " ".join(
            [f"`{p}`" for p in self.bot.config["exclude"]["prefixes"]]
        )

        description = (
            f"セットアップを開始します。\n\n"
            f"サーバー: `{ctx.guild.name}` ({ctx.guild.id})\n"  # type: ignore
            f"含めないチャンネル: {exclude_channels_text}\n"
            f"含めないプレフィックス: {exclude_prefixes_text}\n\n"
            f"以上の内容でよろしければ`✅`とリアクションしてください。(タイムアウト: 30秒)"
        )

        embed = discord.Embed(title="セットアップ", description=description)
        msg = await ctx.reply(embed=embed)
        await msg.add_reaction("✅")

        def check(reaction, user):
            return (
                user == ctx.message.author
                and str(reaction.emoji) == "✅"
                and reaction.message == msg
            )

        try:
            reaction, user = await self.bot.wait_for(
                "reaction_add", timeout=30, check=check
            )
        except asyncio.TimeoutError:
            await msg.clear_reactions()
            return
        else:
            await msg.clear_reactions()
            await msg.edit(content="yarimasu")

        messages = []

        for channel in ctx.guild.channels:
            if channel.id in self.bot.config["exclude"]["channels"]:
                continue
            elif isinstance(channel, discord.CategoryChannel):
                continue
            elif isinstance(channel, discord.ForumChannel):
                for thread in channel.threads:
                    async for message in thread.history(limit=None):
                        if self.check_message(message):
                            messages.append(str(message.content))
            else:
                async for message in channel.history(limit=None):
                    if self.check_message(message):
                        messages.append(str(message.content))

        messages_format = "\n".join(messages)

        with open("messages.txt", "w", encoding="utf-8") as file:
            file.write(messages_format)

        await msg.edit(content="done")

    @tasks.loop()
    async def regenerate(self):
        guild: discord.Guild = self.bot.get_guild(config.guild)
        log: discord.TextChannel = await self.bot.fetch_channel(config.log_channel)  # type: ignore

        start = time.time()

        now = int(datetime.datetime.now().timestamp())
        await log.send(f"<t:{now}:f> モデルの更新を開始します")

        after = datetime.datetime.combine(
            datetime.date.today(), datetime.time()
        ) - datetime.timedelta(days=2)

        messages = []

        for channel in guild.channels:
            if channel.id in config.exclude_channels:
                continue
            elif isinstance(channel, discord.CategoryChannel):
                continue
            elif isinstance(channel, discord.ForumChannel):
                for thread in channel.threads:
                    async for message in thread.history(after=after, limit=None):
                        if check_message(message):
                            messages.append(str(message.content))
            else:
                async for message in channel.history(after=after, limit=None):
                    if check_message(message):
                        messages.append(str(message.content))

        await log.send("取得が完了しました。分かちを開始します…")

        write_messages = "\n"

        for message in messages:
            write_messages += " ".join(tagger.parse(message).split()) + "\n"

        await log.send("分かちが完了しました。書き込んでいます…")

        with open("./wakati.txt", "a", encoding="utf-8") as file:
            file.write(write_messages)

        await log.send("書き込みが完了しました。モデルを作成しています…")

        with open("./wakati.txt", "r", encoding="utf-8") as data:
            self.bot.model = markovify.NewlineText(data.read())

        end = time.time()
        diff = int(end - start)

        await log.send(f"モデルの作成が完了しました。処理を終了します！:tada:\n処理時間: {diff}秒")

    @commands.command()
    async def channels(self, ctx: Context):
        channels = []
        exclude = []
        for channel in ctx.guild.channels:
            if channel.id in config.exclude_channels:
                exclude.append(channel.name)
            elif isinstance(channel, discord.CategoryChannel):
                continue
            elif isinstance(channel, discord.ForumChannel):
                for thread in channel.threads:
                    channels.append(thread.name)
            else:
                channels.append(channel.name)
        await ctx.send(f"channels: {channels}\nexclude: {exclude}")


async def setup(bot: Omake):
    await bot.add_cog(Model(bot))
