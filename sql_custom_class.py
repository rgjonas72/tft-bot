import mysql.connector

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
            
    def update_bot_info(self, patch, api_version, riot_api_key):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            if patch:
                cursor.execute("update bot_info set patch=%s", (patch, ))
            if api_version:
                cursor.execute("update bot_info set api_version=%s", (api_version, ))
            if riot_api_key:
                cursor.execute("update bot_info set riot_api_key=%s", (riot_api_key, ))
            self.cnx.commit()
        
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
            #cursor.execute("SELECT distinct g.puuid, u.disc_id FROM games g inner join users u on g.puuid=u.puuid where placement is null")
            cursor.execute("SELECT distinct u.puuid, u.disc_id FROM users u LEFT JOIN games g ON u.puuid = g.puuid GROUP BY u.puuid HAVING COUNT(g.puuid) = 0 OR SUM(CASE WHEN g.placement IS NULL THEN 1 ELSE 0 END) = 0;")
            rows = cursor.fetchall()
        return rows

    def get_all_puuids(self):
        users = self.get_all_users()
        puuids = [u[3] for u in users] # Element 3 is each user's puuid
        return puuids
    
    def add_new_game(self, puuid, game_id, patch, game_date=None, placement=None, augments=[None for _ in range(4)], units=[None for _ in range(13)], queue_id=None):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("select exists(select * from games where game_id=%s)", (game_id,))
            result = cursor.fetchone()[0]
            if result == 0:
                augments += [None] * (4 - len(augments)) # Extend augments length to 4
                units += [None] * (13 - len(units)) # Extend units length to 13
                #print((puuid, game_id, patch, game_date, placement, *augments, *units, ))
                cursor.execute("insert into games values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", (puuid, game_id, patch, game_date, placement, *augments, *units, queue_id, ))
                self.cnx.commit()
                return True
            else:
                return False
            
    def update_game_on_finish(self, puuid, game_id, placement, units, game_date, queue_id):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            # Update user's current game --------- NO LONGER NEEDED -----------
            #cursor.execute('update users set current_game_id=NULL where puuid=%s', (puuid, ))

            # Update game record
            units += [None] * (13 - len(units)) # Extend units length to 10
            cursor.execute("update games set game_date=%s, placement=%s, unit1=%s, unit2=%s, unit3=%s, unit4=%s, unit5=%s, unit6=%s, unit7=%s, unit8=%s, unit9=%s, unit10=%s, unit11=%s, unit12=%s, unit13=%s, queue_id=%s where game_id=%s and puuid=%s", (game_date, placement, *units, queue_id, game_id, puuid, ))
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

    def get_augment_stats(self, augment):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("SELECT round(avg(placement), 1) as Placement, count(*) as Games FROM games WHERE aug1=%s OR aug2=%s OR aug3=%s OR aug4=%s", (*[augment]*4,))
            row = cursor.fetchone()
        print(row)
        if row is None:
            return None, None
        avp, games = row
        return avp, games
    
    def get_all_augment_stats(self):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            cursor.execute("""SELECT augment, AVG(placement), count(*) AS avg_placement
                FROM (
                    SELECT aug1 AS augment, placement FROM games
                    UNION ALL
                    SELECT aug2 AS augment, placement FROM games
                    UNION ALL
                    SELECT aug3 AS augment, placement FROM games
                    UNION ALL
                    SELECT aug4 AS augment, placement FROM games
                ) AS all_augments
                WHERE augment IS NOT NULL
                GROUP BY augment
                order by avg_placement asc""")
            rows = cursor.fetchall()
        print(rows)
        print(self.tft_stuff.augments)
        augment_stats = {row[0]: {"avg_placement": row[1], "count": row[2]} for row in rows}
        print(augment_stats)
        full_report = []
        for aug in self.tft_stuff.augments:
            stats = augment_stats.get(aug)
            if stats:
                full_report.append((aug, stats["avg_placement"], stats["count"]))
            else:
                full_report.append((aug, None, 0))  # Or 0.0, or 'N/A' as desired
        print('----------------------')
        print(full_report)
        return rows