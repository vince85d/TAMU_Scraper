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
from urllib.parse import urljoin
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
        chrome_options.add_argument('--disable-images')  # Speed up loading
        chrome_options.add_argument('--disable-javascript')  # Only if the site works without JS
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
    
    def extract_basic_job_info(self, element):
        """Extract basic job info from listing page without opening detail page"""
        try:
            # Get all text from the element
            element_text = element.text.strip()
            
            # Try to find job URL
            job_url = None
            try:
                link = element.find_element(By.TAG_NAME, "a")
                job_url = link.get_attribute("href")
            except:
                # Try to get href from the element itself if it's a link
                job_url = element.get_attribute("href")
            
            # Extract title (usually the first line or in a link)
            title = ""
            try:
                # Try common title selectors
                title_selectors = [
                    "h1", "h2", "h3", "h4", "h5", "h6",
                    "[class*='title']", "[class*='job-title']", 
                    "[class*='position']", "a"
                ]
                
                for selector in title_selectors:
                    try:
                        title_elem = element.find_element(By.CSS_SELECTOR, selector)
                        if title_elem.text.strip():
                            title = title_elem.text.strip()
                            break
                    except:
                        continue
                        
                # If no title found in elements, use first line of text
                if not title and element_text:
                    title = element_text.split('\n')[0].strip()
                    
            except Exception as e:
                print(f"Error extracting title: {e}")
                title = "Title not found"
            
            return {
                'title': title,
                'url': job_url,
                'preview_text': element_text,
                'element': element  # Keep reference for later detail extraction
            }
            
        except Exception as e:
            print(f"Error extracting basic job info: {e}")
            return None
    
    def extract_detailed_job_info(self, basic_info):
        """Extract detailed job information by opening the job page"""
        if not basic_info or not basic_info['url']:
            return None
            
        try:
            original_window = self.driver.current_window_handle
            
            # Open job page in new tab
            self.driver.execute_script("window.open(arguments[0]);", basic_info['url'])
            WebDriverWait(self.driver, 10).until(EC.number_of_windows_to_be(2))
            
            # Switch to new tab
            for handle in self.driver.window_handles:
                if handle != original_window:
                    self.driver.switch_to.window(handle)
                    break
            
            # Wait for page to load
            time.sleep(2)
            
            # Get detailed information
            url = self.driver.current_url
            title = self.driver.title.strip() or basic_info['title']
            
            try:
                body_elem = self.driver.find_element(By.TAG_NAME, "body")
                description = body_elem.text.strip()
            except:
                description = basic_info['preview_text']  # Fallback to preview text
            
            # Close tab and return to original
            self.driver.close()
            self.driver.switch_to.window(original_window)
            
            # Create job ID
            job_id = f"{title}_{url}".replace(' ', '_').replace('/', '_')[:200]
            
            return {
                'id': job_id,
                'title': title,
                'url': url,
                'description': description[:1000] + "..." if len(description) > 1000 else description,
                'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"Error extracting detailed job info: {e}")
            # Return basic info as fallback
            job_id = f"{basic_info['title']}_{basic_info['url'] or 'no_url'}".replace(' ', '_').replace('/', '_')[:200]
            return {
                'id': job_id,
                'title': basic_info['title'],
                'url': basic_info['url'] or '',
                'description': basic_info['preview_text'],
                'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def scrape_jobs(self):
        jobs = []
        page_num = 1
        max_pages = 10  # safety limit
        
        try:
            self.setup_driver()
            
            while page_num <= max_pages:
                url = f"https://jobs.rwfm.tamu.edu/search/?PageSize=50&PageNum={page_num}#results"
                print(f"Fetching jobs from: {url}")
                
                try:
                    self.driver.get(url)
                    
                    # Wait for page to load
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    
                    # Additional wait for dynamic content
                    time.sleep(3)
                    
                    # Find job elements using multiple strategies
                    job_elements = self.find_job_elements()
                    
                    if not job_elements:
                        print(f"No jobs found on page {page_num}. Stopping pagination.")
                        break
                    
                    print(f"Processing {len(job_elements)} job elements on page {page_num}...")
                    
                    # First pass: extract basic info and filter by keywords
                    potential_jobs = []
                    for i, job_element in enumerate(job_elements):
                        try:
                            basic_info = self.extract_basic_job_info(job_element)
                            if not basic_info:
                                continue
                            
                            # Check if job is recent
                            if not self.is_job_recent(basic_info['preview_text'], days=7):
                                continue
                            
                            # Check keywords on preview text
                            search_text = f"{basic_info['title']} {basic_info['preview_text']}"
                            has_keywords, matching_keywords = self.contains_keywords(search_text)
                            
                            if has_keywords:
                                basic_info['matching_keywords'] = matching_keywords
                                potential_jobs.append(basic_info)
                                print(f"Job {i+1} matches keywords: {basic_info['title']} (Keywords: {', '.join(matching_keywords)})")
                        
                        except Exception as e:
                            print(f"Error processing job element {i+1}: {e}")
                            continue
                    
                    print(f"Found {len(potential_jobs)} potential jobs matching keywords on page {page_num}")
                    
                    # Second pass: get detailed info only for matching jobs
                    for basic_info in potential_jobs:
                        try:
                            detailed_job = self.extract_detailed_job_info(basic_info)
                            if detailed_job:
                                # Double-check keywords on full description
                                full_text = f"{detailed_job['title']} {detailed_job['description']}"
                                has_keywords, matching_keywords = self.contains_keywords(full_text)
                                
                                if has_keywords:
                                    detailed_job['matching_keywords'] = matching_keywords
                                    jobs.append(detailed_job)
                                    print(f"Added detailed job: {detailed_job['title']}")
                        except Exception as e:
                            print(f"Error getting detailed info for job: {e}")
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
    
    def find_job_elements(self):
        """Find job elements using multiple selectors"""
        job_elements = []
        
        # CSS selectors to try (in order of preference)
        selectors = [
            "div[class*='job']",
            "div[class*='posting']",
            "div[class*='listing']",
            "div[class*='position']",
            "article[class*='job']",
            "article[class*='posting']",
            "li[class*='job']",
            "li[class*='posting']",
            "tr[class*='job']",
            "div[data-job]",
            "a[href*='job']",
            "a[href*='posting']",
            "a[href*='position']",
            ".job",
            ".posting",
            ".listing",
            ".position",
            "[role='listitem']",
            ".search-result",
            ".result-item"
        ]
        
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"Found {len(elements)} elements with selector: {selector}")
                    job_elements = elements
                    break
            except Exception as e:
                print(f"Error with selector '{selector}': {e}")
                continue
        
        # If no specific job elements found, try to find any links or divs that might contain jobs
        if not job_elements:
            try:
                # Look for any links that might be job postings
                links = self.driver.find_elements(By.TAG_NAME, "a")
                job_elements = [link for link in links if link.get_attribute("href") and 
                              any(keyword in link.get_attribute("href").lower() for keyword in ['job', 'posting', 'position'])]
                if job_elements:
                    print(f"Found {len(job_elements)} job links as fallback")
            except Exception as e:
                print(f"Error finding fallback elements: {e}")
        
        return job_elements

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
            # Use stored matching keywords if available
            matching_keywords = job.get('matching_keywords', [])
            if not matching_keywords:
                # Fallback: find matching keywords
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


