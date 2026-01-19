"""
A module that fetches news data from the MosGorIzbirKom (MGIK) API, processes it,
and saves it to a local SQLite database using the DecisionsDatabase class.
"""

import os
import json
import random
from datetime import datetime
import requests
import urllib3
from dotenv import load_dotenv
from datastore import DecisionsDatabase

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

mgik_news_url = os.getenv("MGIK_NEWS_URL")
mgik_headers = json.loads(os.getenv("MGIK_HEADERS", "{}"))
request_timeout = int(os.getenv("REQUEST_TIMEOUT", "0"))

if not mgik_news_url:
    raise ValueError("MGIK_NEWS_URL variable must be set in a .env file")

# Proxy config
proxy_host = os.getenv("MGIK_PROXY_HOST")
proxy_port = os.getenv("MGIK_PROXY_PORT")
proxy_user = os.getenv("MGIK_PROXY_USER")
proxy_pass = os.getenv("MGIK_PROXY_PASS")

earliest_date_str = os.getenv("MGIK_EARLIEST_DATE", "1970-01-01")
earliest_date = datetime.strptime(earliest_date_str, "%Y-%m-%d")

if proxy_host and proxy_port and proxy_user and proxy_pass:
    proxy_url = f"socks5://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
    PROXIES = {"http": proxy_url, "https": proxy_url}
else:
    PROXIES = None


def fetch_mgik_news(mgik_url: str) -> dict:
    """
    Fetch news data from MGIK API endpoint.

    Retrieves news items using environment-configured URL, headers, and proxy settings.
    Performs HTTP GET request with error handling and returns parsed JSON response.

    Returns:
        dict: Parsed JSON response containing news data.
    """

    try:
        resp = requests.get(
            mgik_url,
            headers=mgik_headers,
            proxies=PROXIES,
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

        # look for oldest date in items
        oldest_date_in_items = min(
            datetime.strptime(item["date"], "%Y-%m-%d") for item in items
        )
        if oldest_date_in_items < earliest_date:
            print(
                f"Oldest date in items {oldest_date_in_items} "
                "is less than setup earliest date "
                f"{earliest_date}, stopping pagination."
            )
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


def process_attachments():
    """
    List all files in attchments/ directory.
    List all attachments in the database.
    Understand which attachments are missing.
    Load missing attachments by downloading them.

    Uses DecisionsDatabase to find and download missing attachments.
    """

    db = DecisionsDatabase()
    links_to_files_in_db = db.get_all_files()
    # it's a list like ['http://www.mosgorizbirkom.ru/documents/69395/CustomDocument_69395.pdf',
    # 'http://www.mosgorizbirkom.ru/documents/69384/CustomDocument_69384.pdf']
    links_and_filenames_in_db = [
        {"link": link, "filename": link.split("/")[-1]} for link in links_to_files_in_db
    ]

    os.makedirs("attachments", exist_ok=True)
    files_in_attachments_dir = os.listdir("attachments/")

    missing_attachments = [
        x
        for x in links_and_filenames_in_db
        if x["filename"] not in files_in_attachments_dir
    ]

    # Shuffle the missing attachments list
    random.shuffle(missing_attachments)

    failed_downloads = []

    for file in missing_attachments:
        print(
            f"Downloading missing attachment: {file['filename']} from link {file['link']}"
        )
        try:
            response = requests.get(
                file["link"],
                proxies=PROXIES,
                headers=mgik_headers,
                timeout=request_timeout,
                stream=True,
                verify=False,
            )

            response.raise_for_status()  # Raise an error for HTTP codes 4xx/5xx

            # Save the file to the attachments directory
            with open(f"attachments/{file['filename']}", "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"Downloaded: {file['filename']}")

        except requests.exceptions.RequestException as e:
            print(f"Failed to download {file['filename']} from {file['link']}: {e}")
            failed_downloads.append(file)

    return failed_downloads
