import discord
from discord import app_commands
from discord.ui import Select, View
from discord.ext import commands
import asyncio
from typing import List, Optional 
import requests
import mysql.connector
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

def call_api(url, quiet=False):
    riot_api_key = open('tokens/riot_api_key.txt', 'r').readline().strip()
    headers = {
        'X-Riot-Token': riot_api_key
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        if not quiet: print(response.json())
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
        latest_game_id = self.tft_stuff.get_latest_game_id(puuid)
        if puuid == False:
            return False
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("select exists(select * from users where puuid=%s)", (puuid,))
            result = cursor.fetchone()[0]
            if result == 0:
                cursor.execute("insert into users values (%s, %s, %s, %s, %s)", (disc_id, summoner_name, riot_id, puuid, latest_game_id, ))
                self.cnx.commit()
                return True
            else:
                return False
        
    def get_discord_id_from_puuid(self, puuid):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("SELECT * FROM users where puuid=%s", (puuid, ))
            row = cursor.fetchone()
        if row:
            return row[0]
        else:
            return None

    def get_user_latest_game(self, discord_id):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            #cursor.execute("select puuid, current_game_id from users where disc_id=%s and current_game_id is not NULL", (discord_id,))
            # Check if there is a current game with no placement saved
            cursor.execute("select g.puuid, game_id from games g inner join users u on g.puuid=u.puuid where disc_id=%s and placement is NULL", (discord_id,))
            row = cursor.fetchone()
            if row:
                puuid, current_game_id = row
                return [puuid, current_game_id]
            # If did not get a row, get latest game
            cursor.execute("select g.puuid, g.game_id from games g inner join users u on g.puuid=u.puuid where disc_id=%s and game_date is not NULL order by game_date desc LIMIT 1", (discord_id,))
            row = cursor.fetchone()
            if row: 
                puuid, last_game_id = row
                return [puuid, last_game_id]
        return False
    
    def input_augments(self, game_id, puuid, augment1=None, augment2=None, augment3=None, augment4=None):
        self.cnx.reconnect()
        if not augment1 and not augment2 and not augment3 and not augment4:
            return "No augments entered."
        with self.cnx.cursor() as cursor:
            if augment1:
                cursor.execute("update games set aug1=%s where game_id=%s and puuid=%s", (augment1, game_id, puuid, ))
            if augment2:
                cursor.execute("update games set aug2=%s where game_id=%s and puuid=%s", (augment2, game_id, puuid, ))
            if augment3:
                cursor.execute("update games set aug3=%s where game_id=%s and puuid=%s", (augment3, game_id, puuid, ))
            if augment4:
                cursor.execute("update games set aug4=%s where game_id=%s and puuid=%s", (augment4, game_id, puuid, ))
            # Grab all saved augments
            cursor.execute("select aug1, aug2, aug3, aug4 from games where game_id=%s and puuid=%s", (game_id, puuid, ))
            row = cursor.fetchone()
            self.cnx.commit()
        saved_aug1, saved_aug2, saved_aug3, saved_aug4 = row
        output = f'Saved augments for game ID {game_id}:\nAugment 1: {saved_aug1}\nAugment 2: {saved_aug2}\nAugment 3: {saved_aug3}\nAugment 4: {saved_aug4}'
        return output
    
    def get_augments_by_gameid(self, game_id, puuid):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
        # Grab all saved augments
            cursor.execute("select aug1, aug2, aug3, aug4 from games where game_id=%s and puuid=%s", (game_id, puuid, ))
            row = cursor.fetchone()
        saved_aug1, saved_aug2, saved_aug3, saved_aug4 = row
        output = f'Saved augments for game ID {game_id}:\nAugment 1: {saved_aug1}\nAugment 2: {saved_aug2}\nAugment 3: {saved_aug3}\nAugment 4: {saved_aug4}'
        return output

    def get_all_users(self):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
        return rows
    
    def get_all_users_outofgame(self):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            #cursor.execute("SELECT * FROM users where current_game_id is NULL")
            cursor.execute("SELECT distinct g.puuid, u.disc_id FROM games g inner join users u on g.puuid=u.puuid where placement is null")
            rows = cursor.fetchall()
        return rows

    def get_all_puuids(self):
        users = self.get_all_users()
        puuids = [u[3] for u in users] # Element 3 is each user's puuid
        return puuids
    
    def add_new_game(self, puuid, game_id, patch, game_date=None, placement=None, augments=[None for _ in range(4)], units=[None for _ in range(13)]):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("select exists(select * from games where game_id=%s)", (game_id,))
            result = cursor.fetchone()[0]
            if result == 0:
                augments += [None] * (4 - len(augments)) # Extend augments length to 4
                units += [None] * (13 - len(units)) # Extend units length to 13
                #print((puuid, game_id, patch, game_date, placement, *augments, *units, ))
                cursor.execute("insert into games values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (puuid, game_id, patch, game_date, placement, *augments, *units, ))
                self.cnx.commit()
                return True
            else:
                return False
            
    def update_game_on_finish(self, puuid, game_id, placement, units, game_date):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            # Update user's current game --------- NO LONGER NEEDED -----------
            #cursor.execute('update users set current_game_id=NULL where puuid=%s', (puuid, ))

            # Update game record
            units += [None] * (13 - len(units)) # Extend units length to 10
            cursor.execute("update games set game_date=%s, placement=%s, unit1=%s, unit2=%s, unit3=%s, unit4=%s, unit5=%s, unit6=%s, unit7=%s, unit8=%s, unit9=%s, unit10=%s where game_id=%s and puuid=%s", (game_date, placement, *units, game_id, puuid))
            self.cnx.commit()
    
    def check_current_game_exists(self, puuid, game_id):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("select exists(select * from games where puuid=%s and game_id=%s)", (puuid, game_id,))
            result = cursor.fetchone()[0]
            if result == 0:
                return False
            else:
                return True

    def get_active_games(self):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("select * from games where placement is NULL")
            rows = cursor.fetchall()
        return rows
    
    def get_user_game_ids(self, puuid):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("select game_id from games where puuid=%s", (puuid,))
            rows = cursor.fetchall()
        game_ids = [row[0] for row in rows]
        return game_ids

class tft_stuff_class():
    def __init__(self, version='15.13.1', current_set='14', patch='14.7'):
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
        #print(puuid)
        url = f"https://na1.api.riotgames.com/lol/spectator/tft/v5/active-games/by-puuid/{puuid}"
        game = call_api(url, quiet=False)
        #print(game)
        return game
    
    def get_latest_game_id(self, puuid):
        url = f'https://americas.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids'
        games = call_api(url)
        latest_game = int(games[0].split('NA1_')[1]) # Isolate game ID from NA1_ and make int
        return latest_game

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
        #main = Image.open(f"champs/{champ}.png")
        main = Image.open(BytesIO(requests.get(f"https://cdn.metatft.com/cdn-cgi/image/width=48,height=48,format=auto/https://cdn.metatft.com/file/metatft/champions/{champ.lower()}.png").content))
        items_array = []
        for item in items:
            #items_array.append(Image.open(f"items/{item}.png"))
            items_array.append(Image.open(BytesIO(requests.get(f'https://ddragon.leagueoflegends.com/cdn/{self.version}/img/tft-item/{item}.png').content)).resize((48, 48), Image.LANCZOS))


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
        full = Image.new("RGBA", ((image_width+gap)*max(10, len(units)) + placement_gap, image_height), (0, 0, 0, 0))

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

        
        #full.save('test.png')

        image_binary = BytesIO()
        full.save(image_binary, 'PNG')
        #return image_binary
        image_binary.seek(0)
        return image_binary

    def get_user_unit_info(self, puuid, game_json):
        #print(game_json)
        matched_participant = next(
            (p for p in game_json['info']['participants'] if p['puuid'] == puuid),
            None
        )
        units = matched_participant['units']
        unit_pics = []
        for unit in units:
            unit_pics.append(self.construct_champ(unit['character_id'], unit['itemNames']))
        
        placement = matched_participant['placement']
        full_pic = self.create_full_pic(unit_pics, placement)
        
        units_only = [u['character_id'] for u in units]
        return units_only, placement, full_pic


tft_stuff = tft_stuff_class()
sql_stuff = sql_stuff_class(tft_stuff)

guild_id = 1391926028536123403
intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

auth_users = [196404822063316992]

@client.event
async def on_ready():
    #await tree.sync(guild=discord.Object(id=guild_id))
    await tree.sync()
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
            sql_stuff.update_game_on_finish(puuid, game_id, placement, units, game_date)
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

        games_url = f'https://americas.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids'
        game_ids = call_api(games_url)
        clean_ids = [int(game_id.replace('NA1_', '')) for game_id in game_ids]

        if user_first_game_id in clean_ids:
            missed_games = clean_ids[:clean_ids.index(user_first_game_id)]
        else:
            missed_games = clean_ids

        existing_game_ids = sql_stuff.get_user_game_ids(puuid)

        missed_games = [gid for gid in missed_games if gid not in existing_game_ids]

        for game_id in reversed(missed_games):
            url = f'https://americas.api.riotgames.com/tft/match/v1/matches/NA1_{game_id}'
            game = call_api(url)

            game_date = datetime.fromtimestamp(game['info']['game_datetime']/1000)

            units, placement, full_pic = tft_stuff.get_user_unit_info(puuid, game)
            #sql_stuff.update_game_on_finish(puuid, game_id, placement, units, game_date)
            sql_stuff.add_new_game(puuid, game_id, tft_stuff.patch, game_date, placement, units=units)
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

# Run the bot
disc_token = open('tokens/disc_token.txt', 'r').readline()
client.run(disc_token)