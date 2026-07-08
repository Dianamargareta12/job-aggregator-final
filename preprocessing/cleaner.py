import pandas as pd

def clean_data(df):
    df = df.drop_duplicates()
    return df