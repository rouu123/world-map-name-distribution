import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import pycountry
import logging
import os
import numpy as np
from matplotlib.patches import Patch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
BASE_URL = "https://forebears.io"
HEADERS = {'User-Agent': 'Mozilla/5.0'}  # To avoid blocking
NATURAL_EARTH_FILE = "D:/rt/indep/Deep learning/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp"

# Generate country list using pycountry
URL_COUNTRIES = {
    getattr(country, "common_name", country.name).lower().replace(" ", "-"): country.alpha_3 
    for country in pycountry.countries
}
# Replace faulty country names
COUNTRY_CORRECTION = {"bosnia-and-herzegovina":"bosnia","russian-federation":"russia","türkiye":"turkey",
"côte-d'ivoire":"ivory-coast","united-kingdom":"england","congo,-the-democratic-republic-of-the":"dr-congo",
"eswatini":"swaziland"}
for old, new in COUNTRY_CORRECTION.items():
    URL_COUNTRIES[new] = URL_COUNTRIES.pop(old)
def fetch_name_count(country: str, name_type: str) -> int:
    """
    Fetches the number of occurrences of a given name type (surname or forename) in a specified country.

    Parameters:
        country (str): The name of the country (in lowercase, as used in the URL).
        name_type (str): The type of name ('surnames' or 'forenames').

    Returns:
        int: The number of names found, or None if no valid number is found.
    """
    try:
        response = requests.get(f"{BASE_URL}/{country}/{name_type}", headers=HEADERS)
        response.raise_for_status()  # Raise an error for bad responses

        soup = BeautifulSoup(response.text, 'html.parser')
        first_p = soup.find('p')

        if first_p:
            match = re.search(r'\d{1,3}(?:,\d{3})*', first_p.text)  # Find first int with comma separators
            return int(match.group().replace(',', '')) if match else None
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {country}: {e}")
        return None

def create_name_distribution_df() -> pd.DataFrame:
    """
    Creates a DataFrame with surname and forename counts for a list of countries.

    Returns:
        pd.DataFrame: A DataFrame with columns: 'Alpha_3', 'Country', 'Surname_Count', 'Forename_Count', 'Color'.
    """
    data = {
        'Alpha_3': [],
        'Country': [],
        'Surname_Count': [],
        'Forename_Count': []
    }

    logging.info("Starting to fetch data for countries.")

    for country, alpha3 in URL_COUNTRIES.items():
        logging.info(f"Fetching data for country: {country} ({alpha3})")

        try:
            surname_count = fetch_name_count(country, "surnames")
            forename_count = fetch_name_count(country, "forenames")

            data['Alpha_3'].append(alpha3)
            data['Country'].append(country)
            data['Surname_Count'].append(surname_count)
            data['Forename_Count'].append(forename_count)

            logging.info(f"Data for {country} fetched: Surnames = {surname_count}, Forenames = {forename_count}")

        except Exception as e:
            logging.error(f"Error fetching data for {country}: {e}")
            # Add a default value if there's an error fetching the data
            data['Alpha_2'].append(alpha3)
            data['Country'].append(country)
            data['Surname_Count'].append(None)
            data['Forename_Count'].append(None)

    logging.info("Data fetching complete. Creating DataFrame.")

    return pd.DataFrame(data)


def data_manipulation(df: pd.DataFrame) -> pd.DataFrame:
    # Calculate the ratio between forenames and surnames
    df['Ratio'] = np.where(
        (df['Surname_Count'] > 0) & (df['Forename_Count'] > 0),
        df['Forename_Count'] / df['Surname_Count'],
        np.nan  # Default ratio if either count is 0 or missing
    )

    # Define color levels
    ratio_colors = ["#3b7b80", "#68999d", "#89afb4", "#f1a85f", "#ee9133", "#db780b"]

    # Define the bins for the ratio values
    bins = [0, 0.25, 0.5, 1, 1.5, 2, float('inf')]

    # Assign colors based on the ratio
    df['Color'] = pd.cut(df['Ratio'], bins=bins, labels=ratio_colors, include_lowest=True)

    # Add "#ffffff" as a new category to the 'Color' column
    df['Color'] = df['Color'].cat.add_categories("#ffffff")

    # Fill missing color values with white
    df['Color'] = df['Color'].fillna("#ffffff")

    return df


import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

def plot_world_map(df: pd.DataFrame):
    """
    Plots a world map highlighting countries based on the DataFrame.
    
    Parameters:
        df (pd.DataFrame): A DataFrame containing 'Alpha_3', 'Surname_Count', 
                          'Forename_Count', and 'Color' columns with hex color codes.
    """
    # Load a world map dataset
    world = gpd.read_file(NATURAL_EARTH_FILE)
    
    # Merge the DataFrame with the world map data
    world = world.merge(df, how='left', left_on='ISO_A3_EH', right_on='Alpha_3')
    
    # Create the figure and axis with a larger size
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Set the background color
    fig.patch.set_facecolor('#F0F8FF')
    ax.set_facecolor('#F0F8FF')
    
    # Plot the map using color column directly (hex codes)
    base = world.plot(color=world['Color'].fillna('#ffffff'),  # White for missing data
                     ax=ax)
    
    # Add country boundaries
    world.boundary.plot(ax=ax, linewidth=0.3, color='white', alpha=0.2)
    
    # Remove axes
    ax.axis('off')
    
    # Add title
    plt.title('Global Distribution of Names: Surnames vs Forenames',
             pad=20,
             size=16,
             fontweight='bold')
    
    # Add description
    plt.figtext(0.02, 0.02,
                'Data source: forebears.io\n'
                'Color intensity indicates relative prevalence',
                fontsize=8,
                alpha=0.7)
    
    # Define the color levels and their meanings
    color_levels = ["#3b7b80", "#68999d", "#89afb4", "#f1a85f", "#ee9133", "#db780b"]
    color_meanings = [
        "Many more surnames",
        "More surnames",
        "Moderatly more surnames",
        "Moderatly more forenames",
        "More forenames",
        "Many more forenames"
    ]
    
    # Create legend elements
    legend_elements = [Patch(facecolor=color, label=meaning) for color, meaning in zip(color_levels, color_meanings)]
    
    # Add a legend for the color levels
    ax.legend(handles=legend_elements, 
              loc='lower right', 
              bbox_to_anchor=(0.84, 0),  # Adjust these values to move the legend
              fontsize=10, 
              title='Color Legend', 
              title_fontsize=12)
    # Adjust layout
    plt.tight_layout()
    plt.savefig('world_map.png', bbox_inches='tight', dpi=300)
    plt.show()

def main():
    # Check if data.csv exists
    if os.path.exists("data.csv"):
        print("Loading existing data from data.csv...")
        df = pd.read_csv("data.csv", index_col=0)
    else:
        print("No existing data found. Creating new name distribution DataFrame...")
        df = create_name_distribution_df()
        df.to_csv("data.csv")
        print("Data saved to data.csv")

    # Plot the world map
    data_manipulation(df)
    plot_world_map(df)

if __name__ == "__main__":
    main()