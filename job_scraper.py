import requests
from bs4 import BeautifulSoup
from datetime import datetime
import smtplib
import ssl
from email.message import EmailMessage
import os

def scrape_jobs():
    url = "https://jobs.rwfm.tamu.edu/search/"
    keywords = [
        "reptile", "amphibian", "herp", "turtle", "toad", "frog", "seal", "island",
        "whale", "cetacean", "tortoise", "spatial ecology", "predator", "tropical"
    ]

    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    postings = soup.find_all("li", class_="search-result")
    print(f"[{datetime.now()}] Scanned {len(postings)} job postings")

    matches = []

    for posting in postings:
        title_tag = posting.find("a")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link = title_tag["href"]
        summary = posting.get_text(separator=" ", strip=True).lower()

        for kw in keywords:
            if kw.lower() in summary:
                matches.append(f"{title}\nLink: {link}")
                break  # Stop checking more keywords if one matched

    print(f"[{datetime.now()}] Found {len(matches)} matching jobs")
    return matches


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


if __name__ == "__main__":
    job_listings = scrape_jobs()

    if job_listings:
        job_text = "\n\n".join(job_listings)
        send_email(
            subject="🦎 Daily TAMU Wildlife Jobs",
            body=f"Found {len(job_listings)} matching job(s):\n\n{job_text}"
        )
    else:
        send_email(
            subject="🦎 Daily TAMU Wildlife Jobs",
            body="No matching jobs found today."
        )
