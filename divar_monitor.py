import os
import json
import requests

SEARCH_URL = "https://api.divar.ir/v8/postlist/w/search"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    r = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )

    r.raise_for_status()


def search_divar():
    payload = {
        "city_ids": ["4"],
        "categories": ["light"],
        "query": "تیبا 2",
    }

    r = requests.post(
        SEARCH_URL,
        json=payload,
        headers=HEADERS,
        timeout=30,
    )

    r.raise_for_status()

    return r.json()


def main():

    print("Searching Divar for Tiba 2 in Isfahan...")

    data = search_divar()

    widgets = data.get("list_widgets", [])

    posts = []

    for widget in widgets:

        if widget.get("widget_type") != "POST_ROW":
            continue

        item = widget.get("data", {})
        action = item.get("action", {})
        payload = action.get("payload", {})

        post = {
            "title": item.get("title"),
            "price": item.get("middle_description_text"),
            "location": item.get("bottom_description_text"),
            "token": payload.get("token"),
        }

        posts.append(post)

    print("POST COUNT:", len(posts))

    print(
        json.dumps(
            posts,
            ensure_ascii=False,
            indent=2
        )
    )

    # فقط برای اینکه نتیجه را در Telegram هم ببینیم
    message = "🔎 تست جستجوی تیبا ۲ در اصفهان\n\n"

    if not posts:
        message += "هیچ آگهی‌ای از API برنگشت."
    else:
        message += f"تعداد نتایج: {len(posts)}\n\n"

        for i, post in enumerate(posts[:10], 1):
            message += (
                f"{i}. {post['title']}\n"
                f"💰 {post['price']}\n"
                f"📍 {post['location']}\n"
                f"Token: {post['token']}\n\n"
            )

    send_telegram(message)


if __name__ == "__main__":
    main()
