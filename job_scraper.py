import smtplib
import ssl
from email.message import EmailMessage
import os

def send_email(subject, body):
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_TO = os.getenv('EMAIL_TO')

    print(f"DEBUG: Sending from {EMAIL_USER} to {EMAIL_TO}")
    print(f"DEBUG: Password length = {len(EMAIL_PASS) if EMAIL_PASS else 'None'}")

    msg = EmailMessage()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = subject
    msg.set_content(body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print(f"Email sent successfully to {EMAIL_TO}")
    except Exception as e:
        print(f"Failed to send email: {e}")
        
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
if __name__ == "__main__":
    # Run your scraper function
    job_listings = scrape_jobs()

    if job_listings:
        job_text = "\n\n".join(job_listings)
        send_email(
            subject="🦎 Daily TAMU Wildlife Jobs",
            body=f"Found {len(job_listings)} job(s):\n\n{job_text}"
        )
    else:
        send_email(
            subject="🦎 Daily TAMU Wildlife Jobs",
            body="No matching jobs found today."
        )




# Save scraped jobs as a CSV file
def save_jobs(jobs, filename):
    df = pd.DataFrame
