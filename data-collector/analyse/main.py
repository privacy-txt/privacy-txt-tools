import asyncio
import os
import re
from playwright.async_api import async_playwright
import base64
import json
from datetime import date
import logging
import argparse
import time
import tldextract
from pathlib import Path
import sqlite3
from google_search import get_first_result, search_google
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import statistics

from db_to_txt import db_to_txt

from constants import HEADLESS, COOKIE_CHECK_LIST, \
    PRIVACY_WORD_LIST, \
    ELIST_DOMAINS, EPRIVACY_DOMAINS, DISCONNECT_LIST, \
    CONSENT_MANAGERS, DATABASE, JSON_FILE

consent_tracker_count = {}
no_consent_tracker_count = {}
consent_persistent_count = {}
no_consent_persistent_count = {}
consent_trackdomain_count = {}
no_consent_trackdomain_count = {}


def setup_driver(url):
    """
        Driver for Chrome
    """
    chrome_options = Options()
    chrome_options.headless = HEADLESS
    chrome_options.add_argument('--no-sandbox')  # Needed for Docker image
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    info = {'current_ts': time.time(), 'site': url, 'cookies': []}
    try:
        driver.get(url)
    except WebDriverException as e:
        if 'www.' not in url:
            driver.close()
            [proto, domain] = url.split('://')
            return setup_driver(f'{proto}://www.{domain}')

        msg = re.split('\n|:', e.msg)
        error = msg[3] if len(msg) > 3 else 'ERR_GENERIC'

        possible_url = get_first_result(driver, url)
        driver.close()
        if possible_url is None:
            raise Exception('Site inaccessible with no google results.')

        info['error'] = {'url': url, 'msg': error}
        info['site'] = possible_url

        # Restart driver with newly found url
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(possible_url)

    # Waiting for 1s so JS should be done running
    time.sleep(1)

    return driver, info


def init_database(db_name):
    """
    Setup the DB connection and seed with data if needed
    """
    conn = sqlite3.connect(db_name)

    return conn


def batch(iterable, n=1):
    """
    Turn any iterable into a generator of batches of batch size n
    from: https://stackoverflow.com/a/8290508
    """
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]


async def get_3levels(ext):
    return f'{ext.subdomain.split(".")[-1]}.{ext.domain}.{ext.suffix}'


async def is_tracker(ext, trackers):
    return (
            ext.fqdn in trackers
            or ext.registered_domain in trackers
            # 3 levels
            or ((ext.subdomain and await get_3levels(ext)) in trackers)
    )


