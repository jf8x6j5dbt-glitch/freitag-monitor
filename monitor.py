import os
import re
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
FREITAG_URL = "https://freitag.ch/fr_FR/products/f41-hawaii-five-0"
STATE_FILE = "seen_bags.json"

def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)

def fetch_bags():
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(FREITAG_URL, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    bags = []
    seen_ids = set()

    for a in soup.select("a[href*='f41-hawaii-five-0?v=']"):
        href = a.get("href", "")
        match = re.search(r"\?v=(\d+)", href)
        if not match:
            continue

        product_id = match.group(1)
        if product_id in seen_ids:
            continue
        seen_ids.add(product_id)

        full_url = "https://freitag.ch" + href if href.startswith("/") else href

        text = a.get_text(" ", strip=True)
        color_match = re.search(r"(RED|BLUE|GREEN|BLACK|WHITE|YELLOW|GREY|ORANGE|SILVER|MULTICOLOR)", text)
        color = f" . {color_match.group(1)}" if color_match else ""

        bags.append({
            "id": product_id,
            "url": full_url,
            "color": color,
        })

    return bags

def screenshot_bag(url, product_id):
    path = f"/tmp/{product_id}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 600, "height": 600})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        print("Texte page:", page.inner_text("body")[:500])
        for selector in ["text=REFUSER", "text=Refuser", "button:has-text('REFUSER')", "button:has-text('Refuser')", "[id*=refuse]", "[class*=refuse]"]:
            try:
                page.click(selector, timeout=2000)
                print(f"  Cookies fermes avec : {selector}")
                page.wait_for_timeout(1000)
                break
            except Exception:
                pass
        try:
            page.wait_for_selector("img", timeout=10000)
        except Exception:
            pass
        page.screenshot(path=path, clip={"x": 0, "y": 80, "width": 600, "height": 520})
        browser.close()
    return path

def send_telegram(bag):
    caption = (
        f"Nouveau F41 disponible{bag['color']} !\n"
        f"Voir le sac : {bag['url']}"
    )
    screenshot_path = None
    try:
        screenshot_path = screenshot_bag(bag["url"], bag["id"])
    except Exception as e:
        print(f"  Screenshot echoue : {e}")

    if screenshot_path and os.path.exists(screenshot_path):
        with open(screenshot_path, "rb") as photo:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                files={"photo": photo},
                timeout=30,
            )
    else:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": caption},
            timeout=10,
        )

def main():
    seen = load_seen()
    bags = fetch_bags()
    new_bags = [b for b in bags if b["id"] not in seen]

    print(f"Sacs F41 trouves : {len(bags)} | Nouveaux : {len(new_bags)}")

