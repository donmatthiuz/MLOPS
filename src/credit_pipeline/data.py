import pandas as pd

FILE_ID = "10S8JVFiLfCoRB9mb0NJG5YhITyXbH37B"
DOWNLOAD_URL = f"https://drive.google.com/uc?export=download&id={FILE_ID}"


def load_data(url: str = DOWNLOAD_URL) -> pd.DataFrame:
    """Descarga el dataset crudo de tarjetas de credito."""
    return pd.read_csv(url)