async def extract_data(url, browser, consent_accept_selectors={}, screenshot=False):
    """
    Open a new browser context with a URL and extract data about cookies and 
    tracking domains before and after consent.
    Returns:
    - All third party domains requested
    - Third party domains requested before consent
    - Tracking domains before consent
    - All cookies (name, domain, expiration in days)
    - Cookies set before consent
    - Consent manager that was used on the site
    - Screenshot of the site before consenting
    """
    # import files for trackers and privacy policies
    with open(Path(__file__).parent / COOKIE_CHECK_LIST) as trackers_file, \
            open(Path(__file__).parent / PRIVACY_WORD_LIST) as privacy_file, \
            open(Path(__file__).parent / ELIST_DOMAINS) as elist_file, \
            open(Path(__file__).parent / EPRIVACY_DOMAINS) as eprivacy_file, \
            open(Path(__file__).parent / DISCONNECT_LIST) as disconnect_file:
        trackers = [line.strip() for line in trackers_file.readlines()] \
                   + [line.strip() for line in elist_file.readlines()] \
                   + [line.strip() for line in eprivacy_file.readlines()]
        privacy_wording = json.load(privacy_file)
        disconnect_json = json.load(disconnect_file)['categories']

        # Parsing disconnect.me file
        for _, categories in disconnect_json.items():
            for category in categories:
                for _, site in category.items():
                    for _, domains in site.items():
                        if type(domains) == list:
                            trackers += domains

    try:
        if not url.startswith("http"):
            url = "http://" + url

        browser_context = await browser.new_context()
        domain_name = re.search("(?:https?://)?(?:www.)?([^/]+)", url).group(0)
        base64_url = base64.urlsafe_b64encode(domain_name.encode('ascii')).decode('ascii')

        req_urls = []

        page = await browser_context.new_page()
        page.on("request", lambda req: req_urls.append(req.url))

        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(
            5000)  # additional wait time just to be sure as consent managers can sometimes take a while to load

        screenshot_file = ""
        if screenshot:
            await page.screenshot(path=f'../screenshots/screenshot_{base64_url}.png')
            screenshot_file = f'../screenshots/screenshot_{base64_url}.png'

        # init domain extraction
        no_cache_extract = tldextract.TLDExtract(cache_dir=None)
        fl_domain = no_cache_extract(domain_name).domain
        fl_suffix = no_cache_extract(domain_name).suffix

        # Capture data pre-consent
        thirdparty_requests = list(filter(lambda req_url: not domain_name in req_url, req_urls))
        try:
            third_party_domains_no_consent = list(
                set(map(lambda r: re.search("https?://(?:www.)?([^\/]+\.[^\/]+)", r).group(0), thirdparty_requests)))
            for tp in third_party_domains_no_consent:
                if no_cache_extract(tp).domain == fl_domain and no_cache_extract(tp).suffix == fl_suffix:
                    third_party_domains_no_consent.remove(tp)
        except:
            third_party_domains_no_consent = ['error not found']
        tracking_domains_no_consent = list(
            set([re.search("[^\.]+\.[a-z]+$", d).group(0) for d in third_party_domains_no_consent if
                 await is_tracker(no_cache_extract(d), trackers)]))
        if len(tracking_domains_no_consent) != 0:
            no_consent_trackdomain_count[url] = len(tracking_domains_no_consent)

        cookies = await browser_context.cookies()
        cookies_no_consent = [{
            "name": c["name"],
            "domain": c["domain"],
            "expires_days": (date.fromtimestamp(int(c["expires"])) - date.today()).days if int(
                c["expires"]) < 200000000000 else -1,  # prevent out of range errors for the date
            "third_party": not (
                    no_cache_extract(c["domain"]).domain == no_cache_extract(url).domain and
                    no_cache_extract(c["domain"]).suffix == no_cache_extract(url).suffix),
            "httponly": c["httpOnly"],
            "secure": c["secure"],
            "persistent": ((date.fromtimestamp(int(c["expires"])) - date.today()).days if int(
                c["expires"]) < 200000000000 else -1) > 31,  # TODO set constant
            "tracker": await is_tracker(no_cache_extract(c["domain"]), trackers)
        } for c in cookies]

        # List third party cookies without consent
        tp_cookie_count = {}
        for cookie in cookies_no_consent:
            if cookie["third_party"]:
                if cookie["domain"] in tp_cookie_count:
                    tp_cookie_count[cookie["domain"]]["total"] += 1
                else:
                    tp_cookie_count[cookie["domain"]] = {"total": 1, "session": 0, "persistent": 0}
                if cookie["expires_days"] <= 0:
                    tp_cookie_count[cookie["domain"]]["session"] += 1
                elif cookie["expires_days"] >= 365:
                    tp_cookie_count[cookie["domain"]]["persistent"] += 1
            if cookie["tracker"]:
                if url in no_consent_tracker_count:
                    no_consent_tracker_count[url] += 1
                else:
                    no_consent_tracker_count[url] = 1
            if cookie["persistent"]:
                if url in no_consent_persistent_count:
                    no_consent_persistent_count[url] += 1
                else:
                    no_consent_persistent_count[url] = 1

        # try to accept all cookies
        consent_manager = "none detected"
        for k in consent_accept_selectors.keys():
            if await page.locator(consent_accept_selectors[k]).count() > 0:
                consent_manager = k
                try:
                    # explicit wait for navigation as some pages will reload after accepting cookies
                    async with page.expect_navigation(wait_until="networkidle", timeout=15000):
                        await page.click(consent_accept_selectors[k], delay=10)
                except Exception as e:
                    logging.debug(url, e)
                break

        await page.wait_for_timeout(
            10000)  # additional wait time just to be sure as consent managers can sometimes take a while to load
        print(url, consent_manager)
        thirdparty_requests = list(filter(lambda req_url: not domain_name in req_url, req_urls))
        try:
            third_party_domains_all = list(
                set(map(lambda r: re.search("https?://(?:www.)?([^\/]+\.[^\/]+)", r).group(0), thirdparty_requests)))
            for tp in third_party_domains_all:
                if no_cache_extract(tp).domain == fl_domain and no_cache_extract(tp).suffix == fl_suffix:
                    third_party_domains_all.remove(tp)
        except:
            third_party_domains_all = ['error not found']
        tracking_domains_all = list(
            set([re.search("[^\.]+\.[a-z]+$", d).group(0) for d in third_party_domains_all if
                 await is_tracker(no_cache_extract(d), trackers)]))
        consent_trackdomain_count[url] = len(tracking_domains_all)

        cookies = await browser_context.cookies()

        cookies_all = [{
            "name": c["name"],
            "domain": c["domain"],
            "expires_days": (date.fromtimestamp(int(c["expires"])) - date.today()).days if int(
                c["expires"]) < 200000000000 else -1,
            "third_party": not (
                    no_cache_extract(c["domain"]).domain == no_cache_extract(url).domain and
                    no_cache_extract(c["domain"]).suffix == no_cache_extract(url).suffix),
            "httponly": c["httpOnly"],
            "secure": c["secure"],
            "persistent": ((date.fromtimestamp(int(c["expires"])) - date.today()).days if int(
                c["expires"]) < 200000000000 else -1) > 31,  # TODO set constant
            "tracker": await is_tracker(no_cache_extract(c["domain"]), trackers)
        } for c in cookies]

        for cookie in cookies_all:
            if cookie["tracker"]:
                if url in consent_tracker_count:
                    consent_tracker_count[url] += 1
                else:
                    consent_tracker_count[url] = 1
            if cookie["persistent"]:
                if url in consent_persistent_count:
                    consent_persistent_count[url] += 1
                else:
                    consent_persistent_count[url] = 1

        # setup driver for finding privacy policy
        driver, https = setup_driver(url)

        gdpr_references = 0
        privacy_policies = set()
        for privacy_words in privacy_wording:
            # Only doing NL and EN
            if privacy_words['country'] not in ['en', 'nl']:
                continue

            for word in privacy_words['words']:
                try:
                    privacy_policy = driver.find_element(
                        f"//a [contains( text(), '{word}')]")
                    if link := privacy_policy.get_attribute('href'):
                        privacy_policies.add(link)
                except Exception:
                    # Ignore errors from XPath
                    pass

        privacy_policy = {
            'xpath_results': list(privacy_policies),
            'google_results': []
        }

        if len(privacy_policies) == 0:
            google_results = search_google(
                driver, f'privacy policy site:{url}')
            privacy_policy['google_results'] = [
                result for result in google_results if 'privacy' in result.lower()]

        xpath_results = privacy_policy['xpath_results']
        google_results = privacy_policy['google_results']
        if len(xpath_results) > 0:
            privacy_policy['link'] = xpath_results[0]
        elif len(google_results) > 0:
            privacy_policy['link'] = google_results[0]
        else:
            privacy_policy['link'] = 'ERROR'

        await browser_context.close()

        return {
            "id": base64_url,
            "url": url,
            "cookies_all": cookies_all,
            "cookies_no_consent": cookies_no_consent,
            "third_party_domains_all": third_party_domains_all,
            "third_party_domains_no_consent": third_party_domains_no_consent,
            "third_party_cookies_no_consent": tp_cookie_count,
            "tracking_domains_all": tracking_domains_all,
            "tracking_domains_no_consent": tracking_domains_no_consent,
            "consent_manager": consent_manager,
            "privacy_policy": privacy_policy,
            "screenshot": screenshot_file
        }
    except Exception as e:
        logging.debug(url, e)
        return None


