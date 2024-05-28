import streamlit as st
import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageOps
from io import BytesIO
import matplotlib.pyplot as plt
from mplsoccer import PyPizza, FontManager, add_image
import unicodedata
import logging
import re
from bs4 import BeautifulSoup
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import os

logging.basicConfig(filename='player_selector.log', level=logging.DEBUG,
                    format='%(asctime)s:%(levelname)s:%(message)s')

# Load the data from the Excel sheet
def load_data():
    try:
        file_path = 'player_profiles.xlsx'  # Update the path if necessary
        df = pd.read_excel(file_path)
        df['Name'] = df['Name'].apply(lambda x: unicodedata.normalize('NFKD', x))
        logging.info("Loaded player profiles successfully.")
        return df
    except Exception as e:
        logging.exception("Error loading player_profiles.xlsx")
        return None

df = load_data()

if df is None:
    st.error("Failed to load player profiles.")
    st.stop()

# Function to generate player links
def link_generator(player_name):
    try:
        player_name = unicodedata.normalize('NFKD', player_name.strip())
        if player_name in df['Name'].values:
            return df[df['Name'] == player_name]['Link'].values[0]
        else:
            logging.error(f"Player {player_name} not found in the Excel file.")
            return None
    except Exception as e:
        logging.exception("Error in link_generator")
        return None

# Function to get player data
def get_players_data(player_name):
    try:
        player_stat_topics = ['Standard Stats', 'Shooting', 'Passing', 'Pass Types',
                              'Goal and Shot Creation', 'Defense', 'Possession', 'Miscellaneous Stats', 'Goalkeeping',
                              'Advanced Goalkeeping']

        link_to_player_profile = link_generator(player_name)
        if not link_to_player_profile:
            logging.error("Player not found!")
            return None, None, None

        try:
            html = urlopen(link_to_player_profile)
        except (HTTPError, URLError) as error:
            logging.error(f"Error fetching player profile: {error}")
            return None, None, None

        bs = BeautifulSoup(html, 'html.parser')

        media_item_div = bs.find('div', {'class': 'media-item'})
        if media_item_div and media_item_div.find('img'):
            player_image_url = media_item_div.find('img').attrs['src']
        else:
            player_image_url = 'https://via.placeholder.com/150'

        player_id = link_to_player_profile.split('/')[-2]
        scout_report_link = f"/en/players/{player_id}/scout/12192/{player_name.replace(' ', '-')}-Scouting-Report"

        try:
            scout_html = urlopen("https://fbref.com" + scout_report_link)
        except (HTTPError, URLError) as error:
            logging.error(f"Error fetching scout report: {error}")
            return None, None, None

        bs_scout_all = BeautifulSoup(scout_html, 'lxml')
        bs_scout = bs_scout_all.find('div', {'id': re.compile(r'div_scout_full_')})
        stat_tables_keys = bs_scout.find("table", {'id': re.compile(r'scout_full_')}).find_all('tr')
        stat_tables_p90Percentile = bs_scout.find("table", {'id': re.compile(r'scout_full_')}).find_all('td')

        player_stat_keys_raw = [list_th.find('th').get_text() for list_th in stat_tables_keys if
                                list_th.find('th').get_text() not in ("", "Statistic")]
        player_stat_values = [
            [stat_tables_p90Percentile[i].get_text(), stat_tables_p90Percentile[i + 1].get_text(strip=True)] for i in
            range(0, len(stat_tables_p90Percentile), 2) if stat_tables_p90Percentile[i].get_text()]

        player_stat_values = [stat for stat in player_stat_values if "" not in stat]
        player_stat_keys_raw = [stat for stat in player_stat_keys_raw if stat not in player_stat_topics]

        return player_image_url, player_stat_keys_raw, player_stat_values
    except Exception as e:
        logging.exception("Error in get_players_data")
        return None, None, None

