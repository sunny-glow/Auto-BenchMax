#!/bin/bash

# Array of real code examples extracted from tool-calls.json files
code_snippets=(
  'import re
from datetime import datetime

raw_data = """Game ID: 2746
Date: 2025-04-01T02:10:00.000Z
Season: 2025
Postseason: false
Status: STATUS_FINAL
Venue: Dodger Stadium
Attendance: 50816
Matchup: Los Angeles Dodgers vs Atlanta Braves
Home Team: Los Angeles Dodgers (LAD)
League: National
Division: West
Runs: 6
Hits: 9
Errors: 0
Inning Scores: Inning 1: 2, Inning 2: 0, Inning 3: 2, Inning 4: 0, Inning 5: 1, Inning 6: 1, Inning 7: 0, Inning 8: 0
Away Team: Atlanta Braves (ATL)
League: National
Division: East
Runs: 1
Hits: 4
Errors: 0
Inning Scores: Inning 1: 0, Inning 2: 0, Inning 3: 0, Inning 4: 0, Inning 5: 0, Inning 6: 0, Inning 7: 0, Inning 8: 1, Inning 9: 0
Final Score: Los Angeles Dodgers 6 - 1 Atlanta Braves
-----
Game ID: 3224
Date: 2025-04-02T02:10:00.000Z
Season: 2025
Postseason: false
Status: STATUS_FINAL
Venue: Dodger Stadium
Attendance: 50182
Matchup: Los Angeles Dodgers vs Atlanta Braves
Home Team: Los Angeles Dodgers (LAD)
League: National
Division: West
Runs: 3
Hits: 5
Errors: 1
Inning Scores: Inning 1: 0, Inning 2: 0, Inning 3: 0, Inning 4: 0, Inning 5: 0, Inning 6: 3, Inning 7: 0, Inning 8: 0
Away Team: Atlanta Braves (ATL)
League: National
Division: East
Runs: 1
Hits: 3
Errors: 1
Inning Scores: Inning 1: 0, Inning 2: 1, Inning 3: 0, Inning 4: 0, Inning 5: 0, Inning 6: 0, Inning 7: 0, Inning 8: 0, Inning 9: 0
Final Score: Los Angeles Dodgers 3 - 1 Atlanta Braves"""

games = raw_data.strip().split("-----")
dodgers_games = []
for game in games:
    if "Los Angeles Dodgers" not in game:
        continue
    date_match = re.search(r"Date:\s([\d\-T:\.Z]+)", game)
    date = datetime.fromisoformat(date_match.group(1).replace("Z", "")) if date_match else None
    score_match = re.search(r"Final Score:\s(.+?)\s(\d+)\s-\s(\d+)\s(.+)", game)
    if score_match:
        team1, score1, score2, team2 = score_match.groups()
        score1, score2 = int(score1), int(score2)
        dodgers_home = "Home Team: Los Angeles Dodgers" in game
        dodgers_win = (team1 == "Los Angeles Dodgers" and score1 > score2) or (team2 == "Los Angeles Dodgers" and score2 > score1)
        dodgers_score = score1 if team1 == "Los Angeles Dodgers" else score2
        dodgers_games.append({"date": date, "home": dodgers_home, "win": dodgers_win, "runs": dodgers_score})

total_games = len(dodgers_games)
wins = sum(g["win"] for g in dodgers_games)
home_games = [g for g in dodgers_games if g["home"]]
home_wins = sum(g["win"] for g in home_games)
avg_runs = sum(g["runs"] for g in dodgers_games) / total_games if total_games > 0 else 0

print(f"Total Dodgers games in April 2025: {total_games}")
print(f"Overall Win Rate: {wins / total_games:.2%}")
print(f"Average Runs Scored: {avg_runs:.2f}")
print(f"Home Win Rate: {home_wins / len(home_games):.2%}")'

  'import pandas as pd

# Crear el DataFrame con los datos
data = [
    {"TotalSpent": 12713, "AudienceReached": 44517},
    {"TotalSpent": 10964, "AudienceReached": 17581},
    {"TotalSpent": 9820, "AudienceReached": 49545},
    {"TotalSpent": 8603, "AudienceReached": 43103},
    {"TotalSpent": 8428, "AudienceReached": 32881},
    {"TotalSpent": 6807, "AudienceReached": 42986},
    {"TotalSpent": 6274, "AudienceReached": 16050},
    {"TotalSpent": 5674, "AudienceReached": 45104},
    {"TotalSpent": 2961, "AudienceReached": 42947},
    {"TotalSpent": 1645, "AudienceReached": 4597},
    {"TotalSpent": 1601, "AudienceReached": 13892},
    {"TotalSpent": 891, "AudienceReached": 42289}
]

df = pd.DataFrame(data)

# Sumar cada columna
total_spent = df["TotalSpent"].sum()
total_audience = df["AudienceReached"].sum()

# Mostrar resultados
print(f"Total Spent: {total_spent}")
print(f"Total Audience Reached: {total_audience}")'

  'import sys
import subprocess

try:
    import pandas as pd
    import tabulate
except ImportError:
    # Install pandas and tabulate if not found
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "tabulate"])
    import pandas as pd
    import tabulate

