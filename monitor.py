"""
Currently main module for MGIK news monitoring pipeline.
"""

import os
import json
import requests
from dotenv import load_dotenv
from datastore import DecisionsDatabase
import urllib3

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

mgik_news_url = os.getenv("MGIK_NEWS_URL")
mgik_headers = json.loads(os.getenv("MGIK_HEADERS", "{}"))
request_timeout = int(os.getenv("REQUEST_TIMEOUT"))

if not mgik_news_url:
    raise ValueError("MGIK_NEWS_URL variable must be set in a .env file")

# Proxy config
proxy_host = os.getenv("MGIK_PROXY_HOST")
proxy_port = os.getenv("MGIK_PROXY_PORT")
proxy_user = os.getenv("MGIK_PROXY_USER")
proxy_pass = os.getenv("MGIK_PROXY_PASS")

proxies = None
if proxy_host and proxy_port and proxy_user and proxy_pass:
    proxy_url = f"socks5://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
    proxies = {"http": proxy_url, "https": proxy_url}


def fetch_mgik_news(mgik_news_url: str) -> dict:
    """
    Fetch news data from MGIK API endpoint.

    Retrieves news items using environment-configured URL, headers, and proxy settings.
    Performs HTTP GET request with error handling and returns parsed JSON response.

    Returns:
        dict: Parsed JSON response containing news data.
    """

    try:
        resp = requests.get(
            mgik_news_url,
            headers=mgik_headers,
            proxies=proxies,
            timeout=request_timeout,
            verify=False,
        )
        # resp.raise_for_status()
        return {"status": "success", "data": resp.json()}
    except requests.exceptions.Timeout:
        return {"status": "error", "error": f"MGIK timeout ({request_timeout}s)"}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "error": "MGIK connection failed (proxy/offline)"}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "error": f"MGIK HTTP {e.response.status_code}"}
    except json.JSONDecodeError:
        return {"status": "error", "error": "MGIK invalid JSON response"}
    except Exception as e:
        return {"status": "error", "error": f"Unexpected: {str(e)[:100]}"}


def load_decisions_file(filepath: str) -> dict:
    """
    Load decisions data from JSON decisions file.

    Reads and parses JSON file containing decisions data with 'items' structure.

    Args:
        filepath (str): Path to decisions JSON file.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        json.JSONDecodeError: If file contains invalid JSON.
        KeyError: If 'items' key is missing from loaded data.

    Returns:
        list: List of decision items extracted from file.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # return data
    return {"status": "success", "data": data}


def save_to_database(items, db_class=DecisionsDatabase):
    """
    Save decision items to DecisionsDatabase.

    Instantiates database connection and persists items using save_decisions method.

    Args:
        items (list): List of decision items to save.
        db_class (type): Database class to instantiate. Defaults to DecisionsDatabase.

    Returns:
        int: Number of new records inserted.
    """
    db = db_class()
    return db.save_decisions(items)


def load_decisions_from_web_to_database():
    """
    Load decisions data directly from MGIK web API.

    Fetches data using fetch_mgik_news function.

    Returns:
        dict: Parsed JSON response containing news data.
    """

    current_url = mgik_news_url

    while current_url:
        # Fetch data from the current URL
        result = fetch_mgik_news(current_url)
        if result["status"] != "success":
            print(f"Fetch failed: {result['error']}")
            break

        data = result["data"]
        print(f"Fetched {len(data)} items from MGIK API")

        # Extract items and save them to the database
        if not (items := data.get("items")):
            print("No 'items' found in input data")
            break

        new_count = save_to_database(items)
        print(
            f"Inserted {new_count} new records, {len(items) - new_count} duplicates skipped"
        )

        # Stop if no new records were inserted
        if new_count == 0:
            print("No new records inserted, stopping pagination.")
            break

        # Get the next page URL
        current_url = data.get("meta", {}).get("next")
        if not current_url:
            print("No more pages available, stopping pagination.")
            break

        print(f"Fetching next page: {current_url}")


def main():
    """
    Main execution function for MGIK news processing pipeline.

    Orchestrates data fetching (commented), file loading, and database persistence.
    Provides logging for debugging and monitoring pipeline execution.
    """
    load_decisions_from_web_to_database()


if __name__ == "__main__":
    main()
