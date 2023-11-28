# data-collector
Automatically audit for GDPR/CCPA by running a Playwright browser to check for marketing and analytics scripts firing before and after consent. The program registers all cookies before and after accepting the consent banner, finds third party domains, counts trackers and persistent cookies, registers the banner and privacy policy. 

## How it works
Playwright allows you to automate browser windows. This script takes a list of URLs, runs a Playwright browser instance and fetches data about cookies and requested domains for each URL. The URLs are fetched asynchronously and in batches to speed up the process. After the URL is fetched, the script tries to identify the consent manager and click 'accept' to determine if and what marketing and analytics tags are fired before and after consent. It uses a 'tracker list' to determine whether a domain is a tracking (marketing/analytics) domain.

## CLI Arguments
| Argument | Description |
|----------|-------------|
| url      | either a single URL starting with 'http' or file containing one url per line
| --batch_size | Number of URLs to open simultaneously, default is 15 |
| --debug   | Flag to log output for debugging |
| --nd_json | Add flag to store output as new line delimited JSON for use in e.g. BigQuery |
|--screenshot   | Flag to save screenshots |
|--headless   | Flag to hide actual browser windows |
|--gdprtxt  | Flag to create gdprtxt file and give file name  |
|-db, --database  | Name of database, default is gdpr.db  |

## Installation
First install Playwright:
`pip install playwright`

 And the Playwright browsers:
 `playwright install`
 
The necessary packages can be found in the `analyse/requirements.txt` file and installed using [pip](https://github.com/pypa/pip):
```bash
pip3 install -r analyse/requirements.txt
```
 
### Usage 
You can provide either a single URL or a file with one URL per line.
`python3 main.py "url_list.txt" --batch_size=10 --headless`

Or for a single site, showing the actual browser window
`python3 main.py https://www.gdprtxt.nl`
