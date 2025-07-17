import math
import time
import re
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import odoorpc
import os
from selenium.webdriver.chrome.service import Service

# logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_logger = logging.getLogger("3cx_scraper")

# ENV CONFIG
ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USER = os.getenv("ODOO_USER")
ODOO_PASS = os.getenv("ODOO_PASS")
THREECX_URL = os.getenv("THREECX_URL")
THREECX_USER = os.getenv("THREECX_USER")
THREECX_PASS = os.getenv("THREECX_PASS")


def hms_to_ceil_float_hours(time_str):
    if not time_str or time_str == "":
        return 0.0
    try:
        h, m, s = map(int, time_str.split(":"))
        total_seconds = h * 3600 + m * 60 + s
        total_minutes = math.ceil(total_seconds / 60)
        return total_minutes / 60
    except:
        return 0.0


def scrape_3cx():
    sleep_time = 10  # Reduced initial sleep time
    timeout_time = 30  # Reduced timeout
    today = datetime.today()
    login_url = THREECX_URL.rstrip('/') + "/#/login"
    report_url = THREECX_URL.rstrip('/') + "/#/office/reports/call-reports"
    data_rows = []

    # Setup headless Chrome with better options
    opts = Options()
    opts.binary_location = os.getenv("CHROME_BIN", "/usr/bin/chromium-browser")
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--disable-extensions')
    opts.add_argument('--disable-plugins')
    opts.add_argument('--disable-images')
    opts.add_argument('--disable-javascript')  # Remove if site needs JS
    opts.add_argument('--window-size=1920,1080')
    opts.add_argument(
        '--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    # Add environment variables check
    _logger.info("Checking environment variables...")
    required_vars = ['THREECX_URL', 'THREECX_USER', 'THREECX_PASS']
    for var in required_vars:
        if not os.getenv(var):
            _logger.error(f"Missing required environment variable: {var}")
            return []
        else:
            _logger.info(f"{var} is set")

    chrome_service = Service(executable_path=os.getenv(
        "CHROMEDRIVER_PATH", "/usr/bin/chromedriver"))

    try:
        driver = webdriver.Chrome(service=chrome_service, options=opts)
        _logger.info("Chrome driver initialized successfully")

        # Navigate to login page
        _logger.info(f"Navigating to login URL: {login_url}")
        driver.get(login_url)
        _logger.info(f"Current URL after navigation: {driver.current_url}")

        # Wait for page to load and take screenshot for debugging
        time.sleep(5)
        _logger.info("Page loaded, checking for login elements...")

        # Check if we're already logged in or redirected
        current_url = driver.current_url
        _logger.info(f"Current URL: {current_url}")

        # More flexible element waiting
        try:
            # Try multiple possible login input selectors
            login_element = None
            possible_selectors = [
                (By.ID, 'loginInput'),
                (By.NAME, 'username'),
                (By.NAME, 'login'),
                (By.CSS_SELECTOR, 'input[type="text"]'),
                (By.CSS_SELECTOR, 'input[placeholder*="user"]'),
                (By.CSS_SELECTOR, 'input[placeholder*="User"]'),
                (By.CSS_SELECTOR, 'input[placeholder*="name"]')
            ]

            for selector_type, selector_value in possible_selectors:
                try:
                    login_element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (selector_type, selector_value))
                    )
                    _logger.info(
                        f"Found login element with selector: {selector_type}={selector_value}")
                    break
                except TimeoutException:
                    continue

            if not login_element:
                _logger.error("Could not find login input element")
                _logger.info(f"Page source: {driver.page_source[:1000]}...")
                return []

            # Clear and enter username
            login_element.clear()
            login_element.send_keys(THREECX_USER)
            _logger.info("Username entered")

            # Find password field
            password_element = None
            password_selectors = [
                (By.ID, 'passwordInput'),
                (By.NAME, 'password'),
                (By.CSS_SELECTOR, 'input[type="password"]'),
                (By.CSS_SELECTOR, 'input[placeholder*="pass"]'),
                (By.CSS_SELECTOR, 'input[placeholder*="Pass"]')
            ]

            for selector_type, selector_value in password_selectors:
                try:
                    password_element = driver.find_element(
                        selector_type, selector_value)
                    _logger.info(
                        f"Found password element with selector: {selector_type}={selector_value}")
                    break
                except NoSuchElementException:
                    continue

            if not password_element:
                _logger.error("Could not find password input element")
                return []

            password_element.clear()
            password_element.send_keys(THREECX_PASS)
            _logger.info("Password entered")

            # Find and click submit button
            submit_button = None
            submit_selectors = [
                (By.ID, "submitBtn"),
                (By.CSS_SELECTOR, 'button[type="submit"]'),
                (By.CSS_SELECTOR, 'input[type="submit"]'),
                (By.CSS_SELECTOR, 'button:contains("Login")'),
                (By.CSS_SELECTOR, 'button:contains("Sign")'),
                (By.XPATH, "//button[contains(text(), 'Login')]"),
                (By.XPATH, "//button[contains(text(), 'Sign')]"),
                (By.XPATH, "//input[@type='submit']")
            ]

            for selector_type, selector_value in submit_selectors:
                try:
                    submit_button = driver.find_element(
                        selector_type, selector_value)
                    _logger.info(
                        f"Found submit button with selector: {selector_type}={selector_value}")
                    break
                except NoSuchElementException:
                    continue

            if not submit_button:
                _logger.error("Could not find submit button")
                return []

            submit_button.click()
            _logger.info("Submit button clicked")

            # Wait for login to complete
            time.sleep(sleep_time)
            _logger.info(f"Current URL after login: {driver.current_url}")

        except TimeoutException as e:
            _logger.error(f"Timeout waiting for login elements: {e}")
            _logger.info(f"Page source: {driver.page_source}")
            return []

        # Navigate to reports page
        _logger.info(f"Navigating to reports URL: {report_url}")
        driver.get(report_url)
        time.sleep(sleep_time)
        _logger.info(
            f"Current URL after reports navigation: {driver.current_url}")

        # Wait for loading to complete
        try:
            WebDriverWait(driver, timeout_time).until(
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, '.loading'))
            )
            _logger.info("Loading completed")
        except TimeoutException:
            _logger.warning(
                "Loading element not found or didn't disappear, continuing...")

        # Wait for table to appear
        try:
            WebDriverWait(driver, timeout_time).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'table tbody tr'))
            )
            _logger.info("Table found")
        except TimeoutException:
            _logger.error("Table not found within timeout")
            _logger.info(f"Page source: {driver.page_source}")
            return []

        # Extract data from table
        rows = driver.find_elements(By.CSS_SELECTOR, 'table tbody tr')
        _logger.info(f"Found {len(rows)} rows in table")

        if len(rows) == 0:
            _logger.warning("No rows found in table")
            return []

        for i, row in enumerate(rows):
            try:
                cols = row.find_elements(By.TAG_NAME, 'td')
                _logger.info(f"Processing row {i+1} with {len(cols)} columns")

                if len(cols) < 11:
                    _logger.warning(
                        f"Row {i+1} has insufficient columns ({len(cols)}), skipping")
                    continue

                _call_time = cols[0].text.strip()
                call_time = None
                if _call_time:
                    try:
                        call_time = datetime.strptime(
                            _call_time, "%m/%d/%Y %I:%M:%S %p")
                    except ValueError:
                        _logger.warning(
                            f"Could not parse call time: {_call_time}")
                        continue

                call_id = cols[1].text.strip()
                if not call_id:
                    _logger.warning(f"Row {i+1} has no call ID, skipping")
                    continue

                _call_from = cols[2].text.strip()
                match = re.search(r'\((\d+)\)', _call_from)
                call_from = match.group(1) if match else _call_from

                call_to = cols[3].text.strip()
                call_type = cols[4].text.strip().lower()
                call_status = cols[5].text.strip().lower()

                _call_ringing_time = cols[7].text.strip()
                ringing_time = hms_to_ceil_float_hours(_call_ringing_time)

                _call_talking_time = cols[8].text.strip()
                talking_time = hms_to_ceil_float_hours(_call_talking_time)

                call_cost = cols[9].text.strip()
                call_activity_details = cols[10].text.strip()

                data_rows.append({
                    'call_id': call_id,
                    'call_from': call_from,
                    'call_to': call_to,
                    'call_time': call_time.strftime('%m/%d/%Y %I:%M:%S %p'),
                    'call_type': call_type,
                    'call_status': call_status,
                    'call_ringing_time': ringing_time,
                    'call_talking_time': talking_time,
                    'call_cost': call_cost,
                    'call_activity_details': call_activity_details,
                })

                _logger.info(
                    f"Successfully processed row {i+1}: Call ID {call_id}")

            except Exception as e:
                _logger.error(f"Error processing row {i+1}: {e}")
                continue

        _logger.info(f"Successfully scraped {len(data_rows)} records")

    except Exception as e:
        _logger.error(f"Error during scraping: {e}")
        _logger.error(
            f"Current URL: {driver.current_url if 'driver' in locals() else 'Driver not initialized'}")
        if 'driver' in locals():
            _logger.error(f"Page source: {driver.page_source[:1000]}...")
    finally:
        if 'driver' in locals():
            driver.quit()
            _logger.info("Chrome driver closed")

    return data_rows


