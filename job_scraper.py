from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin, urlparse
import time

class TAMUJobScraper:
    def __init__(self, email_config):
        self.base_url = "https://jobs.rwfm.tamu.edu/search/"
        self.keywords = [
            "reptile", "amphibian", "herp", "turtle", "toad", "frog", 
            "seal", "island", "whale", "cetacean", "tortoise", 
            "spatial ecology", "predator", "tropical", "hawaii", 
            "bear", "lion", "snake", "lizard", "alligator", "crocodile", 
            "marine mammal"
        ]
        self.email_config = email_config
        self.sent_jobs_file = "sent_jobs.json"
        self.sent_jobs = self.load_sent_jobs()
        self.driver = None
        
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        chrome_options = Options()
        
        # Common options for both local and GitHub Actions
        chrome_options.add_argument('--headless')  # Run in background
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Additional options for stability
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            # Try to create driver - will work locally or in GitHub Actions with setup-chromedriver action
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("Chrome driver initialized successfully")
        except Exception as e:
            print(f"Error setting up Chrome driver: {e}")
            raise
    
    def cleanup_driver(self):
        """Clean up the driver"""
        if self.driver:
            try:
                self.driver.quit()
                print("Driver cleaned up successfully")
            except Exception as e:
                print(f"Error cleaning up driver: {e}")
    
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
    
    def contains_keywords(self, text):
        """Check if text contains any of the target keywords"""
        if not text:
            return False, []
            
        text_lower = text.lower()
        matching_keywords = []
        
        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                matching_keywords.append(keyword)
        
        return len(matching_keywords) > 0, matching_keywords
    
    def extract_job_details_from_elements(self, job_elements):
        """Extract job information from DOM elements and find the real job URLs"""
        jobs = []
        
        for element in job_elements:
            try:
                # Get all text from this element
                job_text = element.text.strip()
                
                if len(job_text) < 50:  # Skip if too short
                    continue
                
                # Check if this job matches our keywords
                has_keywords, matching_keywords = self.contains_keywords(job_text)
                
                if not has_keywords:
                    continue
                
                # Try to find the job title and URL
                title = "Unknown Position"
                job_url = ""
                
                # Look for links within this element - try multiple selectors
                link_selectors = [
                    'a[href*="/job/"]',          # Most common pattern
                    'a[href*="/posting/"]',      # Alternative pattern
                    'a[href*="/position/"]',     # Another alternative
                    'a[href*="view"]',           # Links with "view" text
                    'a[title*="view"]',          # Links with "view" in title
                    'a:contains("View")',        # CSS selector for "View" text
                    'a',                         # Fallback: any link
                ]
                
                link_element = None
                for selector in link_selectors:
                    try:
                        if selector == 'a:contains("View")':
                            # For this selector, we need to find links with "View" text
                            links = element.find_elements(By.TAG_NAME, "a")
                            for link in links:
                                if "view" in link.text.lower() or "details" in link.text.lower():
                                    link_element = link
                                    break
                        else:
                            potential_links = element.find_elements(By.CSS_SELECTOR, selector)
                            if potential_links:
                                link_element = potential_links[0]  # Take the first one
                                break
                    except:
                        continue
                
                if link_element:
                    try:
                        job_url = link_element.get_attribute('href')
                        # Make sure it's a full URL
                        if job_url and not job_url.startswith('http'):
                            job_url = urljoin(self.base_url, job_url)
                        
                        # Try to get title from link text or nearby elements
                        link_text = link_element.text.strip()
                        if link_text and link_text.lower() not in ['view', 'details', 'more']:
                            title = link_text
                        else:
                            # Look for title in parent or sibling elements
                            parent = link_element.find_element(By.XPATH, '..')
                            parent_text = parent.text.strip()
                            lines = [line.strip() for line in parent_text.split('\n') if line.strip()]
                            if lines:
                                title = lines[0]  # Usually the first line is the title
                    except Exception as e:
                        print(f"Error extracting link details: {e}")
                
                # Extract other job details
                location = ""
                compensation = ""
                
                # Look for location patterns
                location_patterns = [
                    r'Location:?\s*([^\n]+)',
                    r'Position Location:?\s*([^\n]+)',
                    r'City:?\s*([^\n]+)',
                    r'([A-Z][a-z]+,\s*[A-Z]{2})',  # City, State format
                ]
                
                for pattern in location_patterns:
                    match = re.search(pattern, job_text, re.IGNORECASE)
                    if match:
                        location = match.group(1).strip()
                        break
                
                # Look for compensation patterns
                comp_patterns = [
                    r'Salary:?\s*([^\n]+)',
                    r'Compensation:?\s*([^\n]+)',
                    r'Pay:?\s*([^\n]+)',
                    r'\$[\d,]+(?:\.\d{2})?(?:\s*-\s*\$[\d,]+(?:\.\d{2})?)?',
                ]
                
                for pattern in comp_patterns:
                    match = re.search(pattern, job_text, re.IGNORECASE)
                    if match:
                        compensation = match.group(0).strip()
                        break
                
                # Create unique job ID
                job_id = f"{title}_{job_url}".replace(' ', '_').replace('/', '_')[:200]
                
                job_data = {
                    'id': job_id,
                    'title': title,
                    'location': location,
                    'compensation': compensation,
                    'url': job_url or f"{self.base_url}#{title.replace(' ', '-')}",  # Fallback URL
                    'description': job_text,
                    'matching_keywords': matching_keywords,
                    'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                jobs.append(job_data)
                print(f"Found job: {title[:50]}... with URL: {job_url}")
                
            except Exception as e:
                print(f"Error processing job element: {e}")
                continue
        
        return jobs
    
    def scrape_jobs(self):
        jobs = []
        page_num = 1
        max_pages = 5
        
        try:
            self.setup_driver()
            
            while page_num <= max_pages:
                url = f"https://jobs.rwfm.tamu.edu/search/?PageSize=50&PageNum={page_num}"
                print(f"Fetching jobs from: {url}")
                
                try:
                    self.driver.get(url)
                    
                    # Wait for page to load completely
                    WebDriverWait(self.driver, 30).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    
                    # Wait for content to load
                    time.sleep(5)
                    
                    # Try multiple strategies to find job elements
                    job_elements = []
                    
                    # Strategy 1: Look for common job listing containers
                    job_selectors = [
                        'div[class*="job"]',
                        'div[class*="listing"]',
                        'div[class*="posting"]',
                        'div[class*="position"]',
                        'tr[class*="job"]',        # Table rows
                        'tr[class*="listing"]',
                        'li[class*="job"]',        # List items
                        '.job-item',
                        '.listing-item',
                        '.position-item',
                        'article',
                        '[data-job-id]',           # Elements with job ID data attributes
                    ]
                    
                    for selector in job_selectors:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                job_elements = elements
                                print(f"Found {len(elements)} job elements using selector: {selector}")
                                break
                        except Exception as e:
                            continue
                    
                    # Strategy 2: If no specific job containers found, look for elements containing links
                    if not job_elements:
                        print("No job containers found, looking for elements with job links...")
                        try:
                            # Find all elements that contain links with job-like URLs
                            all_elements = self.driver.find_elements(By.XPATH, "//div[.//a[contains(@href, 'job') or contains(@href, 'position') or contains(@href, 'posting')]]")
                            job_elements = all_elements
                            print(f"Found {len(job_elements)} elements with job links")
                        except Exception as e:
                            print(f"Error finding elements with job links: {e}")
                    
                    # Strategy 3: Fallback - find any substantial div elements
                    if not job_elements:
                        print("Using fallback strategy...")
                        all_divs = self.driver.find_elements(By.TAG_NAME, "div")
                        job_elements = [div for div in all_divs if len(div.text.strip()) > 100]
                        print(f"Fallback found {len(job_elements)} substantial div elements")
                    
                    if not job_elements:
                        print(f"No job elements found on page {page_num}")
                        break
                    
                    # Extract job details
                    page_jobs = self.extract_job_details_from_elements(job_elements)
                    jobs.extend(page_jobs)
                    
                    print(f"Page {page_num}: Found {len(page_jobs)} matching jobs")
                    
                    if not page_jobs:
                        print("No matching jobs found, stopping pagination")
                        break
                    
                    page_num += 1
                    
                except TimeoutException:
                    print(f"Timeout loading page {page_num}")
                    break
                except WebDriverException as e:
                    print(f"WebDriver error on page {page_num}: {e}")
                    break
                    
        finally:
            self.cleanup_driver()
        
        print(f"Total: Found {len(jobs)} jobs matching keywords across all pages")
        return jobs
    
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
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .job {{ border: 1px solid #ddd; padding: 20px; margin: 15px 0; border-radius: 8px; background-color: #f9f9f9; }}
                .title {{ color: #500000; font-size: 20px; font-weight: bold; margin-bottom: 15px; }}
                .meta {{ color: #666; font-size: 14px; margin-bottom: 10px; }}
                .location {{ color: #0066cc; font-weight: bold; }}
                .compensation {{ color: #006600; font-weight: bold; }}
                .url {{ color: #0066cc; text-decoration: none; font-weight: bold; }}
                .description {{ margin-top: 15px; color: #333; background-color: white; padding: 15px; border-radius: 5px; }}
                .keywords {{ background-color: #e6f3ff; padding: 10px; margin-top: 15px; font-size: 12px; border-radius: 5px; }}
                .date {{ color: #999; font-size: 11px; margin-top: 10px; }}
                h2 {{ color: #500000; }}
                .url-note {{ color: #666; font-size: 12px; font-style: italic; }}
            </style>
        </head>
        <body>
            <h2>🐾 TAMU Natural Resources Job Alert</h2>
            <p><strong>Found {len(jobs)} new job(s) matching your wildlife/ecology keywords:</strong></p>
        """
        
        for i, job in enumerate(jobs, 1):
            # Use stored matching keywords if available
            matching_keywords = job.get('matching_keywords', [])
            
            # Check if we have a real job URL or a fallback
            url_note = ""
            if job['url'].startswith(self.base_url) and '#' in job['url']:
                url_note = '<div class="url-note">⚠️ Direct job link not found - this links to the main job search page</div>'
            
            html += f"""
            <div class="job">
                <div class="title">{i}. {job['title']}</div>
                <div class="meta">
                    {f'<div class="location">📍 {job["location"]}</div>' if job.get('location') else ''}
                    {f'<div class="compensation">💰 {job["compensation"]}</div>' if job.get('compensation') else ''}
                </div>
                <div><a href="{job['url']}" class="url">🔗 View Full Job Details</a></div>
                {url_note}
                <div class="description">
                    <strong>Job Description:</strong><br>
                    {job['description'][:500]}{'...' if len(job['description']) > 500 else ''}
                </div>
                <div class="keywords">
                    <strong>🎯 Matching keywords:</strong> {', '.join(matching_keywords)}
                </div>
                <div class="date">Scraped: {job['scraped_date']}</div>
            </div>
            """
        
        html += f"""
            <hr style="margin: 30px 0;">
            <p><em>📧 This is an automated job alert from the TAMU Natural Resources Job Board.<br>
            🔍 Keywords monitored: {', '.join(self.keywords[:10])}{'...' if len(self.keywords) > 10 else ''}<br>
            🌐 Source: <a href="https://jobs.rwfm.tamu.edu/search/">https://jobs.rwfm.tamu.edu/search/</a></em></p>
        </body>
        </html>
        """
        
        return html
    
    def run_daily_scrape(self):
        """Run the daily scraping job"""
        print(f"Starting job scrape at {datetime.now()}")
        
        try:
            jobs = self.scrape_jobs()
            new_jobs = [job for job in jobs if job['id'] not in self.sent_jobs]
            
            print(f"Found {len(jobs)} total jobs, {len(new_jobs)} new jobs")
            
            if new_jobs:
                self.send_email(new_jobs)
            else:
                print("No new jobs found")
            
        except Exception as e:
            print(f"Error during scraping: {e}")
            raise
        finally:
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
