from playwright.sync_api import sync_playwright
import math
import re
import os
import logging
from datetime import datetime
import odoorpc

# Setup logging
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger("3cx_scraper")

# Load env vars
ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USER = os.getenv("ODOO_USER")
ODOO_PASS = os.getenv("ODOO_PASS")
THREECX_URL = os.getenv("THREECX_URL")
THREECX_USER = os.getenv("THREECX_USER")
THREECX_PASS = os.getenv("THREECX_PASS")


def hms_to_ceil_float_hours(time_str):
    try:
        h, m, s = map(int, time_str.split(":"))
        total_seconds = h * 3600 + m * 60 + s
        total_minutes = math.ceil(total_seconds / 60)
        return total_minutes / 60
    except:
        return 0.0


def scrape_3cx():
    data_rows = []
    today = datetime.today()
    login_url = THREECX_URL.rstrip('/') + "/#/login"
    report_url = THREECX_URL.rstrip('/') + "/#/office/reports/call-reports"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Login
            page.goto(login_url, timeout=60000)
            page.wait_for_selector('#loginInput', timeout=15000)
            html_content = page.content()
            print(f"LOGIN PAGE: {html_content}")
            page.fill('#loginInput', THREECX_USER)
            page.fill('#passwordInput', THREECX_PASS)
            page.click('#submitBtn')
            page.wait_for_timeout(3000)

            # Navigate to call reports
            page.goto(report_url)
            page.wait_for_selector('table tbody tr', timeout=15000)
            html_content = page.content()
            print(f"TABLE PAGE: {html_content}")

            rows = page.query_selector_all('table tbody tr')

            for row in rows:
                cols = row.query_selector_all('td')
                _call_time = cols[0].inner_text().strip()
                if _call_time.lower() == 'no data':
                    continue

                call_time = datetime.strptime(
                    _call_time, "%m/%d/%Y %I:%M:%S %p")
                if call_time.date() < today.date():
                    continue

                call_id = cols[1].inner_text().strip()
                _call_from = cols[2].inner_text().strip()
                match = re.search(r'\((\d+)\)', _call_from)
                call_from = match.group(1) if match else False
                call_to = cols[3].inner_text().strip()
                call_type = cols[4].inner_text().strip().lower()
                call_status = cols[5].inner_text().strip().lower()
                ringing_time = hms_to_ceil_float_hours(
                    cols[7].inner_text().strip())
                talking_time = hms_to_ceil_float_hours(
                    cols[8].inner_text().strip())
                call_cost = cols[9].inner_text().strip()
                call_activity_details = cols[10].inner_text().strip()

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

        except Exception as e:
            _logger.error(f"Playwright scraping failed: {e}")
        finally:
            browser.close()

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
    _logger.info(f"Scraped data: {scraped_data}.")
    if scraped_data:
        push_to_odoo(scraped_data)
