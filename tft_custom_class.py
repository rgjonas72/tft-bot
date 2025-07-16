import requests
import mysql.connector
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

class tft_stuff_class():
    def __init__(self):
        self.update_bot_info()

    def update_bot_info(self):
        db_name = 'tft'
        cnx = mysql.connector.connect(user='root', password=open('tokens/db_pw.txt', 'r').readline().strip(),host='127.0.0.1', database=db_name)
        with cnx.cursor() as cursor:
            cursor.execute("SELECT * FROM bot_info")
            row = cursor.fetchone()
        self.patch, self.version, self.riot_api_key = row
        self.augments = self.get_augs(self.version)


    def call_api(self, url, quiet=False):
        #iot_api_key = open('tokens/riot_api_key.txt', 'r').readline().strip()
        headers = {
            'X-Riot-Token': self.riot_api_key
        }
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            if not quiet: print(url, response.json())
            return False

    def get_augs(self, version):
        # URL of the JSON
        url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/tft-augments.json"
        data = self.call_api(url)

        augs = [d['name'] for d in data['data'].values()]
        return augs
    
    def get_current_game(self, puuid):
        #print(puuid)
        url = f"https://na1.api.riotgames.com/lol/spectator/tft/v5/active-games/by-puuid/{puuid}"
        game = self.call_api(url, quiet=False)
        #print(game)
        return game
    
    def get_latest_game_id(self, puuid):
        url = f'https://americas.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids'
        games = self.call_api(url)
        latest_game = int(games[0].split('NA1_')[1]) # Isolate game ID from NA1_ and make int
        return latest_game

    def get_user_puuid(self, summoner_name, riot_id, region='americas'):
        url = f'https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{riot_id}'
        response = self.call_api(url)
        if not response:
            return False
        return response['puuid']
    
    def get_game(self, game_id):
        url = f'https://americas.api.riotgames.com/tft/match/v1/matches/NA1_{game_id}'
        response = self.call_api(url)
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
    
    def get_game_ids(self, puuid):
        url = f'https://americas.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids'
        game_ids = self.call_api(url)
        return game_ids

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
        
        units_only = [u['character_id'] for u in units]
        return units_only, placement, full_pic