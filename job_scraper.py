import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import smtplib
import ssl
from email.message import EmailMessage
import os

# Keywords you're searching for in job titles
KEYWORDS = [
    "reptile", "amphibian", "herp", "turtle", "toad", "frog",
    "seal", "island", "whale", "cetacean", "tortoise",
    "spatial ecology", "predator", "tropical"
]

# Scrape jobs from the TAMU job board
def scrape_jobs():
    url = "https://jobs.rwfm.tamu.edu/search/"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    jobs = []
    for row in soup.select("tr.job"):
        cols = row.find_all("td")
        if len(cols) < 4:
            continue
        title = cols[0].text.strip()
        organization = cols[1].text.strip()
        location = cols[2].text.strip()
        deadline = cols[3].text.strip()
        description = title.lower()

        if any(k in description for k in KEYWORDS):
            link = row.find("a")["href"]
            jobs.append({
                "title": title,
                "organization": organization,
                "location": location,
                "deadline": deadline,
                "link": link
            })

    return jobs

# Save scraped jobs as a CSV file
def save_jobs(jobs, filename):
    df = pd.DataFrame