# Function to show picture and stats
def show_picture(params, values, name_of_player, player_image_url):
    try:
        font_normal = FontManager()
        font_italic = FontManager()
        font_bold = FontManager()

        try:
            response = requests.get(player_image_url)
            image = Image.open(BytesIO(response.content))
        except (HTTPError, URLError, ValueError):
            image = Image.open('placeholder.jpg')

        mask = Image.new('L', image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + image.size, fill=255)

        masked_img = ImageOps.fit(image, mask.size, centering=(0.5, 0.5))
        masked_img.putalpha(mask)

        slice_colors = ["#bbEE90"] * 5 + ["#FF93ff"] * 5 + ["#FFCCCB"] * 5 + ["#87CEEB"] * 5
        text_colors = ["#000000"] * 20

        baker = PyPizza(
            params=params,
            background_color="#1C1C1C",
            straight_line_color="#000000",
            straight_line_lw=1,
            last_circle_color="#000000",
            last_circle_lw=1,
            other_circle_lw=0,
            inner_circle_size=11
        )

        fig, ax = baker.make_pizza(
            values,
            figsize=(10, 12),
            color_blank_space="same",
            slice_colors=slice_colors,
            value_colors=text_colors,
            value_bck_colors=slice_colors,
            blank_alpha=0.4,
            kwargs_slices=dict(
                edgecolor="#000000", zorder=2, linewidth=1
            ),
            kwargs_params=dict(
                color="#ffffff", fontsize=13,
                fontproperties=font_bold.prop, va="center"
            ),
            kwargs_values=dict(
                color="#ffffff", fontsize=11,
                fontproperties=font_normal.prop, zorder=3,
                bbox=dict(
                    edgecolor="#000000", facecolor="cornflowerblue",
                    boxstyle="round,pad=0.2", lw=1
                )
            )
        )

        fig.text(
            0.515, 0.945, name_of_player, size=27,
            ha="center", fontproperties=font_bold.prop, color="#ffffff"
        )

        fig.text(
            0.515, 0.925,
            "Percentile Rank vs Premier League Players in their Position for 2023/2024",
            size=13,
            ha="center", fontproperties=font_bold.prop, color="#ffffff"
        )

        fig.text(
            0.23, 0.9, " Standard         Passing         Possession           Defense", size=18,
            fontproperties=font_bold.prop, color="#ffffff"
        )

        fig.patches.extend([
            plt.Rectangle(
                (0.205, 0.9), 0.025, 0.0196, fill=True, color="#bbEE90",
                transform=fig.transFigure, figure=fig
            ),
            plt.Rectangle(
                (0.365, 0.9), 0.025, 0.0196, fill=True, color="#FF93ff",
                transform=fig.transFigure, figure=fig
            ),
            plt.Rectangle(
                (0.505, 0.9), 0.025, 0.0196, fill=True, color="#FFCCCB",
                transform=fig.transFigure, figure=fig
            ),
            plt.Rectangle(
                (0.695, 0.9), 0.025, 0.0196, fill=True, color="#87CEEB",
                transform=fig.transFigure, figure=fig
            ),
        ])

        ax_image = add_image(
            masked_img, fig, left=0.472, bottom=0.457, width=0.086, height=0.08, zorder=-1
        )

        st.pyplot(fig)

    except Exception as e:
        logging.exception("Error in show_picture")

# Function to get stats
def stats_gobbler(name_of_player, selected_values):
    try:
        data_scraper = get_players_data(name_of_player)
        if data_scraper[0] is None:
            return

        player_image_url, player_stat_keys_raw, player_stat_values = data_scraper
        params_raw = selected_values
        values = []

        params = [value.replace(' ', '\n') for value in selected_values]

        df_stats = pd.DataFrame({'Stat': player_stat_keys_raw, 'Values': player_stat_values})

        for name in params_raw:
            if name in df_stats['Stat'].tolist():
                value = df_stats.loc[df_stats['Stat'] == name, 'Values'].iloc[0]
                values.append(int(value[1]))

        show_picture(params, values, name_of_player, player_image_url)
    except Exception as e:
        logging.exception("Error in stats_gobbler")

# Streamlit interface
st.title("Player Profile and Stats Selector")

league = st.selectbox("Select a league:", sorted(df['League'].unique().tolist()))
teams = sorted(df[df['League'] == league]['Team'].unique().tolist())
team = st.selectbox("Select a team:", teams)
players = sorted(df[df['Team'] == team]['Name'].tolist())
player_name = st.selectbox("Select a player:", players)

