import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

class TAMUJobScraper:
    def __init__(self, email_config):
        self.base_url = "https://jobs.rwfm.tamu.edu/search/"
        self.keywords = [
            "reptile", "amphibian", "herp", "turtle", "toad", "frog", 
            "seal", "island", "whale", "cetacean", "tortoise", 
            "spatial ecology", "predator", "tropical", "hawaii", 
            "bear", "lion", "snake", "lizard", "alligator", "crocodile"
        ]
        self.email_config = email_config
        self.sent_jobs_file = "sent_jobs.json"
        self.sent_jobs = self.load_sent_jobs()
        
    def setup_selenium_driver(self):
        """Setup Selenium WebDriver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        return webdriver.Chrome(options=chrome_options)
        
    def load_sent_jobs(self):
        """Load previously sent job IDs to avoid duplicates"""
        if os.path.exists(self.sent_jobs_file):
            try:
                with open(self.sent_jobs_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        return []
    
    def save_sent_jobs(self):
        """Save sent job IDs"""
        try:
            with open(self.sent_jobs_file, 'w') as f:
                json.dump(self.sent_jobs, f, indent=2)
        except Exception as e:
            print(f"Error saving sent jobs: {e}")
    
    def scrape_jobs(self):
        jobs = []
        driver = self.setup_selenium_driver()
        
        try:
            page_num = 1
            max_pages = 10  # safety limit
            
            while True:
                url = f"https://jobs.rwfm.tamu.edu/search/?PageSize=50&PageNum={page_num}#results"
                print(f"Fetching jobs from: {url}")
                
                driver.get(url)
                
                # Wait for page to load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Get page source and parse with BeautifulSoup for consistency
                soup = BeautifulSoup(driver.page_source, 'html.parser')
        
                # Your existing logic to find job_elements
                job_elements = []
                selectors = [
                    {'tag': 'div', 'class': re.compile(r'job|posting|listing|position', re.I)},
                    {'tag': 'article', 'class': re.compile(r'job|posting|listing|position', re.I)},
                    {'tag': 'li', 'class': re.compile(r'job|posting|listing|position', re.I)},
                    {'tag': 'tr', 'class': re.compile(r'job|posting|listing|position', re.I)},
                    {'tag': 'div', 'attrs': {'data-job': True}},
                    {'tag': 'a', 'href': re.compile(r'job|posting|position', re.I)},
                ]
                
                for selector in selectors:
                    if 'class' in selector:
                        elements = soup.find_all(selector['tag'], class_=selector['class'])
                    elif 'href' in selector:
                        elements = soup.find_all(selector['tag'], href=selector['href'])  
                    elif 'attrs' in selector:
                        elements = soup.find_all(selector['tag'], attrs=selector['attrs'])
                    else:
                        elements = soup.find_all(selector['tag'])
                    if elements:
                        job_elements.extend(elements)
                        print(f"Found {len(elements)} elements with selector: {selector}")
                        break
        
                if not job_elements:
                    print(f"No jobs found on page {page_num}. Stopping pagination.")
                    break
        
                print(f"Processing {len(job_elements)} job elements on page {page_num}...")
                
                for i, job_element in enumerate(job_elements):
                    try:
                        # Check if job is recent before processing it
                        job_text = job_element.get_text()
                        if not self.is_job_recent(job_text, days=7):
                            continue  # Skip this job if it's older than 7 days
                            
                        job_data = self.extract_job_data_with_selenium(job_element, driver)
                        if job_data and self.contains_keywords(job_data):
                            jobs.append(job_data)
                            print(f"Job {i+1} matches keywords: {job_data['title']}")
                    except Exception as e:
                        print(f"Error processing job element {i+1}: {e}")
                        continue
        
                page_num += 1
                if page_num > max_pages:
                    print("Reached maximum page limit, stopping.")
                    break
                    
        finally:
            driver.quit()
    
        print(f"Found {len(jobs)} jobs matching keywords across all pages")
        return jobs
    
    def extract_job_data_with_selenium(self, element, driver):
        """Extract job data from HTML element using Selenium for click-through"""
        try:
            # Extract basic info from listing page first
            title = None
            title_selectors = [
                {'tag': ['h1', 'h2', 'h3', 'h4'], 'class': re.compile(r'title|heading|job-title', re.I)},
                {'tag': 'a', 'class': re.compile(r'title|heading|job-title', re.I)},
                {'tag': ['h1', 'h2', 'h3', 'h4']},
                {'tag': 'a', 'href': True}
            ]
            
            for selector in title_selectors:
                if 'class' in selector:
                    title_elem = element.find(selector['tag'], class_=selector['class'])
                elif 'href' in selector:
                    title_elem = element.find(selector['tag'], href=True)
                else:
                    title_elem = element.find(selector['tag'])
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            if not title:
                if element.name == 'a':
                    title = element.get_text(strip=True)
                else:
                    title = element.get_text(strip=True)[:100]
            
            if not title or len(title) < 3:
                return None
            
            # Find the clickable element for this job
            clickable_element = None
            href = None
            
            if element.name == 'a' and element.get('href'):
                href = element['href']
            else:
                link_elem = element.find('a', href=True)
                if link_elem:
                    href = link_elem['href']
            
            if not href:
                return None
            
            # Find the corresponding clickable element in Selenium
            try:
                # Try to find the element by href attribute
                clickable_element = driver.find_element(By.XPATH, f"//a[@href='{href}']")
            except:
                try:
                    # Try to find by partial text match
                    clickable_element = driver.find_element(By.PARTIAL_LINK_TEXT, title[:50])
                except:
                    print(f"Could not find clickable element for job: {title}")
                    # Fall back to original URL construction
                    base_url = "https://jobs.rwfm.tamu.edu/"
                    url = urljoin(base_url, href.strip())
                    return {
                        'id': f"{title}_{url}".replace(' ', '_').replace('/', '_')[:200],
                        'title': title,
                        'url': url,
                        'description': element.get_text(strip=True)[:1000],
                        'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
            
            # Click the job to navigate to individual posting
            original_url = driver.current_url
            try:
                # Scroll element into view and click
                driver.execute_script("arguments[0].scrollIntoView(true);", clickable_element)
                time.sleep(0.5)  # Brief pause for scroll
                clickable_element.click()
                
                # Wait for navigation to complete
                WebDriverWait(driver, 10).until(
                    lambda d: d.current_url != original_url
                )
                
                # Get the actual job posting URL
                job_url = driver.current_url
                
                # Extract additional details from job posting page
                description = ""
                try:
                    # Wait for job details to load
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    
                    # Try to find job description on the detail page
                    description_selectors = [
                        (By.CLASS_NAME, "job-description"),
                        (By.CLASS_NAME, "description"),
                        (By.CLASS_NAME, "content"),
                        (By.CLASS_NAME, "details"),
                        (By.TAG_NAME, "main"),
                        (By.TAG_NAME, "article")
                    ]
                    
                    for by_type, selector in description_selectors:
                        try:
                            desc_element = driver.find_element(by_type, selector)
                            description = desc_element.text.strip()
                            if description and len(description) > 50:  # Only use if substantial
                                break
                        except:
                            continue
                    
                    # If no good description found, use page body text
                    if not description or len(description) < 50:
                        body_element = driver.find_element(By.TAG_NAME, "body")
                        description = body_element.text.strip()
                
                except Exception as e:
                    print(f"Error extracting description: {e}")
                    description = "Description not available"
                
                # Go back to listings page for next iteration
                driver.back()
                
                # Wait for listings page to reload
                WebDriverWait(driver, 10).until(
                    lambda d: d.current_url == original_url
                )
                
                # Limit description length
                if len(description) > 1000:
                    description = description[:1000] + "..."
                
                # Create unique ID for job
                job_id = f"{title}_{job_url}".replace(' ', '_').replace('/', '_')[:200]
                
                return {
                    'id': job_id,
                    'title': title,
                    'url': job_url,  # This is now the actual job posting URL!
                    'description': description,
                    'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
            except Exception as e:
                print(f"Error clicking through to job: {e}")
                # Fall back to original URL construction if click fails
                base_url = "https://jobs.rwfm.tamu.edu/"
                url = urljoin(base_url, href.strip())
                return {
                    'id': f"{title}_{url}".replace(' ', '_').replace('/', '_')[:200],
                    'title': title,
                    'url': url,
                    'description': element.get_text(strip=True)[:1000],
                    'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            
        except Exception as e:
            print(f"Error extracting job data: {str(e)}")
            return None

    def is_job_recent(self, job_text, days=7):
        """Check if job was posted in the last N days"""
        # Look for "Published:MM/DD/YYYY" pattern
        date_match = re.search(r'Published:(\d{2}/\d{2}/\d{4})', job_text)
        if date_match:
            try:
                job_date = datetime.strptime(date_match.group(1), '%m/%d/%Y')
                cutoff_date = datetime.now() - timedelta(days=days)
                return job_date >= cutoff_date
            except ValueError:
                pass
        
        # Look for "X days ago"
        days_ago_match = re.search(r'(\d+)\s+days?\s+ago', job_text, re.IGNORECASE)
        if days_ago_match:
            days_ago = int(days_ago_match.group(1))
            return days_ago <= days
    
        # If no date found, include it (better safe than sorry)
        return True
    
    def contains_keywords(self, job_data):
        """Check if job contains any of the target keywords"""
        if not job_data:
            return False
            
        text_to_search = f"{job_data['title']} {job_data['description']}".lower()
        
        matching_keywords = []
        for keyword in self.keywords:
            if keyword.lower() in text_to_search:
                matching_keywords.append(keyword)
        
        if matching_keywords:
            print(f"Keywords found: {', '.join(matching_keywords)}")
            return True
        return False
    
    def send_email(self, jobs):
        """Send email with job listings"""
        if not jobs:
            print("No new jobs to send")
            return
        
        try:
            # Create email content
            subject = f"TAMU Job Alert - {len(jobs)} New Jobs Found ({datetime.now().strftime('%Y-%m-%d')})"
            
            html_body = self.create_email_body(jobs)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_config['from_email']
            msg['To'] = self.email_config['to_email']
            
            # Add HTML body
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Send email
            print(f"Connecting to SMTP server: {self.email_config['smtp_server']}:{self.email_config['smtp_port']}")
            with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['from_email'], self.email_config['password'])
                server.send_message(msg)
            
            print(f"Email sent successfully with {len(jobs)} jobs")
            
            # Update sent jobs list
            for job in jobs:
                if job['id'] not in self.sent_jobs:
                    self.sent_jobs.append(job['id'])
            self.save_sent_jobs()
            
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            raise
    
    def create_email_body(self, jobs):
        """Create HTML email body"""
        html = f"""    
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .job {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .title {{ color: #500000; font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
                .url {{ color: #0066cc; text-decoration: none; }}
                .description {{ margin-top: 10px; color: #333; }}
                .date {{ color: #666; font-size: 12px; }}
                .keywords {{ background-color: #f0f0f0; padding: 5px; margin-top: 10px; font-size: 12px; }}
            </style>
        </head>
        <body>
            <h2>TAMU Job Alert - Wildlife/Ecology Positions</h2>
            <p>Found {len(jobs)} new job(s) matching your keywords:</p>
        """
        
        for job in jobs:
            # Find matching keywords for this job
            text_to_search = f"{job['title']} {job['description']}".lower()
            matching_keywords = [kw for kw in self.keywords if kw.lower() in text_to_search]
            
            html += f"""
            <div class="job">
                <div class="title">{job['title']}</div>
                <div><a href="{job['url']}" class="url">View Job Posting</a></div>
                <div class="description">{job['description'][:300]}{'...' if len(job['description']) > 300 else ''}</div>
                <div class="keywords"><strong>Matching keywords:</strong> {', '.join(matching_keywords)}</div>
                <div class="date">Scraped: {job['scraped_date']}</div>
            </div>
            """
        
        html += f"""
            <p><em>This is an automated job alert. Keywords: {', '.join(self.keywords)}</em></p>
        </body>
        </html>
        """
        
        return html
    
    def run_daily_scrape(self):
        """Run the daily scraping job"""
        print(f"Starting job scrape at {datetime.now()}")
        
        jobs = self.scrape_jobs()
        new_jobs = [job for job in jobs if job['id'] not in self.sent_jobs]
        
        print(f"Found {len(jobs)} total jobs, {len(new_jobs)} new jobs")
        
        if new_jobs:
            self.send_email(new_jobs)
        else:
            print("No new jobs found")
        
        # Always save the state
        self.save_sent_jobs()

def main():
    # Email configuration from environment variables
    smtp_port_str = os.environ.get('SMTP_PORT', '587').strip()
    smtp_port = 587 if not smtp_port_str else int(smtp_port_str)
    
    email_config = {
        'from_email': os.environ.get('FROM_EMAIL', '').strip(),
        'password': os.environ.get('EMAIL_PASSWORD', '').strip(),
        'to_email': os.environ.get('TO_EMAIL', '').strip(),
        'smtp_server': os.environ.get('SMTP_SERVER', 'smtp.gmail.com').strip(),
        'smtp_port': smtp_port
    }
    
    # Validate configuration
    required_vars = ['from_email', 'password', 'to_email']
    missing_vars = [var for var in required_vars if not email_config[var]]
    
    if missing_vars:
        print(f"Missing required environment variables: {missing_vars}")
        print("Please set the following GitHub Secrets:")
        print("  - FROM_EMAIL")
        print("  - EMAIL_PASSWORD") 
        print("  - TO_EMAIL")
        print("\nCurrent values:")
        print(f"  FROM_EMAIL: {'✓' if email_config['from_email'] else '✗ (empty/missing)'}")
        print(f"  EMAIL_PASSWORD: {'✓' if email_config['password'] else '✗ (empty/missing)'}")
        print(f"  TO_EMAIL: {'✓' if email_config['to_email'] else '✗ (empty/missing)'}")
        return
    
    print("Email configuration loaded successfully")
    print(f"From: {email_config['from_email']}")
    print(f"To: {email_config['to_email']}")
    print(f"SMTP: {email_config['smtp_server']}:{email_config['smtp_port']}")
    
    # Create scraper instance
    scraper = TAMUJobScraper(email_config)
    
    # Run once (GitHub Actions will handle scheduling)
    print("Running job scrape...")
    scraper.run_daily_scrape()
    print("Job scrape completed.")

if __name__ == "__main__":
    main()

