import os
import json
import hashlib
import requests
from bs4 import BeautifulSoup

# --- Configuration ---
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
    for card in soup.select("a[href*='/fr_FR/products/f41']"):
        href = card.get("href", "")
        if not href or href == "/fr_FR/products/f41-hawaii-five-0":
            continue

        img_tag = card.find("img")
        img_url = img_tag.get("src") or img_tag.get("data-src") if img_tag else None
        if img_url and img_url.startswith("//"):
            img_url = "https:" + img_url

        bag_id = hashlib.md5(href.encode()).hexdigest()
        bags.append({
            "id": bag_id,
            "url": "https://freitag.ch" + href if href.startswith("/") else href,
            "img": img_url,
        })

    return bags

def send_telegram(bag):
    text = (
        "🖤 *Nouveau F41 disponible !*\n"
        f"[Voir le sac sur Freitag]({bag['url']})"
    )
    if bag.get("img"):
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "photo": bag["img"],
                "caption": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
    else:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )

def main():
    seen = load_seen()
    bags = fetch_bags()
    new_bags = [b for b in bags if b["id"] not in seen]

    print(f"Sacs trouvés : {len(bags)} | Nouveaux : {len(new_bags)}")

    for bag in new_bags:
        send_telegram(bag)
        seen.add(bag["id"])
        print(f"  → Notifié : {bag['url']}")

    save_seen(seen)

if __name__ == "__main__":
    main()
