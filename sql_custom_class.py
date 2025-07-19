import mysql.connector
import pandas as pd
import discord
from pagination import Pagination
from typing import List

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

    def get_augment_stats(self, augment, user):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            if user:
                cursor.execute("SELECT round(avg(placement), 1) as Placement, count(*) as Games FROM games WHERE (aug1=%s OR aug2=%s OR aug3=%s OR aug4=%s) and puuid in (select puuid from users where disc_id=%s)", (*[augment]*4, user.id, ))
            else:
                cursor.execute("SELECT round(avg(placement), 1) as Placement, count(*) as Games FROM games WHERE aug1=%s OR aug2=%s OR aug3=%s OR aug4=%s", (*[augment]*4,))
            row = cursor.fetchone()
        print(row)
        if row is None:
            return None, None
        avp, games = row
        return avp, games

    def get_augment_stats_filter(self, augment, include_users, exclude_users):
        self.cnx.reconnect()
        if len(include_users) > 0:
            placeholders = ','.join(['%s'] * len(include_users))
            filter_str = f"AND (puuid in (select puuid from users where disc_id in ({placeholders})))"
            params = (*[augment]*4, *include_users, )
        elif len(exclude_users) > 0:
            placeholders = ','.join(['%s'] * len(exclude_users))
            filter_str = f"AND (puuid not in (select puuid from users where disc_id in ({placeholders})))"
            params = (*[augment]*4, *exclude_users, )
        else:
            filter_str = ""
            params = params = (*[augment]*4, )
        print(filter_str)
        print(params)
        with self.cnx.cursor() as cursor:
            cursor.execute(f"SELECT round(avg(placement), 1) as Placement, count(*) as Games FROM games WHERE (aug1=%s OR aug2=%s OR aug3=%s OR aug4=%s) {filter_str}", params)
            row = cursor.fetchone()
        print(row)
        if row is None:
            return None, None
        avp, games = row
        return avp, games
    
    def get_all_augment_stats(self, interaction: discord.Interaction, user):
        self.cnx.reconnect()
        with self.cnx.cursor() as cursor:
            if user:
                cursor.execute("""SELECT augment, AVG(placement), count(*) AS avg_placement
                    FROM (
                        SELECT aug1 AS augment, placement FROM games where puuid in (select puuid from users where disc_id=%s)
                        UNION ALL
                        SELECT aug2 AS augment, placement FROM games where puuid in (select puuid from users where disc_id=%s)
                        UNION ALL
                        SELECT aug3 AS augment, placement FROM games where puuid in (select puuid from users where disc_id=%s)
                        UNION ALL
                        SELECT aug4 AS augment, placement FROM games where puuid in (select puuid from users where disc_id=%s)
                    ) AS all_augments
                    WHERE augment IS NOT NULL
                    GROUP BY augment
                order by avg_placement asc""", (*[user.id]*4,))
            else:
                cursor.execute("""SELECT augment, round(AVG(placement), 1), count(*) AS avg_placement
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
        augment_stats = {row[0]: {"avg_placement": row[1], "count": row[2]} for row in rows}
        full_report = []
        for aug in self.tft_stuff.augments:
            stats = augment_stats.get(aug)
            if stats:
                full_report.append((aug, stats["avg_placement"], stats["count"]))
            else:
                full_report.append((aug, None, 0))  # Or 0.0, or 'N/A' as desired
        
        df = pd.DataFrame(full_report, columns=["Augment", "AVP", "Games"])
        df = df.sort_values(by=["AVP", "Games", "Augment"], na_position='last')
        df["AVP"] = df["AVP"].fillna("N/A")
        pagination = self.get_all_augments_embed(df, interaction, user)
        return pagination
    
    def get_all_augment_stats_filter(self, interaction: discord.Interaction, included_users, excluded_users, client):
        self.cnx.reconnect()
        if len(included_users) > 0:
            placeholders = ','.join(['%s'] * len(included_users))
            filter_str = f"AND (puuid in (select puuid from users where disc_id in ({placeholders})))"
            params = (*(included_users)*4, )
        elif len(excluded_users) > 0:
            placeholders = ','.join(['%s'] * len(excluded_users))
            filter_str = f"AND (puuid not in (select puuid from users where disc_id in ({placeholders})))"
            params = (*(excluded_users)*4, )
        else:
            filter_str = ""
            params = None


        print(params)
        with self.cnx.cursor() as cursor:
            cursor.execute(f"""SELECT augment, AVG(placement), count(*) AS avg_placement
                    FROM (
                        SELECT aug1 AS augment, placement FROM games where true {filter_str} 
                        UNION ALL
                        SELECT aug2 AS augment, placement FROM games where true {filter_str} 
                        UNION ALL
                        SELECT aug3 AS augment, placement FROM games where true {filter_str} 
                        UNION ALL
                        SELECT aug4 AS augment, placement FROM games where true {filter_str} 
                    ) AS all_augments
                    WHERE augment IS NOT NULL
                    GROUP BY augment
                order by avg_placement asc""", params)
            rows = cursor.fetchall()
        augment_stats = {row[0]: {"avg_placement": row[1], "count": row[2]} for row in rows}
        full_report = []
        for aug in self.tft_stuff.augments:
            stats = augment_stats.get(aug)
            if stats:
                full_report.append((aug, stats["avg_placement"], stats["count"]))
            else:
                full_report.append((aug, None, 0))  # Or 0.0, or 'N/A' as desired
        
        df = pd.DataFrame(full_report, columns=["Augment", "AVP", "Games"])
        df = df.sort_values(by=["AVP", "Games", "Augment"], na_position='last')
        df["AVP"] = df["AVP"].fillna("N/A")
        pagination = self.get_all_augments_embed_filter(df, interaction, included_users, excluded_users, client)
        return pagination
    
    def get_all_augments_embed(self, df, interaction: discord.Interaction, user):
        ar = df.to_numpy()
        """
        out = ["{: <25} {: <4} {: <4}".format(*df.columns)]
        for row in ar:
            print(row)
            out.append("{: <25} {: <4} {: <4}".format(*row))
        header, data = '\n'.join(out).split('\n', 1)
        """
        header="{: <25} {: <4} {: <4}".format(*df.columns)
        #print(header, data)
        #embed = discord.Embed(color=0x151a26, description=f"```yaml\n{header}``` ```\n{data}```")
        #data = out[1:]
        num_elements = 25
        async def get_page(page: int):
            title = "Augment Stats"
            if user:
                title += f' for {user.name}'
            emb = discord.Embed(title=title, description=f"```yaml\n{header}``` ```\n")
            offset = (page-1) * num_elements
            for d in ar[offset:offset+num_elements]:
                emb.description += "{: <25} {: <4} {: <4}\n".format(*d)
            emb.description += "```"
            #emb.set_author(name=f"Requested by {interaction.user}")
            n = Pagination.compute_total_pages(len(ar), num_elements)
            emb.set_footer(text=f"Page {page} from {n}")
            return emb, n

        return Pagination(interaction, get_page)
    
    def get_all_augments_embed_filter(self, df, interaction: discord.Interaction, included_users, excluded_users, client):
        ar = df.to_numpy()
        """
        out = ["{: <25} {: <4} {: <4}".format(*df.columns)]
        for row in ar:
            print(row)
            out.append("{: <25} {: <4} {: <4}".format(*row))
        header, data = '\n'.join(out).split('\n', 1)
        """
        header="{: <25} {: <4} {: <4}".format(*df.columns)
        #print(header, data)
        #embed = discord.Embed(color=0x151a26, description=f"```yaml\n{header}``` ```\n{data}```")
        #data = out[1:]
        num_elements = 25
        async def get_page(page: int):
            title = "Augment Stats"
            print(included_users)
            print(excluded_users)
            if len(included_users) > 0:
                title += ' | Includes data for: ' + ', '.join([client.get_user(disc_id).name for disc_id in included_users])
            elif len(excluded_users) > 0:
                title += ' | Excludes data for: ' + ', '.join([client.get_user(disc_id).name for disc_id in excluded_users])
            #if user:
            #    title += f' for {user.name}'
            emb = discord.Embed(title=title, description=f"```yaml\n{header}``` ```\n")
            offset = (page-1) * num_elements
            for d in ar[offset:offset+num_elements]:
                emb.description += "{: <25} {: <4} {: <4}\n".format(*d)
            emb.description += "```"
            #emb.set_author(name=f"Requested by {interaction.user}")
            n = Pagination.compute_total_pages(len(ar), num_elements)
            emb.set_footer(text=f"Page {page} from {n}")
            return emb, n

        return Pagination(interaction, get_page)

class IncludeSelect(discord.ui.Select):
    def __init__(self, members: List[discord.Member]):
        options = [
            discord.SelectOption(label=member.name, value=str(member.id))
            for member in members[:25]
        ]
        super().__init__(
            placeholder="Users to INCLUDE",
            min_values=0,
            max_values=min(5, len(options)),
            options=options,
            custom_id="include_select"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.included_users = self.values
        await interaction.response.defer()  # No message, just acknowledge

class ExcludeSelect(discord.ui.Select):
    def __init__(self, members: List[discord.Member]):
        options = [
            discord.SelectOption(label=member.name, value=str(member.id))
            for member in members[:25]
        ]
        super().__init__(
            placeholder="Users to EXCLUDE",
            min_values=0,
            max_values=min(5, len(options)),
            options=options,
            custom_id="exclude_select"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.excluded_users = self.values
        await interaction.response.defer()  # No message, just acknowledge

class FilterView(discord.ui.View):
    def __init__(self, members: List[discord.Member], augment, client, sql_stuff, tft_stuff):
        super().__init__(timeout=120)
        self.sql_stuff = sql_stuff
        self.tft_stuff = tft_stuff
        self.augment = augment
        self.client = client
        self.included_users = []
        self.excluded_users = []
        self.members_dict = {str(m.id): m for m in members}

        self.add_item(IncludeSelect(members))
        self.add_item(ExcludeSelect(members))

    @discord.ui.button(label="Submit", style=discord.ButtonStyle.green)
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        included_mentions = [int(self.members_dict[uid].mention.strip('<@!>')) for uid in self.included_users]
        excluded_mentions = [int(self.members_dict[uid].mention.strip('<@!>')) for uid in self.excluded_users]

        print(self.augment)
        if self.augment:
            avp, games=self.sql_stuff.get_augment_stats_filter(self.augment, included_mentions, excluded_mentions)
            #embed = tft_stuff.create_augment_stats_pic(augment, avp)
            #await interaction.response.send_message(file=discord.File(fp=embed, filename='image.png'))
            embed = self.tft_stuff.get_augment_stats_embed_filter(self.augment, avp, games, included_mentions, excluded_mentions, self.client)
            await interaction.response.send_message(embed=embed)
        else:
            #embed = sql_stuff.get_all_augment_stats()
            pagination = self.sql_stuff.get_all_augment_stats_filter(interaction, included_mentions, excluded_mentions, self.client)
            await pagination.navegate()
        '''
        # You can now use these lists however you like
        await interaction.response.send_message(
            f"✅ Included: {', '.join(included_mentions) or 'None'}\n❌ Excluded: {', '.join(excluded_mentions) or 'None'}",
            ephemeral=True
        )
        '''
        self.stop()  # Optional: ends the view
