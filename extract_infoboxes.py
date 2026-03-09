import requests
from bs4 import BeautifulSoup
import csv
import os
import time

# create folder
os.makedirs("infobox_html", exist_ok=True)

# read countries from CSV
countries = []

with open("countries.csv", newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    for row in reader:
        countries.append(row["country"])

headers = {
    "User-Agent": "Mozilla/5.0"
}

for country in countries:

    page = country.replace(" ", "_")
    url = f"https://en.wikipedia.org/wiki/{page}"

    print("Processing:", country)

    try:
        r = requests.get(url, headers=headers)

        if r.status_code != 200:
            print("Failed:", country)
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        infobox = soup.find("table", {"class": "infobox"})

        if infobox:

            filepath = f"infobox_html/{country}.html"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(str(infobox))

            print("Saved:", country)

        else:
            print("No infobox:", country)

        time.sleep(1)

    except Exception as e:
        print("Error:", country, e)