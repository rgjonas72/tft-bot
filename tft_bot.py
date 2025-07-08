import discord
from discord import app_commands
from discord.ui import Select, View
from discord.ext import commands
import asyncio
from typing import List
import requests
import mysql.connector

def call_api(url):
    riot_api_key = open('tokens/riot_api_key.txt', 'r').readline().strip()
    headers = {
        'X-Riot-Token': riot_api_key
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(response.json())
        return False

class sql_stuff_class():
    def __init__(self, tft_stuff):
        self.cnx = self.get_cnx()
        self.tft_stuff = tft_stuff

    def get_cnx(self):
        db_name = 'tft'
        cnx = mysql.connector.connect(user='root', password=open('tokens/db_pw.txt', 'r').readline().strip(),host='127.0.0.1', database=db_name)
        return cnx
    
    def add_user(self, disc_id, summoner_name, riot_id):
        puuid = self.tft_stuff.get_user_puuid(summoner_name, riot_id)
        if puuid == False:
            return False
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("select exists(select * from users where disc_id=%s)", (disc_id,))
            result = cursor.fetchone()[0]

            if result == 0:
                cursor.execute("insert into users values (%s, %s, %s, %s, NULL)", (disc_id, summoner_name, riot_id, puuid,))
                self.cnx.commit()
                return True
            else:
                return False
        

    def get_all_users(self):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
        
        print(rows)



class tft_stuff_class():
    def __init__(self, version='15.9.1', current_set='14'):
        self.version = version
        self.augments = self.get_augs(version)
        self.current_set=current_set

    def get_augs(self, version):
        # URL of the JSON
        url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/tft-augments.json"
        data = call_api(url)

        augs = [d['name'] for d in data['data'].values()]
        return augs
    
    def get_user_last_game(self, puuid='q-MM0r_oPHvU5YWtq366Y2a0_faxYl_yr-y0VhAhP81VcNxEZyA-FqhxUAsvGq5hvJjAuaV6CKQbog'):
        url = f'https://americas.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids'
        games = call_api(url)
        if games is False:
            return "Error getting latest games."
        for game_id in games:
            url = f'https://americas.api.riotgames.com/tft/match/v1/matches/{game_id}'
            game = call_api(url)
            print(game)
            print('-------------------------')
            print(game['info']['tft_game_type'], game['info']['tft_set_number'])

    def get_user_puuid(self, summoner_name, riot_id, region='americas'):
        url = f'https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{riot_id}'
        response = call_api(url)
        if not response:
            return False
        return response['puuid']



tft_stuff = tft_stuff_class()
sql_stuff = sql_stuff_class(tft_stuff)
#tft_stuff.get_user_last_game(puuid)
#quit()

#cnx = get_cnx()
guild_id = 1391926028536123403
intents = discord.Intents.all()
client = discord.Client(command_prefix='.', intents=intents)
tree = app_commands.CommandTree(client)

auth_users = [231554084782604288, 196404822063316992]

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=guild_id))
    client.loop.create_task(background_loop())
    print("Ready!")

async def background_loop():
    await client.wait_until_ready()
    #channel = client.get_channel(channel_id)
    while True:
        await asyncio.sleep(1)


@tree.command(name = "register", description = "Register your account")
@app_commands.describe(
    summoner_name="Summoner name",
    riot_id="Riot ID"
)
async def register(
    interaction: discord.Interaction,
    summoner_name: app_commands.Range[str, 1, 16],
    riot_id: app_commands.Range[str, 1, 5]
    ):
    if sql_stuff.add_user(interaction.user.id, summoner_name, riot_id):
        await interaction.response.send_message(f'Registered {summoner_name}#{riot_id}!')
    else:
        await interaction.response.send_message(f'Failed to register {summoner_name}#{riot_id}.')


@tree.command(name = "test", description = "Test message")
@app_commands.choices(choices=[app_commands.Choice(name=i, value=i) for i in range(20)])
async def first_command(interaction, choices: app_commands.Choice[int]):
    await interaction.user.send("Test")

@tree.command(name = "get_users", description = "Get list of users")
async def first_command(interaction):
    await interaction.response.send_message("test")

async def rps_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    choices = tft_stuff.augments
    choices = [app_commands.Choice(name=choice, value=choice) for choice in choices if current.lower() in choice.lower()][:25]
    return choices

@tree.command(name="abc", description = "ABC")
@app_commands.autocomplete(something=rps_autocomplete)
async def second_commad(interaction: discord.Interaction, something: str):
    await interaction.user.send(something)

# Run the bot
disc_token = open('tokens/disc_token.txt', 'r').readline()
client.run(disc_token)