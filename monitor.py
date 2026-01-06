"""
Currently main module for MGIK news monitoring pipeline.
"""

import os
import json
import requests
from dotenv import load_dotenv
from datastore import DecisionsDatabase

load_dotenv()

mgik_news_url = os.getenv("MGIK_NEWS_URL")
mgik_headers = json.loads(os.getenv("MGIK_HEADERS", "{}"))


def fetch_mgik_news():
    """
    Fetch news data from MGIK API endpoint.

    Retrieves news items using environment-configured URL, headers, and proxy settings.
    Performs HTTP GET request with error handling and returns parsed JSON response.

    Raises:
        ValueError: If MGIK_NEWS_URL environment variable is not set.
        requests.exceptions.RequestException: If HTTP request fails.

    Returns:
        dict: Parsed JSON response containing news data.
    """

    if not mgik_news_url:
        raise ValueError("MGIK_NEWS_URL variable must be set in a .env file")

    # Proxy config
    proxy_host = os.getenv("MGIK_PROXY_HOST")
    proxy_port = os.getenv("MGIK_PROXY_PORT")
    proxy_user = os.getenv("MGIK_PROXY_USER")
    proxy_pass = os.getenv("MGIK_PROXY_PASS")

    proxies = None
    if proxy_host:
        proxy_url = f"socks5://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
        proxies = {"http": proxy_url, "https": proxy_url}

    resp = requests.get(
        mgik_news_url, headers=mgik_headers, proxies=proxies, timeout=30, verify=False
    )
    resp.raise_for_status()

    return resp.json()


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

    return data


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


def main():
    """
    Main execution function for MGIK news processing pipeline.

    Orchestrates data fetching (commented), file loading, and database persistence.
    Provides logging for debugging and monitoring pipeline execution.
    """

    # # Fetch live data from MGIK API
    data = fetch_mgik_news()
    print(f"Fetched {len(data)} items from MGIK API")
    with open("solutions.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Load from local solutions file
    # data = load_decisions_file("solutions.json")
    if not (items := data.get("items")):
        raise ValueError("No 'items' found in solutions.json")

    print(f"Loaded {len(items)} decision items from solutions.json")

    # Persist to database
    new_count = save_to_database(items)
    print(
        f"Inserted {new_count} new records ({len(items) - new_count} duplicates skipped)"
    )

    # # Pagination: fetch next pages if new records were found
    # data = fetch_mgik_news()
    # total_new = 0
    # page = 1
    #
    # while True:
    #     items = data.get("items", [])
    #     print(f"Page {page}: Fetched {len(items)} items")
    #
    #     new_count = save_to_database(items)
    #     total_new += new_count
    #     print(f"  Inserted {new_count} new records")
    #
    #     # Check if there are new records and a next page
    #     next_url = data.get("meta", {}).get("next")
    #     if new_count > 0 and next_url:
    #         print(f"  Fetching next page: {next_url}")
    #         resp = requests.get(next_url, headers=mgik_headers, timeout=30, verify=False)
    #         resp.raise_for_status()
    #         data = resp.json()
    #         page += 1
    #     else:
    #         if new_count == 0:
    #             print(f"  No new records, stopping pagination")
    #         if not next_url:
    #             print(f"  No more pages available")
    #         break
    #
    # print(f"\nTotal: {total_new} new records inserted across {page} page(s)")


if __name__ == "__main__":
    main()