data = [
    {"Service": "Haircut", "Price": 15.00},
    {"Service": "Beard Trim", "Price": 8.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Beard Trim", "Price": 7.00},
    {"Service": "Beard Trim", "Price": 9.00},
    {"Service": "Beard Trim", "Price": 8.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Beard Trim", "Price": 7.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Shave", "Price": 10.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Shave", "Price": 8.00},
    {"Service": "Shave", "Price": 10.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Shave", "Price": 10.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Beard Trim", "Price": 8.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Beard Trim", "Price": 8.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Beard Trim", "Price": 8.00},
    {"Service": "Shave", "Price": 10.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Shave", "Price": 10.00},
    {"Service": "Haircut", "Price": 12.00},
    {"Service": "Shave", "Price": 10.00},
    {"Service": "Haircut", "Price": 12.00}
]

df = pd.DataFrame(data)

average_prices_usd = df.groupby("Service")["Price"].mean().reset_index()
average_prices_usd.rename(columns={"Price": "Average_Price_USD"}, inplace=True)

usd_to_cad_rate = 1.43660
usd_to_eur_rate = 0.97114497

average_prices_usd["Average_Price_EUR"] = average_prices_usd["Average_Price_USD"] * usd_to_eur_rate
average_prices_usd["Average_Price_CAD"] = average_prices_usd["Average_Price_USD"] * usd_to_cad_rate

print("Average Price Per Service:")
print(average_prices_usd.to_markdown(index=False))'

  'import pandas as pd
import io

def create_bar_chart(percentage, width=20):
    num_pipes = int(percentage / 100 * width)
    num_spaces = width - num_pipes
    return "|" + "|" * num_pipes + " " * num_spaces + "|"

data = """Crime_ID,Date_Reported,Crime_Type,Location,Arrest_Made,Suspect_Age,Suspect_Gender,Victim_Age,Victim_Gender,Crime_Severity
CRIME679,2014-05-10,Theft,Shopping Mall,Yes,27,Male,35,Female,Moderate
CRIME680,2014-06-22,Assault,Park,No,19,Female,45,Male,Severe
CRIME681,2014-07-15,Burglary,Residential Area,Yes,35,Male,42,Female,High
CRIME682,2014-08-03,Robbery,Convenience Store,Yes,40,Male,28,Male,High
CRIME683,2014-09-18,Vandalism,Public Library,No,17,Male,55,Female,Low
CRIME684,2014-10-05,Fraud,Online,No,30,Female,40,Female,Moderate
CRIME685,2014-11-12,Drug Trafficking,Street,Yes,50,Male,29,Male,Severe
CRIME686,2014-12-09,Kidnapping,Residential Area,No,23,Male,18,Female,High
CRIME687,2015-01-20,Cybercrime,Financial Institution,Yes,28,Female,55,Male,Moderate
CRIME688,2016-09-02,Assault,Bar,Yes,29,Male,32,Female,Moderate
CRIME689,2016-10-15,Fraud,Telephone,No,45,Female,55,Female,Moderate
CRIME690,2016-11-09,Robbery,Bank,Yes,35,Male,40,Male,High
CRIME691,2016-12-18,Vandalism,School,No,18,Female,60,Male,Low
CRIME692,2017-01-07,Cybercrime,Social Media,Yes,22,Male,28,Female,Moderate
CRIME693,2017-02-03,Kidnapping,Parking Lot,No,40,Female,25,Female,High
CRIME694,2017-03-20,Theft,Gas Station,Yes,30,Male,35,Male,Moderate
CRIME695,2017-04-11,Drug Trafficking,Warehouse,Yes,38,Female,45,Male,Severe
CRIME696,2017-05-29,Arson,Residential Area,No,27,Male,50,Female,High
CRIME697,2017-06-14,Shoplifting,Department Store,Yes,20,Female,30,Male,Low
CRIME698,2017-07-22,Assault,Restaurant,Yes,32,Male,40,Female,Moderate"""

df = pd.read_csv(io.StringIO(data))

df["Date_Reported"] = pd.to_datetime(df["Date_Reported"])

df_2010s = df[(df["Date_Reported"].dt.year >= 2010) & (df["Date_Reported"].dt.year <= 2019)].copy()

gender_counts = df_2010s["Suspect_Gender"].value_counts()
most_offending_gender = gender_counts.index[0]

arrest_status_by_gender = df_2010s[df_2010s["Suspect_Gender"] == most_offending_gender]["Arrest_Made"].value_counts(normalize=True) * 100

print(f"\nPercentage of arrest status for the gender that commits most offenses ({most_offending_gender}):")
if "Yes" in arrest_status_by_gender:
    arrest_percent = arrest_status_by_gender["Yes"]
    print(f"{create_bar_chart(arrest_percent)} Arrested: {arrest_percent:.2f}%")
if "No" in arrest_status_by_gender:
    not_arrest_percent = arrest_status_by_gender["No"]
    print(f"{create_bar_chart(not_arrest_percent)} Not Arrested: {not_arrest_percent:.2f}%")

print(f"\nLocation where {most_offending_gender}s committed most offenses: \
      {df_2010s[df_2010s["Suspect_Gender"] == most_offending_gender]["Location"].value_counts().idxmax()}")'

  'brl_value = 420000
usd_brl_rate = 5.67290
usd_value = brl_value / usd_brl_rate

percentage = 0.30
result_usd = usd_value * percentage

final_value_divided_by_12 = result_usd / 12

print(f"Initial BRL value: {brl_value:.2f} BRL")
print(f"Converted to USD: {usd_value:.2f} USD")
print(f"30% of USD value: {result_usd:.2f} USD")
print(f"Final value divided by 12: {final_value_divided_by_12:.2f} USD")'

  'def convert_m2_to_sqft(area_m2):
    SQM_TO_SQFT_FACTOR = 10.7639
    return area_m2 * SQM_TO_SQFT_FACTOR

area_m2_str = "100,80m2"

area_m2_numeric_str = area_m2_str.replace("m2", "").replace(",", ".")
area_m2 = float(area_m2_numeric_str)

area_sqft = convert_m2_to_sqft(area_m2)

print(f"{area_m2_str} is equal to {area_sqft:.2f} sqft")'

  'import datetime

fecha = datetime.date(2022, 10, 23)
dia_semana = fecha.strftime("%A")
print(f"{fecha} was a {dia_semana}")'

  'import pandas as pd
from io import StringIO

data = """Total spent search video	Audience reached video
12105	46253
9697	27696
9195	36731
8781	46108
7300	16132
7236	40766
7224	44025
7218	2489
7130	42536
6865	19952
6802	9263
6474	42610
5846	27092
5334	43151
5159	38210
3555	11738
2509	42681
2464	4884
1738	13916
956	1813"""

df = pd.read_csv(StringIO(data), sep="\t")

total_spent = df["Total spent search video"].sum()
total_audience = df["Audience reached video"].sum()

print("Total spent:", total_spent)
print("Total audience reached:", total_audience)'

  'import pandas as pd
import io

csv_data = """Date,Location,Age Group,Gender,Food Type,Beverage Type,Quantity,Price ($),Total Price ($),Satisfaction (1-5),Comments
 5 Jan 2023,Restaurant,25-34,Male,Italian,Soda,2,6.5,13,4,Enjoyed the meal!
 10 Jan 2023,Cafe,18-24,Female,Vegetarian,Coffee,1,4.2,4.2,5,"Great ambiance, will come back!"
 15 Jan 2023,Bar,35-44,Female,Fast Food,Beer,3,15.75,47.25,3,Average experience
 20 Jan 2023,Home,45-54,Male,Mexican,Water,4,0,0,4,Homemade tacos were delicious!
 25 Jan 2023,Restaurant,55-64,Male,Seafood,Wine,2,35,70,5,Excellent service and food quality
 2 Feb 2023,Cafe,25-34,Female,Asian,Tea,1,3.75,3.75,4,Love their bubble tea!
 9 Feb 2023,Home,18-24,Male,Pizza,Soda,2,4.5,9,3,"Decent pizza, nothing special"
 14 Feb 2023,Restaurant,35-44,Female,Italian,Wine,2,40,80,5,Perfect date night spot
 22 Feb 2023,Bar,45-54,Male,Fast Food,Beer,3,18.25,54.75,2,Crowded and noisy
 28 Feb 2023,Home,55-64,Female,Mexican,Water,4,0,0,4,"Family dinner, everyone loved it"
 7 Mar 2023,Cafe,25-34,Male,Vegetarian,Coffee,1,4.2,4.2,5,Best coffee in town!
 12 Mar 2023,Restaurant,18-24,Female,Seafood,Wine,2,35,70,4,Good portion size
 17 Mar 2023,Bar,35-44,Female,Asian,Beer,3,15.75,47.25,3,Average experience
 25 Mar 2023,Home,45-54,Male,Italian,Water,4,0,0,4,Cooking at home tonight
 1 Apr 2023,Restaurant,55-64,Male,Pizza,Soda,2,6.5,13,5,"Great pizza, friendly staff"
 8 Apr 2023,Cafe,25-34,Female,Fast Food,Coffee,1,5,5,4,Quick bite before work
 13 Apr 2023,Home,18-24,Male,Mexican,Beer,3,12,36,3,"Tacos were okay, not exceptional"
 20 Apr 2023,Restaurant,35-44,Female,Asian,Tea,1,3.5,3.5,4,Authentic flavors
 27 Apr 2023,Bar,45-54,Male,Vegetarian,Wine,2,40,80,5,Expensive but worth it
 5 May 2023,Home,55-64,Female,Seafood,Water,4,0,0,4,Fresh seafood from the market"""

df = pd.read_csv(io.StringIO(csv_data))
df["Total Price ($)"] = pd.to_numeric(df["Total Price ($)"], errors="coerce")
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")

total_profit_by_food = df.groupby("Food Type")["Total Price ($)"].sum().sort_values(ascending=False)
total_quantity_by_food = df.groupby("Food Type")["Quantity"].sum().sort_values(ascending=False)
most_ordered_food_type = total_quantity_by_food.idxmax()
avg_quantity_by_gender_food = df.groupby(["Gender", "Food Type"])["Quantity"].mean().unstack()

print("Total Profit by Food Type ($):", total_profit_by_food)
print("Total quantity sold by food type:", total_quantity_by_food)
print("Most ordered food type:", most_ordered_food_type)
print("Average quantity by gender and Food type:", avg_quantity_by_gender_food)'

  'import re

stock_prices_string = """
{
  "meta": {
    "symbol": "AAPL",
    "interval": "1day",
    "currency": "USD",
    "exchange_timezone": "America/New_York",
    "exchange": "NASDAQ",
    "mic_code": "XNGS",
    "type": "Common Stock"
  },
  "values": [
    {
      "datetime": "2023-12-29",
      "open": "193.89999",
      "high": "194.39999",
      "low": "191.73000",
      "close": "192.53000",
      "volume": "42628800"
    },
    {
      "datetime": "2023-12-28",
      "open": "194.14000",
      "high": "194.66000",
      "low": "193.17000",
      "close": "193.58000",
      "volume": "34049900"
    },
    {
      "datetime": "2023-12-27",
      "open": "192.49001",
      "high": "193.5",
      "low": "191.089996",
      "close": "193.14999",
      "volume": "48087700"
    }
  ],
  "status": "ok"
}
"""

def stock_process(stock_prices_string):
    matches = re.findall(r".*?(open.*?)(\d{1,3}\.\d*).*?(close.*?)(\d{1,3}\.\d*).?", stock_prices_string, flags=re.DOTALL)
    n_trading_days = len(matches)
    profit = 0
    for _, op_price, _, cl_price in matches:
        if float(op_price) < float(cl_price):
            profit += 1
    
    print(f"The chance of profit buying on open and selling on close for apple stocks in 2023: {(profit/n_trading_days)*100:.4}%")
    return

stock_process(stock_prices_string)'
)

# Function to create JSON payload with proper escaping
create_e2b_call() {
    local code="$1"
    # Escape quotes, backslashes, tabs, and newlines for JSON
    local escaped_code=$(printf '%s' "$code" | \
        sed 's/\\/\\\\/g' | \
        sed 's/"/\\"/g' | \
        sed 's/	/\\t/g' | \
        awk '{printf "%s\\n", $0}' | \
        sed 's/\\n$//')
    echo "{\"tool_name\": \"e2b-server_run_code\", \"tool_args\": {\"code\": \"$escaped_code\"}}"
}

# Select a random code snippet
# random_index=$((RANDOM % ${#code_snippets[@]}))
random_index=3
selected_code="${code_snippets[$random_index]}"

# Create the JSON payload
json_payload=$(create_e2b_call "$selected_code")

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d "$json_payload" 