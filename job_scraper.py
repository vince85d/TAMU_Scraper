import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import smtplib
import ssl
from email.message import EmailMessage
import os
import re

KEYWORDS = [
    "reptile", "amphibian", "herp", "turtle", "toad", "frog", "seal",
    "island", "whale", "cetacean", "tortoise", "spatial ecology",
    "predator", "tropical"
]

async def scrape_jobs():
    url = "https://jobs.rwfm.tamu.edu/search/"
    matching_jobs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)

        os.makedirs("screenshots", exist_ok=True)
        await page.screenshot(path="screenshots/page_initial.png", full_page=True)
        print("Screenshot saved: page_initial.png")

        try:
            await page.wait_for_selector("div.job-result", timeout=30000)
        except Exception as e:
            print(f"Wait for selector failed: {e}")
            await page.screenshot(path="screenshots/page_error.png", full_page=True)
            print("Screenshot saved: page_error.png")
            await browser.close()
            raise e  # Or return [] if you'd rather not crash

        job_elements = await page.query_selector_all("div.job-result")
        print(f"Scanned {len(job_elements)} job postings")

        for job in job_elements:
            title_el = await job.query_selector("h2")
            title = await title_el.inner_text() if title_el else "No Title"

            preview_el = await job.query_selector("div.job-info")
            preview = await preview_el.inner_text() if preview_el else ""

            link_el = await job.query_selector("a")
            link = await link_el.get_attribute("href") if link_el else ""

            job_text = f"{title} {preview}".lower()
            if any(re.search(rf"\b{kw}\b", job_text) for kw in KEYWORDS):
                matching_jobs.append({
                    "title": title.strip(),
                    "preview": preview.strip(),
                    "link": f"https://jobs.rwfm.tamu.edu{link.strip()}" if link else "N/A"
                })

        await browser.close()
    return matching_jobs

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
        job_text = "\n\n".join(f"{j['title']}\n{j['preview']}\n{j['link']}" for j in jobs)
        send_email("🦎 Daily TAMU Wildlife Jobs", f"Found {len(jobs)} matching job(s):\n\n{job_text}")
    else:
        send_email("🦎 Daily TAMU Wildlife Jobs", "No matching jobs found today.")

