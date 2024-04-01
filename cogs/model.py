from __future__ import annotations

import asyncio
import datetime
import os
import re
import time
import yaml
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

# source: https://github.com/yaml/pyyaml/issues/127
class YamlDumper(yaml.SafeDumper):
    # HACK: insert blank lines between top-level objects
    # inspired by https://stackoverflow.com/a/44284819/3786245
    def write_line_break(self, data=None):
        super().write_line_break(data)

        if len(self.indents) == 1:
            super().write_line_break()

class Model(commands.Cog):
    def __init__(self, bot: Omake) -> None:
        self.bot: Omake = bot

        timezone = zoneinfo.ZoneInfo(self.bot.config["regenerate"]["timezone"])

        # init model
        data_path = self.bot.root_dir + "/data.txt"
        if os.path.isfile(data_path):
            with open(data_path, "r", encoding="utf-8") as data:
                self.bot.model = markovify.NewlineText(data.read())
                print("[-] モデルの生成が完了しました")
        else:
            print(
                f"[!] メッセージのデータが見つかりませんでした！\n    メッセージを収集するサーバーで {self.bot.command_prefix}setup と送信してください。"
            )

        if self.bot.config["regenerate"]["enabled"] and self.bot.config["guild"]:
            regen_time = datetime.time(hour=0, tzinfo=timezone)
            self.regenerate.change_interval(time=regen_time)
            self.regenerate.start()

    def cog_unload(self):
        self.regenerate.cancel()

    @staticmethod
    def first_line(string: str | None) -> str | None:
        if isinstance(string, str):
            try:
                return string.splitlines()[0]
            except:
                return
        else:
            return

    def check_message(self, message: discord.Message):
        first_line = self.first_line(message.content)
        if message.content == "": # Exclude empty message
            print("Message is empty")
            return False
        elif message.author.bot: # Exclude bots
            print("Message author is bot:", first_line)
            return False
        elif message.content.startswith(tuple(self.bot.config["exclude"]["prefixes"])): # Exclude prefix(configure in config.yaml): !command
            print("Message starts with prefix:", first_line)
            return False
        elif message.content.isdigit(): # Exclude only digits
            print("Message is digits only: ", first_line)
            return False
        elif re.search(pattern_url, first_line): # Exclude URL
            print("Message include URL:", first_line)
            return False
        elif re.search(pattern_emoji, first_line): # Exclude emoji
            print("Message include emoji:", first_line)
            return False
        elif "discord.gg" in message.content: # Exclude invite: discord.gg/discord-developers
            print("Message include invite:", first_line)
            return False
        elif "<@" in message.content: # Exclude user mention: <@00000>
            print("Message include user mention:", first_line)
            return False
        elif "<#" in message.content: # Exclude channel mention: <#00000>
            print("Message include channel mention:", first_line)
            return False
        elif "</" in message.content: # Exclude slash command mention: </command:0>
            print("Message include slash command mention:", first_line)
            return False
        elif "<t:" in message.content: # Exclude timestamp: <t:00000>
            print("Message include timestamp:", first_line)
            return False
        elif "```" in message.content: # Exclude code block
            print("Message include code block: ", first_line)
            return False
        else:
            print(first_line)
            return True

    async def send_regen_log(self, message: str):
        if self.bot.config["regenerate"]["log"]:
            guild: discord.Guild = self.bot.get_guild(config["guild"])
            channel: discord.TextChannel = await self.bot.fetch_channel(self.bot.config["regenerate"]["log_channel"])  # type: ignore
            await channel.send(message)

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
        await ctx.message.clear_reaction("🔄")
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
            await msg.edit(content="timeout")
            return
        else:
            await msg.clear_reactions()
            await msg.edit(content="処理を開始します… (処理に10分以上かかる可能性があります。)", embed=None)

        start = time.time()

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

        print("[-] メッセージの取得が完了しました")

        wakati = ""
        for m in messages:
            wakati += "\n" + tagger.parse(m)

        with open("data.txt", "w", encoding="utf-8") as f:
            f.write(wakati)

        print("[-] 分かち処理が完了しました")
            
        # self.bot.model = markovify.NewlineText(wakati) 
        #
        # print("✅ Model generate")

        await self.bot.reload_extension("cogs.model")
        await self.bot.reload_extension("cogs.generate")
 
        print("[-] リロードが完了しました")

        end = time.time()

        print(f"[!] Setup done. ({end - start}s)")
        await msg.edit(content=f"処理が完了しました！:tada:\n`{self.bot.command_prefix}make`で動作を確認してください！")

        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            config["guild"] = ctx.guild.id

        with open("config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False, Dumper=YamlDumper)


    @setup.error
    async def setup_error(self, ctx, error):
        print(error)

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
                        if self.check_message(message):
                            messages.append(str(message.content))
            else:
                async for message in channel.history(after=after, limit=None):
                    if self.check_message(message):
                        messages.append(str(message.content))

        await log.send("取得が完了しました。分かちを開始します…")

        write_messages = "\n"

        for message in messages:
            write_messages += " ".join(tagger.parse(message).split()) + "\n"

        await log.send("分かちが完了しました。書き込んでいます…")

        with open("./data.txt", "a", encoding="utf-8") as file:
            file.write(write_messages)

        await log.send("書き込みが完了しました。モデルを作成しています…")

        with open("./data.txt", "r", encoding="utf-8") as data:
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
