import pandas as pd
import mysql.connector

CSV_PATH = "data/raw/master_raw_data.csv"

db_config = {
    "host": "hayabusa.proxy.rlwy.net",
    "port": 35394,
    "user": "root",
    "password": "RQVRuTuzkxCzQvLQWQSnUxCkDhZzYnUM",
    "database": "railway",
}

df = pd.read_csv(CSV_PATH)
df = df.fillna("")

max_length = df["nama_perusahaan"].str.len().max()

print("Panjang nama perusahaan terbesar:", max_length)

print(
    df.loc[
        df["nama_perusahaan"].str.len() > 255,
        ["nama_perusahaan"]
    ]
)

conn = mysql.connector.connect(**db_config)
cursor = conn.cursor()

sql = """
INSERT INTO jobs
(judul_posisi, nama_perusahaan, lokasi, pendidikan, link_lowongan, portal_sumber)
VALUES (%s, %s, %s, %s, %s, %s)
"""

for _, row in df.iterrows():
    cursor.execute(sql, (
        str(row["judul_posisi"]),
        str(row["nama_perusahaan"]),
        str(row["lokasi"]),
        str(row["pendidikan"]),
        str(row["link_lowongan"]),
        str(row["portal_sumber"]),
    ))

conn.commit()

print(f"Berhasil import {cursor.rowcount} data.")

cursor.close()
conn.close()