async def process_urls(urls, conn, batch_size, consent_accept_selectors, headless=True, screenshot=True,
                       ndjson=False):
    """
    Start the Playwright browser, run the URLs to test in batches asynchronously
    and write the data to a file.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        if headless:
            time.sleep(5)

        results = []
        for urls_batch in batch(urls, batch_size):
            data = [extract_data(url, browser, consent_accept_selectors, screenshot) for url in urls_batch]
            results.extend([r for r in await asyncio.gather(*data) if r])  # run all urls in parallel

        await browser.close()

        insert_stmt1 = "INSERT OR REPLACE INTO gdprtxt (SITE_DOMAIN, COOKIE_NAME, COOKIE_DOMAIN, DURATION, THIRD_PARTY, OPTIONAL, HTTPONLY, SECURE) VALUES (?, ?, ?, ?, ?, ?, ?, ? );"

        for site in results:
            for cookie in site['cookies_all']:
                cookie_name = cookie['name'].lower().strip()
                cookie_domain = cookie['domain'].lower().strip()
                duration = cookie['expires_days']
                third_party = cookie['third_party']
                optional = cookie not in site['cookies_no_consent'] and site['consent_manager'] != 'none detected'
                httponly = cookie["httponly"]
                secure = cookie['secure']
                hostname = site['url']
                c = conn.cursor()
                try:
                    c.execute(insert_stmt1,
                              (hostname, cookie_name, cookie_domain, duration, third_party, optional, httponly, secure))
                    # Save (commit) the changes
                    conn.commit()
                    if (c.rowcount > 0):
                        sql_rows = c.rowcount
                except sqlite3.OperationalError as err:
                    print(err)
                    print(insert_stmt1)
                    print(hostname, cookie_name, cookie_domain, duration, third_party, optional, httponly, secure)

                insert_stmt = "INSERT OR REPLACE INTO gdprtxt_privacypolicy (SITE_DOMAIN, LOCATION) VALUES (?, ?);"
                c = conn.cursor()
                try:
                    c.execute(insert_stmt, (site['url'], site['privacy_policy']['link']))
                    # Save (commit) the changes
                    conn.commit()
                    if (c.rowcount > 0):
                        sql_rows = c.rowcount
                except sqlite3.OperationalError as err:
                    print(err)
                    print(insert_stmt)
                    print(site['url'])

                insert_stmt2 = "INSERT OR REPLACE INTO gdprtxt_banner (SITE_DOMAIN, BANNER, CMP) VALUES (?, ?, ?);"
                c = conn.cursor()
                try:
                    c.execute(insert_stmt2,
                              (site['url'], site['consent_manager'] != 'none detected', site['consent_manager']))
                    # Save (commit) the changes
                    conn.commit()
                    if (c.rowcount > 0):
                        sql_rows = c.rowcount
                except sqlite3.OperationalError as err:
                    print(err)
                    print(insert_stmt2)
                    print(site['url'])

        with open(JSON_FILE, 'w') as f:
            if ndjson:
                f.writelines([json.dumps(r) + "\n" for r in results])
            else:
                f.write(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('url')
    parser.add_argument('--debug', default=False, action="store_true")
    parser.add_argument('--ndjson', default=False, action="store_true")
    parser.add_argument('--headless', default=False, action="store_true")
    parser.add_argument('--screenshot', default=False, action="store_true")
    parser.add_argument('--batch_size', default=15, type=int)
    parser.add_argument('--gdprtxt', default=False, type=str)
    parser.add_argument('-db', '--database', default=DATABASE, type=str)

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    if not os.path.isdir('screenshots') and args.screenshot:
        os.mkdir('screenshots')

    # List of URLs to test
    urls = []
    if not args.url.startswith("http"):
        # assume it's a file if it doesn't start with http
        with open(args.url, 'r') as f:
            urls = list(set([l.strip().lower() for l in set(f.readlines()) if len(l) > 0]))
    else:
        urls = [args.url]

    # create database
    conn = init_database(args.database)

    # CSS selectors for accepting consent
    consent_accept_selectors = {}
    with open(Path(__file__).parent / CONSENT_MANAGERS, 'r') as f:
        consent_accept_selectors = json.load(f)

    asyncio.run(process_urls(urls, conn, args.batch_size, consent_accept_selectors, args.headless,
                             args.screenshot, args.ndjson))
    print("Websites with tracker cookies:", len(consent_tracker_count), "/", len(urls))
    print("Tracker cookies per website: \n"
          "\t No consent:")
    if no_consent_tracker_count != {}:
        print("\t mean", statistics.mean(no_consent_tracker_count.values()), "\n",
              "\t median", statistics.median(no_consent_tracker_count.values()))
    print("\t Top 5:", *sorted(no_consent_tracker_count.items(), key=lambda item: item[1], reverse=True)[:5], sep='\n\t\t')
    print("\n\t Consent:")
    if consent_tracker_count!= {}:
         print("\t mean", statistics.mean(consent_tracker_count.values()), "\n",
              "\t median", statistics.median(consent_tracker_count.values()))
    print("\t Top 5:", *sorted(consent_tracker_count.items(), key=lambda item: item[1], reverse=True)[:5], sep='\n\t\t')
    print('\n')

    print("Websites with tracker domains:", len(consent_trackdomain_count), "/", len(urls))
    print("Tracker domains per website: \n"
          "\t No consent:")
    if no_consent_trackdomain_count != {}:
        print("\t mean", statistics.mean(no_consent_trackdomain_count.values()), "\n",
              "\t median", statistics.median(no_consent_trackdomain_count.values()))
    print("\t Top 5:", *sorted(no_consent_trackdomain_count.items(), key=lambda item: item[1], reverse=True)[:5], sep='\n\t\t')
    print("\n\t Consent:")
    if consent_trackdomain_count != {}:
        print("\t mean", statistics.mean(consent_trackdomain_count.values()), "\n",
              "\t median", statistics.median(consent_trackdomain_count.values()))
    print("\t Top 5:", *sorted(consent_trackdomain_count.items(), key=lambda item: item[1], reverse=True)[:5], sep='\n\t\t')
    print('\n')

    print("Websites with persistent cookies:", len(consent_persistent_count), "/", len(urls))
    print("Persistent cookies per website: \n"
        "\t No consent:")
    if no_consent_persistent_count != {}:
        print("\t mean", statistics.mean(no_consent_persistent_count.values()), "\n",
              "\t median", statistics.median(no_consent_persistent_count.values()))
    print("\t Top 5:", *sorted(no_consent_persistent_count.items(), key=lambda item: item[1], reverse=True)[:5], sep='\n\t\t')
    print("\n\t Consent:")
    if consent_persistent_count != {}:
        print("\t mean", statistics.mean(consent_persistent_count.values()), "\n",
              "\t median", statistics.median(consent_persistent_count.values()))
    print("\t Top 5:", *sorted(consent_persistent_count.items(), key=lambda item: item[1], reverse=True)[:5], sep='\n\t\t')

if args.gdprtxt:
        db_to_txt(args.database, Path(__file__).parent.parent / args.gdprtxt)
