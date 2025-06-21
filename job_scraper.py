from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, StaleElementReferenceException
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from datetime import datetime, timedelta
import re
import time

class TAMUJobScraper:
    def __init__(self, email_config):
        self.base_url = "https://jobs.rwfm.tamu.edu/search/"
        self.keywords = [
            "reptile", "amphibian", "herp", "turtle", "toad", "frog",
            "seal", "island", "whale", "cetacean", "tortoise",
            "spatial ecology", "predator", "tropical", "hawaii",
            "bear", "lion", "snake", "lizard", "alligator", "crocodile", "chainsaw"
        ]
        self.email_config = email_config
        self.sent_jobs_file = "sent_jobs.json"
        self.sent_jobs = self.load_sent_jobs()
        self.driver = None

    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    def cleanup_driver(self):
        if self.driver:
            self.driver.quit()

    def load_sent_jobs(self):
        if os.path.exists(self.sent_jobs_file):
            try:
                with open(self.sent_jobs_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_sent_jobs(self):
        with open(self.sent_jobs_file, 'w') as f:
            json.dump(self.sent_jobs, f, indent=2)

    def scrape_jobs(self):
        jobs = []
        page_num = 1
        max_pages = 10

        try:
            self.setup_driver()

            while page_num <= max_pages:
                url = f"https://jobs.rwfm.tamu.edu/search/?PageSize=50&PageNum={page_num}#results"
                print(f"Fetching jobs from: {url}")

                try:
                    self.driver.get(url)
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(3)
                    job_elements = self.find_job_elements()

                    if not job_elements:
                        break

                    for i, job_element in enumerate(job_elements):
                        try:
                            if not self.is_job_recent(job_element.text, days=7):
                                continue

                            job_preview = self.extract_job_data_basic(job_element)
                            if not job_preview or not self.contains_keywords(job_preview):
                                continue

                            job_data = self.extract_job_data(job_element)
                            if job_data:
                                jobs.append(job_data)
                        except StaleElementReferenceException:
                            continue
                        except Exception as e:
                            print(f"Error processing job element: {e}")
                            continue

                    page_num += 1

                except (TimeoutException, WebDriverException):
                    break
        finally:
            self.cleanup_driver()

        return jobs

    def find_job_elements(self):
        selectors = [
            "div[class*='job']", "div[class*='posting']", "div[class*='listing']",
            "div[class*='position']", "article[class*='job']", "article[class*='posting']",
            "li[class*='job']", "li[class*='posting']", "tr[class*='job']",
            "div[data-job]", "a[href*='job']", "a[href*='posting']",
            "a[href*='position']", ".job", ".posting", ".listing",
            ".position", "[role='listitem']", ".search-result", ".result-item"
        ]

        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    return elements
            except:
                continue

        return []

    def extract_job_data_basic(self, element):
        try:
            link = element.find_element(By.TAG_NAME, "a")
            title = link.text.strip()
            url = link.get_attribute("href")
            return {
                'id': f"{title}_{url}".replace(' ', '_').replace('/', '_')[:200],
                'title': title,
                'url': url,
                'description': '',
                'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            print(f"Preview extraction error: {e}")
            return None

    def extract_job_data(self, element):
        try:
            # Scroll the element into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
    
            # Try to extract job URL from an <a> tag inside the element
            job_url = None
            try:
                clickable_link = element.find_element(By.TAG_NAME, "a")
                job_url = clickable_link.get_attribute("href")
            except NoSuchElementException:
                print("No <a> tag found in job element. Will try clicking the whole element.")
    
            original_window = self.driver.current_window_handle
    
            # Only open the link if it matched keywords
            if job_url:
                self.driver.execute_script("window.open(arguments[0]);", job_url)
            else:
                self.driver.execute_script("arguments[0].click();", element)
    
            WebDriverWait(self.driver, 10).until(EC.number_of_windows_to_be(2))
    
            for handle in self.driver.window_handles:
                if handle != original_window:
                    self.driver.switch_to.window(handle)
                    break
    
            time.sleep(2)
    
            url = self.driver.current_url
            title = self.driver.title.strip()
    
            try:
                body_elem = self.driver.find_element(By.TAG_NAME, "body")
                description = body_elem.text.strip()
            except:
                description = ""
    
            # Clean up
            self.driver.close()
            self.driver.switch_to.window(original_window)
    
            if not url:
                return None
    
            job_id = f"{title}_{url}".replace(' ', '_').replace('/', '_')[:200]
    
            return {
                'id': job_id,
                'title': title,
                'url': url,
                'description': description[:1000] + "..." if len(description) > 1000 else description,
                'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
        except Exception as e:
            print(f"Preview extraction error: {e}")
            return None

    def is_job_recent(self, job_text, days=7):
        date_match = re.search(r'Published:(\d{2}/\d{2}/\d{4})', job_text)
        if date_match:
            try:
                job_date = datetime.strptime(date_match.group(1), '%m/%d/%Y')
                return job_date >= datetime.now() - timedelta(days=days)
            except:
                pass

        days_ago_match = re.search(r'(\d+)\s+days?\s+ago', job_text, re.IGNORECASE)
        if days_ago_match:
            return int(days_ago_match.group(1)) <= days

        return True

    def contains_keywords(self, job_data):
        text = f"{job_data['title']} {job_data['description']}".lower()
        return any(keyword.lower() in text for keyword in self.keywords)

    def send_email(self, jobs):
        if not jobs:
            return

        subject = f"TAMU Job Alert - {len(jobs)} New Jobs Found ({datetime.now().strftime('%Y-%m-%d')})"
        html_body = self.create_email_body(jobs)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.email_config['from_email']
        msg['To'] = self.email_config['to_email']
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
            server.starttls()
            server.login(self.email_config['from_email'], self.email_config['password'])
            server.send_message(msg)

        for job in jobs:
            if job['id'] not in self.sent_jobs:
                self.sent_jobs.append(job['id'])
        self.save_sent_jobs()

    def create_email_body(self, jobs):
        html = f"""
        <html><body>
        <h2>TAMU Job Alert</h2>
        <p>Found {len(jobs)} new job(s):</p>
        """
        for job in jobs:
            html += f"""
            <div style='margin-bottom:20px;'>
                <strong>{job['title']}</strong><br>
                <a href="{job['url']}">View Posting</a><br>
                <p>{job['description'][:300]}{'...' if len(job['description']) > 300 else ''}</p>
                <em>Scraped: {job['scraped_date']}</em>
            </div>
            """
        html += "</body></html>"
        return html

    def run_daily_scrape(self):
        jobs = self.scrape_jobs()
        new_jobs = [job for job in jobs if job['id'] not in self.sent_jobs]
        if new_jobs:
            self.send_email(new_jobs)
        else:
            print("No new jobs found.")
        self.save_sent_jobs()

def main():
    smtp_port_str = os.environ.get('SMTP_PORT', '').strip()
    if not smtp_port_str:
        smtp_port = 587
    else:
        smtp_port = int(smtp_port_str)
    email_config = {
        'from_email': os.environ.get('FROM_EMAIL', '').strip(),
        'password': os.environ.get('EMAIL_PASSWORD', '').strip(),
        'to_email': os.environ.get('TO_EMAIL', '').strip(),
        'smtp_server': os.environ.get('SMTP_SERVER', 'smtp.gmail.com').strip(),
        'smtp_port': smtp_port
    }

    scraper = TAMUJobScraper(email_config)
    scraper.run_daily_scrape()

if __name__ == "__main__":
    main()