def push_to_odoo(records):
    if not records:
        _logger.info("No records to push to Odoo")
        return

    try:
        # Clean URL for Odoo connection
        clean_url = ODOO_URL.replace('https://', '').replace('http://', '')
        _logger.info(f"Connecting to Odoo at: {clean_url}")

        odoo = odoorpc.ODOO(clean_url, port=80)
        odoo.login(ODOO_DB, ODOO_USER, ODOO_PASS)
        model = odoo.env['logs.3cx']

        created_count = 0
        for rec in records:
            try:
                if model.search([('call_id', '=', rec['call_id'])]):
                    _logger.info(
                        f"Record with call_id {rec['call_id']} already exists, skipping")
                    continue

                _logger.info(f"Creating record: {rec['call_id']}")
                model.create(rec)
                created_count += 1

            except Exception as e:
                _logger.error(f"Error creating record {rec['call_id']}: {e}")
                continue

        _logger.info(
            f"Successfully created {created_count} new records in Odoo")

    except Exception as e:
        _logger.error(f"Error connecting to Odoo: {e}")


if __name__ == "__main__":
    _logger.info("Starting 3CX scraper...")
    scraped_data = scrape_3cx()
    _logger.info(f"Scraped {len(scraped_data)} records")

    if scraped_data:
        push_to_odoo(scraped_data)
        _logger.info("Scraping completed successfully")
    else:
        _logger.warning("No data was scraped")
