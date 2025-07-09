import discord
from discord import app_commands
from discord.ui import Select, View
from discord.ext import commands
import asyncio
from typing import List
import requests
import mysql.connector
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

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
        print(puuid)
        if puuid == False:
            return False
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("select exists(select * from users where puuid=%s)", (puuid,))
            result = cursor.fetchone()[0]
            print(result)
            if result == 0:
                cursor.execute("insert into users values (%s, %s, %s, %s, NULL, NULL)", (disc_id, summoner_name, riot_id, puuid,))
                self.cnx.commit()
                return True
            else:
                return False
        

    def get_all_users(self):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
            #print(rows)
        return rows
    
    def get_all_users_outofgame(self):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("SELECT * FROM users where current_game_id is NULL")
            rows = cursor.fetchall()
            #print(rows)
        return rows

    def get_all_puuids(self):
        users = self.get_all_users()
        puuids = [u[3] for u in users]
        #print(puuids)
        return puuids
    
    def add_new_game(self, disc_id, puuid, game_id, patch, game_date, placement=None, augments=[None for _ in range(3)], units=[None for _ in range(10)]):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("select exists(select * from games where game_id=%s)", (game_id,))
            result = cursor.fetchone()[0]
            #print(result)
            if result == 0:
                cursor.execute("insert into games values (%s, %s, %s, %s, NULL, NULL)", (disc_id, puuid, game_id, patch, game_date, placement, *augments, *units))
                self.cnx.commit()
                return True
            else:
                return False
            
    def update_game_on_finish(self, puuid, game_id, placement, units):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            # Update user's current game
            cursor.execute('update users set current_game_id=NULL where puuid=%s', (puuid, ))
            # Update game record
            print(placement, units, game_id)
            print((placement, *units, game_id))
            cursor.execute("update games set placement=%s, unit1=%s, unit2=%s, unit3=%s, unit4=%s, unit5=%s, unit6=%s, unit7=%s, unit8=%s, unit9=%s, unit10=%s where game_id=%s", (placement, *units, game_id))
            self.cnx.commit()



    def update_user_current_game(self, puuid, game_id):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("update users set current_game_id=%s where puuid=%s", (game_id, puuid, ))

    def get_current_game(self, puuid):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("select * from users where puuid=%s", (puuid, ))
            result = cursor.fetchone()
        print(result)
        return result[5]

    def get_active_games(self):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("select * from games where placement is NULL")
            rows = cursor.fetchall()
        return rows

