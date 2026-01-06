import os
import json
import requests
from dotenv import load_dotenv
from datastore import DecisionsDatabase

# from datetime import datetime

load_dotenv()


def fetch_mgik_news():
    mgik_news_url = os.getenv("MGIK_NEWS_URL")
    mgik_headers = json.loads(os.getenv("MGIK_HEADERS", "{}"))

    # Proxy config
    proxy_host = os.getenv("MGIK_PROXY_HOST")
    proxy_port = os.getenv("MGIK_PROXY_PORT")
    proxy_user = os.getenv("MGIK_PROXY_USER")
    proxy_pass = os.getenv("MGIK_PROXY_PASS")

    proxies = None
    if proxy_host:
        proxy_url = f"socks5://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
        proxies = {"http": proxy_url, "https": proxy_url}

    if mgik_news_url is None:
        raise ValueError("URL is not configured")

    resp = requests.get(
        mgik_news_url, headers=mgik_headers, proxies=proxies, timeout=30, verify=False
    )
    resp.raise_for_status()

    return resp.json()


if __name__ == "__main__":
    # data = fetch_mgik_news()
    # print(f"Fetched {len(data)} items at {datetime.now()}")
    # with open("mgik_news.json", "w", encoding="utf-8") as f:
    #     json.dump(data, f, ensure_ascii=False, indent=2)

    with open("solutions.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Loaded {len(data)} solutions from solutions.json")

    db = DecisionsDatabase()
    db.save_decisions(data)
