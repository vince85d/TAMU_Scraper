import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import smtplib
import ssl
from email.message import EmailMessage
import os

KEYWORDS = [
    "reptile", "amphibian", "herp", "turtle", "toad", "frog",
    "seal", "island", "whale", "cetacean", "tortoise",
    "spatial ecology", "predator", "tropical"
]

async def scrape_jobs():
    url = "https://jobs.rwfm.tamu.edu/search/"
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        # Wait for job listings to load (wait for elements)
        await page.wait_for_selector("div.search-result.job-result")


        job_elements = await page.query_selector_all("div.search-result.job-result")
        print(f"[{datetime.now()}] Scanned {len(job_elements)} job postings")

        matches = []

        for job_el in job_elements:
            title_el = await job_el.query_selector("a")
            title = (await title_el.inner_text()).strip() if title_el else ""
            link = await title_el.get_attribute("href") if title_el else ""
            text = (await job_el.inner_text()).lower()

            for kw in KEYWORDS:
                if kw in text:
                    matches.append(f"{title}\nLink: {link}")
                    break

        await browser.close()
        print(f"[{datetime.now()}] Found {len(matches)} matching jobs")
        return matches

def send_email(subject, body):
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASS = os.getenv('EMAIL_PASS')
    EMAIL_TO = os.getenv('EMAIL_TO')

    msg = EmailMessage()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
    print(f"Email sent successfully to {EMAIL_TO}")

if __name__ == "__main__":
    jobs = asyncio.run(scrape_jobs())

    if jobs:
        job_text = "\n\n".join(jobs)
        send_email("🦎 Daily TAMU Wildlife Jobs", f"Found {len(jobs)} matching job(s):\n\n{job_text}")
    else:
        send_email("🦎 Daily TAMU Wildlife Jobs", "No matching jobs found today.")

        send_email(
            subject="🦎 Daily TAMU Wildlife Jobs",
            body="No matching jobs found today."
        )