additional_titles = ["Standard:", "Passing:", "Possession:", "Defense:"]
standard_options = [
    "Goals", "Assists", "Goals + Assists", "Non-Penalty Goals", "Penalty Kicks Made", "Penalty Kicks Attempted",
    "Yellow Cards", "Red Cards", "xG: Expected Goals", "npxG: Non-Penalty xG", "xAG: Exp. Assisted Goals",
    "npxG + xAG", "Progressive Carries", "Progressive Passes", "Progressive Passes Rec", "Goals", "Shots Total",
    "Shots on Target", "Shots on Target %", "Goals/Shot", "Goals/Shot on Target", "Average Shot Distance",
    "Shots from Free Kicks", "Penalty Kicks Made", "Penalty Kicks Attempted", "xG: Expected Goals", "npxG: Non-Penalty xG",
    "npxG/Shot", "Goals - xG", "Non-Penalty Goals - npxG"
]

passing_options = [
    "Passes Completed", "Passes Attempted", "Pass Completion %", "Total Passing Distance", "Progressive Passing Distance",
    "Passes Completed (Short)", "Passes Attempted (Short)", "Pass Completion % (Short)", "Passes Completed (Medium)",
    "Passes Attempted (Medium)", "Pass Completion % (Medium)", "Passes Completed (Long)", "Passes Attempted (Long)",
    "Pass Completion % (Long)", "Assists", "xAG: Exp. Assisted Goals", "xA: Expected Assists", "Key Passes",
    "Passes into Final Third", "Passes into Penalty Area", "Crosses into Penalty Area", "Progressive Passes",
    "Passes Attempted", "Live-ball Passes", "Dead-ball Passes", "Passes from Free Kicks", "Through Balls", "Switches",
    "Crosses", "Throw-ins Taken", "Corner Kicks", "Inswinging Corner Kicks", "Outswinging Corner Kicks",
    "Straight Corner Kicks", "Passes Completed", "Passes Offside", "Passes Blocked", "Shot-Creating Actions",
    "SCA (Live-ball Pass)", "SCA (Dead-ball Pass)", "SCA (Take-On)", "SCA (Shot)", "SCA (Fouls Drawn)", "SCA (Defensive Action)",
    "Goal-Creating Actions", "GCA (Live-ball Pass)", "GCA (Dead-ball Pass)", "GCA (Take-On)", "GCA (Shot)", "GCA (Fouls Drawn)",
    "GCA (Defensive Action)"
]

possession_options = [
    "Touches", "Touches (Def Pen)", "Touches (Def 3rd)", "Touches (Mid 3rd)", "Touches (Att 3rd)", "Touches (Att Pen)",
    "Touches (Live-Ball)", "Take-Ons Attempted", "Successful Take-Ons", "Successful Take-On %", "Times Tackled During Take-On",
    "Tackled During Take-On Percentage", "Carries", "Total Carrying Distance", "Progressive Carrying Distance", "Progressive Carries",
    "Carries into Final Third", "Carries into Penalty Area", "Miscontrols", "Dispossessed", "Passes Received",
    "Progressive Passes Rec", "Fouls Committed", "Fouls Drawn", "Offsides", "Crosses", "Interceptions", "Tackles Won",
    "Penalty Kicks Won", "Penalty Kicks Conceded", "Own Goals", "Ball Recoveries", "Aerials Won", "Aerials Lost", "% of Aerials Won"
]

defense_options = [
    "Tackles", "Tackles Won", "Tackles (Def 3rd)", "Tackles (Mid 3rd)", "Tackles (Att 3rd)", "Dribblers Tackled",
    "Dribbles Challenged", "% of Dribblers Tackled", "Challenges Lost", "Blocks", "Shots Blocked", "Passes Blocked",
    "Interceptions", "Tkl+Int", "Clearances", "Errors"
]

dropdown_options = {
    "Standard:": standard_options,
    "Passing:": passing_options,
    "Possession:": possession_options,
    "Defense:": defense_options
}

default_values = {
    "Standard:": ["Goals + Assists", "xG: Expected Goals", "Shots on Target %", "Progressive Carries", "Goals"],
    "Passing:": ["Pass Completion %", "Key Passes", "Shot-Creating Actions", "Assists", "xA: Expected Assists"],
    "Possession:": ["Successful Take-On %", "Crosses", "Passes Received", "Progressive Carries", "Total Carrying Distance"],
    "Defense:": ["Tkl+Int", "% of Dribblers Tackled", "Tackles Won", "Clearances", "Challenges Lost"]
}

selected_values = {}
for title in additional_titles:
    selected_values[title] = st.multiselect(f"Select {title[:-1]} stats:", dropdown_options[title], default=default_values[title])

if st.button("Submit"):
    all_selected_values = [val for sublist in selected_values.values() for val in sublist]
    stats_gobbler(player_name, all_selected_values)
