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
            "bear", "lion", "snake", "lizard", "alligator", "crocodile", "marine mammal", 
          
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
        # Removed --disable-images and --disable-javascript as they might break the site
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
    
    def extract_job_from_text_block(self, text_block, page_url):
        """Extract job information from a text block"""
        try:
            lines = [line.strip() for line in text_block.split('\n') if line.strip()]
            if len(lines) < 3:  # Too short to be a real job posting
                return None
            
            # The first substantial line is usually the title
            title = lines[0] if lines else "Unknown Position"
            
            # Look for location information
            location = ""
            for line in lines[1:5]:  # Check first few lines for location
                if any(loc_word in line.lower() for loc_word in ['location', 'city', 'state', 'position:']):
                    location = line
                    break
            
            # Look for salary/compensation info
            compensation = ""
            for line in lines:
                if any(comp_word in line.lower() for comp_word in ['salary', 'compensation', 'range:', '$']):
                    compensation = line
                    break
            
            # Create description from all text
            description = text_block
            
            # Try to create a unique URL for this job
            # Since we don't have individual job URLs, create one based on title and current page
            job_url = f"{page_url}#{title.replace(' ', '-').replace('/', '-')}"
            
            # Create unique job ID
            job_id = f"{title}_{job_url}".replace(' ', '_').replace('/', '_')[:200]
            
            return {
                'id': job_id,
                'title': title,
                'location': location,
                'compensation': compensation,
                'url': job_url,
                'description': description,
                'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"Error extracting job from text block: {e}")
            return None
    
    def scrape_jobs(self):
        jobs = []
        page_num = 1
        max_pages = 5  # Reduced since we're doing more thorough processing
        
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
                    
                    # Get the full page text
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    
                    # Print some debug info
                    print(f"Page {page_num} loaded. Text length: {len(page_text)}")
                    print(f"First 500 characters: {page_text[:500]}...")
                    
                    # Try multiple strategies to find job content
                    job_blocks = self.extract_job_blocks_from_page(page_text)
                    
                    if not job_blocks:
                        print(f"No job blocks found on page {page_num}. Trying alternative extraction...")
                        job_blocks = self.extract_jobs_alternative_method()
                    
                    if not job_blocks:
                        print(f"No jobs found on page {page_num}. Stopping pagination.")
                        break
                    
                    print(f"Found {len(job_blocks)} potential job blocks on page {page_num}")
                    
                    for i, job_block in enumerate(job_blocks):
                        try:
                            # Check if this block contains keywords first
                            has_keywords, matching_keywords = self.contains_keywords(job_block)
                            
                            if has_keywords:
                                job_data = self.extract_job_from_text_block(job_block, url)
                                if job_data:
                                    job_data['matching_keywords'] = matching_keywords
                                    jobs.append(job_data)
                                    print(f"Job {i+1} matches keywords: {job_data['title'][:50]}... (Keywords: {', '.join(matching_keywords)})")
                            
                        except Exception as e:
                            print(f"Error processing job block {i+1}: {e}")
                            continue
                    
                    page_num += 1
                    
                except TimeoutException:
                    print(f"Timeout loading page {page_num}")
                    break
                except WebDriverException as e:
                    print(f"WebDriver error on page {page_num}: {e}")
                    break
                    
        finally:
            self.cleanup_driver()
        
        print(f"Found {len(jobs)} jobs matching keywords across all pages")
        return jobs
    
    def extract_job_blocks_from_page(self, page_text):
        """Extract individual job blocks from page text using various strategies"""
        job_blocks = []
        
        # Strategy 1: Split by common job posting patterns
        # Look for patterns that typically start job postings
        job_patterns = [
            r'\n([A-Z][^.\n]{10,100})\n(?=Location:|Position:|Reports to:|Compensation:|Summary:)',
            r'\n([^.\n]{20,100})\n(?=Location of Position:|Job Summary:|Essential Functions:)',
            r'\n\n([A-Z][^.\n]{15,80})\n[A-Z][^.\n]{10,50}:',
        ]
        
        for pattern in job_patterns:
            matches = re.finditer(pattern, page_text, re.MULTILINE)
            for match in matches:
                start_pos = match.start()
                # Find the end of this job posting (next job or end of text)
                next_match = re.search(pattern, page_text[start_pos + 100:])
                if next_match:
                    end_pos = start_pos + 100 + next_match.start()
                else:
                    end_pos = len(page_text)
                
                job_block = page_text[start_pos:end_pos].strip()
                if len(job_block) > 500:  # Only include substantial blocks
                    job_blocks.append(job_block)
        
        # Strategy 2: Split by multiple newlines (common separator)
        if not job_blocks:
            potential_blocks = re.split(r'\n\s*\n\s*\n', page_text)
            for block in potential_blocks:
                block = block.strip()
                if len(block) > 300 and any(keyword in block.lower() for keyword in 
                    ['position', 'job', 'location', 'salary', 'experience', 'duties', 'responsibilities']):
                    job_blocks.append(block)
        
        return job_blocks
    
    def extract_jobs_alternative_method(self):
        """Alternative method using DOM elements"""
        job_blocks = []
        
        try:
            # Try to find specific elements that might contain jobs
            potential_selectors = [
                'div[class*="job"]',
                'div[class*="listing"]', 
                'div[class*="post"]',
                'article',
                'section',
                '.content',
                '#content',
                'main',
                '.main-content'
            ]
            
            for selector in potential_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if len(text) > 300:  # Substantial content
                            job_blocks.append(text)
                    
                    if job_blocks:
                        print(f"Found job blocks using selector: {selector}")
                        break
                        
                except Exception as e:
                    continue
            
            # If still no luck, get all paragraph-like elements
            if not job_blocks:
                try:
                    all_divs = self.driver.find_elements(By.TAG_NAME, "div")
                    for div in all_divs:
                        text = div.text.strip()
                        if (len(text) > 500 and 
                            any(keyword in text.lower() for keyword in ['position', 'location', 'responsibilities', 'qualifications'])):
                            job_blocks.append(text)
                except Exception as e:
                    print(f"Error in alternative extraction: {e}")
            
        except Exception as e:
            print(f"Error in alternative job extraction: {e}")
        
        return job_blocks
    
    def is_job_recent(self, job_text, days=7):
        """Check if job was posted in the last N days"""
        # Look for various date patterns
        date_patterns = [
            r'Published:(\d{2}/\d{2}/\d{4})',
            r'Posted:(\d{2}/\d{2}/\d{4})',
            r'Date Posted:(\d{2}/\d{2}/\d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{4}-\d{2}-\d{2})'
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, job_text)
            if date_match:
                try:
                    date_str = date_match.group(1)
                    if '/' in date_str:
                        job_date = datetime.strptime(date_str, '%m/%d/%Y')
                    else:
                        job_date = datetime.strptime(date_str, '%Y-%m-%d')
                    
                    cutoff_date = datetime.now() - timedelta(days=days)
                    return job_date >= cutoff_date
                except ValueError:
                    continue
        
        # Look for "X days ago"
        days_ago_match = re.search(r'(\d+)\s+days?\s+ago', job_text, re.IGNORECASE)
        if days_ago_match:
            days_ago = int(days_ago_match.group(1))
            return days_ago <= days
    
        # If no date found, include it (better safe than sorry)
        return True
    
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
            </style>
        </head>
        <body>
            <h2>🐾 TAMU Natural Resources Job Alert</h2>
            <p><strong>Found {len(jobs)} new job(s) matching your wildlife/ecology keywords:</strong></p>
        """
        
        for i, job in enumerate(jobs, 1):
            # Use stored matching keywords if available
            matching_keywords = job.get('matching_keywords', [])
            
            html += f"""
            <div class="job">
                <div class="title">{i}. {job['title']}</div>
                <div class="meta">
                    {f'<div class="location">📍 {job["location"]}</div>' if job.get('location') else ''}
                    {f'<div class="compensation">💰 {job["compensation"]}</div>' if job.get('compensation') else ''}
                </div>
                <div><a href="{job['url']}" class="url">🔗 View Full Job Details</a></div>
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

