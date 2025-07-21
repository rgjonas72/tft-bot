import mysql.connector

def read_augments(file, tier):
    with open("augments/augments_silver.txt", "r", encoding="utf-8") as file:
        raw_text = file.read()

    # Now continue parsing it like before
    lines = raw_text.strip().splitlines()
    lines = [line.strip() for line in lines if line.strip()]
    lines = lines[3:]  # Skip the header lines

    augments = []
    for i in range(0, len(lines), 4):
        name = lines[i+1]
        #tier = lines[i+2]
        description = lines[i+3]
        
        augments.append({
            "name": name,
            "tier": tier,
            "description": description
        })

    return augments

silver = read_augments('augments/augments_silver', 'Silver')
gold = read_augments('augments/augments_gold', 'Gold')
pris = read_augments('augments/augments_prismatic', 'Prismatic')

def get_cnx():
    db_name = 'tft'
    cnx = mysql.connector.connect(user='root', password=open('tokens/db_pw.txt', 'r').readline().strip(),host='127.0.0.1', database=db_name)
    return cnx

def add_augs(cnx, aug_list):
    cnx.reconnect()
    with cnx.cursor() as cursor:
        for aug in aug_list:
            cursor.execute("insert into augments values ( %s, %s, %s)", (aug['name'], aug['tier'], aug['description'], ))
        cnx.commit()
cnx = get_cnx()
add_augs(cnx, silver)
add_augs(cnx, gold)
add_augs(cnx, pris)