class tft_stuff_class():
    def __init__(self, version='15.9.1', current_set='14', patch='14.7'):
        self.version = version
        self.augments = self.get_augs(version)
        self.current_set=current_set
        self.patch = patch

    def get_augs(self, version):
        # URL of the JSON
        url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/tft-augments.json"
        data = call_api(url)

        augs = [d['name'] for d in data['data'].values()]
        return augs
    
    def get_current_game(self, puuid):
        url = f"https://na1.api.riotgames.com/lol/spectator/tft/v5/active-games/by-puuid/{puuid}"
        #print(url)
        game = call_api(url)
        return game


    def get_user_last_game(self, puuid):
        url = f'https://americas.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids'
        games = call_api(url)
        if games is False:
            return "Error getting latest games."
        for game_id in games:
            url = f'https://americas.api.riotgames.com/tft/match/v1/matches/{game_id}'
            game = call_api(url)
            #print(game)
            #print('-------------------------')
            #print(game['info']['tft_game_type'], game['info']['tft_set_number'])

    def get_user_puuid(self, summoner_name, riot_id, region='americas'):
        url = f'https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{riot_id}'
        response = call_api(url)
        if not response:
            return False
        return response['puuid']
    
    def get_game(self, game_id):
        url = f'https://americas.api.riotgames.com/tft/match/v1/matches/NA1_{game_id}'
        response = call_api(url)
        if not response:
            return False
        return response
    
    def construct_champ(self, champ, items, image_size=48):
        # Load your images
        main = Image.open(f"champs/{champ}.png")
        items_array = []
        for item in items:
            items_array.append(Image.open(f"items/{item}.png"))


        # Create a new image with the right dimensions
        total_width = image_size*3
        total_height = image_size*4

        # Resize bottom images to match heights if needed
        main = main.resize((image_size*3, image_size*3))


        combined = Image.new("RGBA", (total_width, total_height), (0, 0, 0, 0))

        # Paste the top image
        combined.paste(main, (0, 0))

        # Paste bottom images next to each other
        for index, item in enumerate(items_array):  
            combined.paste(item, (image_size*index, main.height))
        return combined
    
    def create_full_pic(self, units, placement, image_width=144, image_height=192, gap=5, placement_gap = 125):
        full = Image.new("RGBA", ((image_width+gap)*10 + placement_gap, image_height), (0, 0, 0, 0))

        ImageDraw.Draw(full  # Image
            ).text(
            (5, 20),  # Coordinates
            "#" + str(placement),  # Text
            (255, 255, 255),  # Color
            font = ImageFont.load_default(100)
            #font = ImageFont.truetype("DejaVuSans.ttf", 100)
        )
        # Paste the top image
        for index, unit in enumerate(units):
            full.paste(unit, ((gap+image_width)*index + placement_gap, 0))


        return full

    def get_user_unit_info(self, puuid, game_json):
        #print(game_json)
        matched_participant = next(
            (p for p in game_json['info']['participants'] if p['puuid'] == puuid),
            None
        )
        print(matched_participant)
        units = matched_participant['units']
        unit_pics = []
        for unit in units:
            unit_pics.append(self.construct_champ(unit['character_id'], unit['itemNames']))
        placement = matched_participant['placement']
        full_pic = self.create_full_pic(unit_pics, placement)
        return units, placement, full_pic


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
    #client.loop.create_task(new_games_loop())
    client.loop.create_task(ended_games_loop())
    print("Ready!")

async def new_games_loop():
    await client.wait_until_ready()
    #channel = client.get_channel(channel_id)
    while True:
        players = sql_stuff.get_all_users_outofgame()
        #puuids = sql_stuff.get_all_puuids()
        for player in players:
            puuid = player[3]
            response = tft_stuff.get_current_game(puuid)
            #print(response)
            if response != False:
                # Check if game in database already
                game_id = response['gameId']
                if game_id == sql_stuff.get_current_game(puuid):
                    await asyncio.sleep(3)
                    continue
                # Add new game if not already in database
                disc_id = player[0]
                patch = tft_stuff.patch
                game_date = datetime.now()
                sql_stuff.update_user_current_game(puuid, game_id)
                sql_stuff.add_new_game(disc_id, puuid, game_id, patch, game_date)
                await message_user_newgame(disc_id, game_id)
            await asyncio.sleep(3)
        await asyncio.sleep(2)

async def ended_games_loop():
    await client.wait_until_ready()
    while True:
        active_games = sql_stuff.get_active_games()
        for active_game in active_games:
            game_id = active_game[2]
            tft_game = tft_stuff.get_game(game_id)
            if tft_game == False:
                await asyncio.sleep(3)
                continue
            disc_id = active_game[0]
            puuid = active_game[1]
            units, placement, full_pic = tft_stuff.get_user_unit_info(puuid, tft_game)
            sql_stuff.update_game_on_finish(puuid, game_id, placement, units)
            await message_user_game_ended(disc_id, game_id, full_pic)
        await asyncio.sleep(3)


async def message_user_newgame(disc_id, game_id):
    user = await client.fetch_user(disc_id)
    await user.send(f"In a game! Game ID: {game_id}")

async def message_user_game_ended(disc_id, game_id, embed):
    user = await client.fetch_user(disc_id)
    await user.send(f"Game ended! Game ID: {game_id}", embed=embed)

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

@tree.command(name = "get_users", description = "Get list of users")
async def first_command(interaction):
    sql_stuff.get_all_users()
    sql_stuff.get_all_puuids()
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