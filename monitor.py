import os
import re
import json
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

def get_image_url(product_id):
    # Freitag utilise cette structure d'URL pour les images produit
    return f"https://freitag.ch/api/images/{product_id}/1?width=600"

def fetch_bags():
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(FREITAG_URL, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    bags = []
    seen_ids = set()

    for a in soup.select("a[href*='?v=']"):
        href = a.get("href", "")
        match = re.search(r"\?v=(\d+)", href)
        if not match:
            continue

        product_id = match.group(1)
        if product_id in seen_ids:
            continue
        seen_ids.add(product_id)

        full_url = "https://freitag.ch" + href if href.startswith("/") else href
        img_url = get_image_url(product_id)

        # Extraire la couleur depuis le texte du lien
        color = ""
        text = a.get_text(" ", strip=True)
        color_match = re.search(r"(RED|BLUE|GREEN|BLACK|WHITE|YELLOW|GREY|ORANGE|SILVER|MULTICOLOR)", text)
        if color_match:
            color = f" · {color_match.group(1)}"

        bags.append({
            "id": product_id,
            "url": full_url,
            "img": img_url,
            "color": color,
        })

    return bags

def send_telegram(bag):
    text = (
        f"🖤 *Nouveau F41 disponible{bag['color']} !*\n"
        f"[Voir le sac sur Freitag]({bag['url']})"
    )
    # Essayer d'envoyer avec photo
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "photo": bag["img"],
            "caption": text,
            "parse_mode": "Markdown",
        },
        timeout=10,
    )
    # Si la photo échoue, envoyer sans photo
    if not resp.ok:
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
