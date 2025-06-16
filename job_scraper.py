import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os
from datetime import datetime
import re

class TAMUJobScraper:
    def __init__(self, email_config):
        self.base_url = "https://jobs.rwfm.tamu.edu/search/"
        self.keywords = [
            "reptile", "amphibian", "herp", "turtle", "toad", "frog", 
            "seal", "island", "whale", "cetacean", "tortoise", 
            "spatial ecology", "predator", "tropical"
        ]
        self.email_config = email_config
        self.sent_jobs_file = "sent_jobs.json"
        self.sent_jobs = self.load_sent_jobs()
        
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
    page_num = 1
    max_pages = 100  # safety limit
    while True:
        url = f"https://jobs.rwfm.tamu.edu/search/?PageSize=10&PageNum={page_num}#results"
        print(f"Fetching jobs from: {url}")
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

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
                job_data = self.extract_job_data(job_element)
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

    print(f"Found {len(jobs)} jobs matching keywords across all pages")
    return jobs
Notes:

This method will scrape all available pages until it finds a page with no job elements.
Adjust max_pages if you want to limit how many pages to check (prevents infinite loops).
Replace your current scrape_jobs method with this updated version.
Let me know if you want the full function ready to paste, or if you need help integrating it!

is this replacing something or just being added on
The pagination code I provided is intended to replace your current scrape_jobs method, not to be added on top of it. You should:

Locate your existing def scrape_jobs(self): method in job_scraper.py.
Replace the entire contents of that method (from def scrape_jobs(self): to the final return or end of the method) with the new pagination-aware version.
This way, your scraper will loop through all available result pages instead of only scraping the first page.

If you want the complete, ready-to-paste replacement function, let me know!

yes id like that
Here is a ready-to-paste replacement for your entire scrape_jobs method, updated to handle pagination through all result pages on https://jobs.rwfm.tamu.edu/search/:

Python
def scrape_jobs(self):
    """Scrape all job listings from TAMU website, handling pagination"""
    jobs = []
    page_num = 1
    max_pages = 100  # safety limit to prevent infinite loops

    while True:
        url = f"https://jobs.rwfm.tamu.edu/search/?PageSize=10&PageNum={page_num}#results"
        print(f"Fetching jobs from: {url}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        selectors = [
            {'tag': 'div', 'class': re.compile(r'job|posting|listing|position', re.I)},
            {'tag': 'article', 'class': re.compile(r'job|posting|listing|position', re.I)},
            {'tag': 'li', 'class': re.compile(r'job|posting|listing|position', re.I)},
            {'tag': 'tr', 'class': re.compile(r'job|posting|listing|position', re.I)},
            {'tag': 'div', 'attrs': {'data-job': True}},
            {'tag': 'a', 'href': re.compile(r'job|posting|position', re.I)},
        ]

        job_elements = []
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
                job_data = self.extract_job_data(job_element)
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

    print(f"Found {len(jobs)} jobs matching keywords across all pages")
    return jobs
    
    def extract_job_data(self, element):
        """Extract job data from HTML element"""
        try:
            # Extract job title - try multiple approaches
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
                # If element itself is a link, use its text
                if element.name == 'a':
                    title = element.get_text(strip=True)
                else:
                    # Last resort: use first 100 characters of element text
                    title = element.get_text(strip=True)[:100]
            
            if not title or len(title) < 3:
                return None
            
            # Extract job URL
            url = None
            if element.name == 'a' and element.get('href'):
                href = element['href']
            else:
                link_elem = element.find('a', href=True)
                href = link_elem['href'] if link_elem else None
            
            if href:
                if href.startswith('http'):
                    url = href
                elif href.startswith('/'):
                    url = f"https://jobs.rwfm.tamu.edu{href}"
                else:
                    url = f"https://jobs.rwfm.tamu.edu/{href}"
            else:
                url = "No URL found"
            
            # Extract description/summary
            description = ""
            desc_selectors = [
                {'class': re.compile(r'desc|summary|content|detail', re.I)},
                {'tag': 'p'},
                {'tag': 'div'}
            ]
            
            for selector in desc_selectors:
                if 'tag' in selector:
                    desc_elem = element.find(selector['tag'])
                else:
                    desc_elem = element.find(class_=selector['class'])
                
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    break
            
            if not description:
                description = element.get_text(strip=True)
            
            # Limit description length
            if len(description) > 1000:
                description = description[:1000] + "..."
            
            # Create unique ID for job
            job_id = f"{title}_{url}".replace(' ', '_').replace('/', '_')[:200]
            
            return {
                'id': job_id,
                'title': title,
                'url': url,
                'description': description,
                'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"Error extracting job data: {str(e)}")
            return None
    
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

