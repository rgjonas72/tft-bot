import discord
from discord import app_commands
from discord.ui import Select, View
from discord.ext import commands
import asyncio
from typing import List, Optional 
from datetime import datetime
from tft_custom_class import tft_stuff_class
from sql_custom_class import sql_stuff_class

tft_stuff = tft_stuff_class()
sql_stuff = sql_stuff_class(tft_stuff)

guild_id = 1391926028536123403
intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

auth_users = [196404822063316992]

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=guild_id))
    #await tree.sync()
    await catchup_missed_games()
    client.loop.create_task(new_games_loop())
    client.loop.create_task(ended_games_loop())
    print("Ready!")

async def new_games_loop():
    await client.wait_until_ready()
    #channel = client.get_channel(channel_id)
    while True:
        players = sql_stuff.get_all_users_outofgame()
        #print(players)
        #puuids = sql_stuff.get_all_puuids()
        for player in players:
            puuid = player[0]
            response = tft_stuff.get_current_game(puuid)
            #print(response)
            if response != False:
                # Check if game in database already
                game_id = response['gameId']
                if sql_stuff.check_current_game_exists(puuid, game_id):
                    await asyncio.sleep(3)
                    continue
                # Add new game if not already in database
                disc_id = player[1]
                patch = tft_stuff.patch
                #sql_stuff.update_user_current_game(puuid, game_id)
                sql_stuff.add_new_game(puuid, game_id, patch)
                await message_user_newgame(disc_id, game_id)
            await asyncio.sleep(3)
        await asyncio.sleep(2)

async def ended_games_loop():
    await client.wait_until_ready()
    while True:
        active_games = sql_stuff.get_active_games()
        for active_game in active_games:
            game_id = active_game[1]
            tft_game = tft_stuff.get_game(game_id)
            if tft_game == False:
                await asyncio.sleep(3)
                continue
            puuid = active_game[0]
            game_date = datetime.fromtimestamp(tft_game['info']['game_datetime']/1000)
            units, placement, full_pic = tft_stuff.get_user_unit_info(puuid, tft_game)
            queue_id = tft_game['info']['queue_id']
            sql_stuff.update_game_on_finish(puuid, game_id, placement, units, game_date, queue_id)
            disc_id = sql_stuff.get_discord_id_from_puuid(puuid)
            await message_user_game_ended(disc_id, game_id, full_pic, puuid)
        await asyncio.sleep(3)
        await catchup_missed_games()
        await asyncio.sleep(2)

async def catchup_missed_games():
    users = sql_stuff.get_all_users()
    for user in users:
        disc_id = user[0]
        puuid = user[3]
        user_first_game_id = user[4]

        game_ids = tft_stuff.get_game_ids(puuid)

        clean_ids = [int(game_id.replace('NA1_', '')) for game_id in game_ids]

        if user_first_game_id in clean_ids:
            missed_games = clean_ids[:clean_ids.index(user_first_game_id)]
        else:
            missed_games = clean_ids

        existing_game_ids = sql_stuff.get_user_game_ids(puuid)

        missed_games = [gid for gid in missed_games if gid not in existing_game_ids]

        for game_id in reversed(missed_games):
            game = tft_stuff.get_game(game_id)

            game_date = datetime.fromtimestamp(game['info']['game_datetime']/1000)

            units, placement, full_pic = tft_stuff.get_user_unit_info(puuid, game)
            queue_id = game['info']['queue_id']
            #sql_stuff.update_game_on_finish(puuid, game_id, placement, units, game_date)
            sql_stuff.add_new_game(puuid, game_id, tft_stuff.patch, game_date, placement, units=units, queue_id=queue_id)
            #disc_id, puuid, game_id, patch, game_date, placement=None, augments=[None for _ in range(4)], units=[None for _ in range(10)])
            await message_user_game_ended(disc_id, game_id, full_pic, puuid)
            await asyncio.sleep(2)


async def message_user_newgame(disc_id, game_id):
    user = await client.fetch_user(disc_id)
    await user.send(f"In a game! Game ID: {game_id}")

