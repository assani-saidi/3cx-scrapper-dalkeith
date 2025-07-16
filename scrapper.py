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
import odoorpc
import os
# from dotenv import load_dotenv

# load_dotenv()

# logging
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger("3cx_scraper")

# # ENV CONFIG
# ODOO_URL = os.getenv('ODOO_URL')
# ODOO_DB = os.getenv('ODOO_DB')
# ODOO_USER = os.getenv('ODOO_USER')
# ODOO_PASS = os.getenv('ODOO_PASS')

# THREECX_URL = os.getenv('THREECX_URL')
# THREECX_USER = os.getenv('THREECX_USER')
# THREECX_PASS = os.getenv('THREECX_PASS')

# ENV CONFIG
ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USER = os.getenv("ODOO_USER")
ODOO_PASS = os.getenv("ODOO_PASS")
THREECX_URL = os.getenv("THREECX_URL")
THREECX_USER = os.getenv("THREECX_USER")
THREECX_PASS = os.getenv("THREECX_PASS")


def hms_to_ceil_float_hours(time_str):
    h, m, s = map(int, time_str.split(":"))
    total_seconds = h * 3600 + m * 60 + s
    total_minutes = math.ceil(total_seconds / 60)
    return total_minutes / 60


def scrape_3cx():
    sleep_time = 3
    timeout_time = 5
    today = datetime.today()
    login_url = THREECX_URL.rstrip('/') + "/#/login"
    report_url = THREECX_URL.rstrip('/') + "/#/office/reports/call-reports"
    data_rows = []

    # Setup headless Chrome
    opts = Options()
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=opts)

    try:
        driver.get(login_url)
        time.sleep(sleep_time)
        WebDriverWait(driver, timeout_time).until(
            EC.presence_of_element_located((By.ID, 'loginInput')))
        driver.find_element(By.ID, 'loginInput').send_keys(THREECX_USER)
        driver.find_element(By.ID, 'passwordInput').send_keys(THREECX_PASS)
        driver.find_element(By.ID, "submitBtn").click()
        time.sleep(sleep_time)

        driver.get(report_url)
        time.sleep(sleep_time)
        WebDriverWait(driver, timeout_time).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, '.loading')))
        rows = driver.find_elements(By.CSS_SELECTOR, 'table tbody tr')

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, 'td')
            _call_time = cols[0].text.strip()
            call_time = datetime.strptime(
                _call_time, "%m/%d/%Y %I:%M:%S %p") if _call_time else False
            call_id = cols[1].text.strip()
            _call_from = cols[2].text.strip()
            match = re.search(r'\((\d+)\)', _call_from)
            call_from = match.group(1) if match else False
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
                'call_time': call_time.strftime('%Y-%m-%d %H:%M:%S %p'),
                'call_type': call_type,
                'call_status': call_status,
                'call_ringing_time': ringing_time,
                'call_talking_time': talking_time,
                'call_cost': call_cost,
                'call_activity_details': call_activity_details,
            })

    except Exception as e:
        _logger.error(f"Error during scraping: {e}")
    finally:
        driver.quit()

    return data_rows


def push_to_odoo(records):
    odoo = odoorpc.ODOO(ODOO_URL.replace(
        'https://', '').replace('http://', ''), port=80)
    odoo.login(ODOO_DB, ODOO_USER, ODOO_PASS)
    model = odoo.env['logs.3cx']

    for rec in records:
        if model.search([('call_id', '=', rec['call_id'])]):
            continue
        _logger.info(f"Creating record: {rec['call_id']}")
        model.create(rec)


if __name__ == "__main__":
    scraped_data = scrape_3cx()
    print(f"Scraped: {scraped_data}.")
    if scraped_data:
        push_to_odoo(scraped_data)
