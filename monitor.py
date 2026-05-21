import os
import re
import json
import subprocess
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
FREITAG_URL = "https://freitag.ch/fr_FR/products/f11-lassie"
STATE_FILE = "seen_bags.json"

def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)

def commit_seen():
    subprocess.run(["git", "config", "user.email", "bot@freitag-monitor"], check=True)
    subprocess.run(["git", "config", "user.name", "Freitag Bot"], check=True)
    subprocess.run(["git", "add", STATE_FILE], check=True)
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode != 0:
        subprocess.run(["git", "commit", "-m", "Update seen bags"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("Etat sauvegarde dans le repo")
    else:
        print("Aucun nouveau sac, rien a committer")

def fetch_bags():
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(FREITAG_URL, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    bags = []
    seen_ids = set()
    for a in soup.select("a[href*='f11-lassie?v=']"):
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
        bags.append({"id": product_id, "url": full_url, "color": color})
    return bags

def screenshot_bag(url, product_id):
    path = f"/tmp/{product_id}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 600, "height": 600})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        for selector in [
            "button:has-text('REFUSER')",
            "button:has-text('Refuser')",
            "input[value='REFUSER']",
            "a:has-text('REFUSER')",
            "[role='button']:has-text('REFUSER')",
        ]:
            try:
                page.click(selector, timeout=2000)
                print(f"Cookies fermes avec : {selector}")
                page.wait_for_timeout(1000)
                break
            except Exception:
                pass
        try:
            page.wait_for_selector("img", timeout=10000)
        except Exception:
            pass
        page.screenshot(path=path, clip={"x": 0, "y": 80, "width": 600, "height": 520})
        print(f"Screenshot OK : {path} ({os.path.getsize(path)} bytes)")
        browser.close()
    return path

def send_telegram(bag):
    caption = f"Nouveau F11 disponible{bag['color']} !\nVoir le sac : {bag['url']}"
    screenshot_path = None
    try:
        screenshot_path = screenshot_bag(bag["url"], bag["id"])
    except Exception as e:
        print(f"Screenshot echoue : {e}")
    if screenshot_path and os.path.exists(screenshot_path):
        with open(screenshot_path, "rb") as photo:
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                files={"photo": photo},
                timeout=30,
            )
            print(f"Telegram photo : {resp.status_code} {resp.text}")
    else:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": caption},
            timeout=10,
        )
        print(f"Telegram message : {resp.status_code} {resp.text}")

def main():
    seen = load_seen()
    bags = fetch_bags()
    new_bags = [b for b in bags if b["id"] not in seen]
    print(f"Sacs F11 trouves : {len(bags)} | Nouveaux : {len(new_bags)}")
    for bag in new_bags:
        send_telegram(bag)
        seen.add(bag["id"])
        print(f"Notifie : {bag['url']}")
    save_seen(seen)
    commit_seen()

if __name__ == "__main__":
    main()