async def message_user_game_ended(disc_id, game_id, embed, puuid):
    user = await client.fetch_user(disc_id)
    augments = sql_stuff.get_augments_by_gameid(game_id, puuid)
    await user.send(f"Game ended! Game ID: {game_id}\n{augments}", file=discord.File(fp=embed, filename='image.png'))


async def rps_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    choices = tft_stuff.augments
    choices = [app_commands.Choice(name=choice, value=choice) for choice in choices if current.lower() in choice.lower()][:25]
    return choices


@tree.command(name="input_augments", description = "Input your augments")
@app_commands.describe(game_id="Game ID (will automatically use current/last game)",
                       augment1="Augment 1",
                       augment2="Augment 2",
                       augment3="Augment 3",
                       augment4="Augment 4")
@app_commands.autocomplete(augment1=rps_autocomplete)
@app_commands.autocomplete(augment2=rps_autocomplete)
@app_commands.autocomplete(augment3=rps_autocomplete)
@app_commands.autocomplete(augment4=rps_autocomplete)
async def input_augments(interaction: discord.Interaction, augment1: Optional[str]=None, augment2: Optional[str]=None, augment3: Optional[str]=None, augment4: Optional[str]=None, game_id: Optional[int]=None):
    if not game_id:
        puuid_game_id = sql_stuff.get_user_latest_game(interaction.user.id)
        if not puuid_game_id: interaction.response.send_message('No game ID provided and no default game found.')
        puuid, game_id = puuid_game_id

    output = sql_stuff.input_augments(game_id, puuid, augment1, augment2, augment3, augment4)
    await interaction.response.send_message(output)

@tree.command(name = "register_account", description = "Register your account")
@app_commands.describe(summoner_name="Summoner name",
                       riot_id="Riot ID")
async def register_account(interaction: discord.Interaction, summoner_name: app_commands.Range[str, 1, 16], riot_id: app_commands.Range[str, 1, 5]):
    if sql_stuff.add_user(interaction.user.id, summoner_name, riot_id):
        await interaction.response.send_message(f'Registered {summoner_name}#{riot_id}!')
    else:
        await interaction.response.send_message(f'Failed to register {summoner_name}#{riot_id}.')

@tree.command(name="update_bot_info", description = "Update patch/api key", guild=discord.Object(id=guild_id))
@app_commands.describe(patch="TFT Patch",
                       api_version="API Version",
                       riot_api_key="Riot API Key")
async def update_bot_info(interaction: discord.Member, patch: Optional[str]=None, api_version: Optional[str]=None, riot_api_key: Optional[str]=None):
    if interaction.user.id not in auth_users:
        await interaction.response.send_message(f"Not allowed to update.", ephemeral=True)

    sql_stuff.update_bot_info(patch, api_version, riot_api_key)
    tft_stuff.update_bot_info()
    await interaction.response.send_message(f"Updated bot info", ephemeral=True)

@tree.command(name="augment_stats", description = "Check augment stats", guild=discord.Object(id=guild_id))
@app_commands.describe(augment="Augment to check stats on",
                       user="Specify augment stats to user")
@app_commands.autocomplete(augment=rps_autocomplete)
async def augment_stats(interaction: discord.Member, augment: Optional[str]=None, user: discord.Member=None):
    if augment:
        avp, games=sql_stuff.get_augment_stats(augment, user)
        #embed = tft_stuff.create_augment_stats_pic(augment, avp)
        #await interaction.response.send_message(file=discord.File(fp=embed, filename='image.png'))
        embed = tft_stuff.get_augment_stats_embed(augment, avp, games, user)
        await interaction.response.send_message(embed=embed)
    else:
        #embed = sql_stuff.get_all_augment_stats()
        pagination = sql_stuff.get_all_augment_stats(interaction, user)
        await pagination.navegate()
        #await interaction.response.send_message(embed=embed)

from tft_custom_class import UserSelectView
@tree.command(name="test", description="Select multiple users via menu")
async def select_users(interaction: discord.Interaction):
    members = [m for m in interaction.guild.members if not m.bot]
    view = UserSelectView(members)
    await interaction.response.send_message(
        "Select users from the dropdown menu:", view=view, ephemeral=True
    )

# Run the bot
disc_token = open('tokens/disc_token.txt', 'r').readline()
client.run(disc_token)