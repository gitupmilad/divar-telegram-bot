import os
import requests
import json

SEARCH_URL = "https://api.divar.ir/v8/postlist/w/search"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://divar.ir",
    "Referer": "https://divar.ir/",
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

        "search_data": {
            "form_data": {
                "data": {
                    "category": {
                        "str": {
                            "value": "ROOT"
                        }
                    },
                    "query": {
                        "str": {
                            "value": "تیبا 2"
                        }
                    }
                }
            },

            "server_payload": {
                "@type": "type.googleapis.com/widgets.SearchData.ServerPayload",
                "additional_form_data": {
                    "data": {
                        "sort": {
                            "str": {
                                "value": "sort_date"
                            }
                        }
                    }
                }
            }
        }
    }

    r = requests.post(
        SEARCH_URL,
        json=payload,
        headers=HEADERS,
        timeout=30,
    )

    print("STATUS:", r.status_code)

    r.raise_for_status()

    return r.json()


def main():

    print("Searching real Divar text search...")

    data = search_divar()

    posts = []

    for widget in data.get("list_widgets", []):

        if widget.get("widget_type") != "POST_ROW":
            continue

        item = widget.get("data", {})
        action = item.get("action", {})
        payload = action.get("payload", {})

        posts.append({
            "title": item.get("title", ""),
            "price": item.get("middle_description_text", ""),
            "location": item.get("bottom_description_text", ""),
            "token": payload.get("token", "")
        })

    print("RESULT COUNT:", len(posts))

    print(
        json.dumps(
            posts[:20],
            ensure_ascii=False,
            indent=2
        )
    )

    message = "🔎 تست جستجوی واقعی Divar\n\n"

    if not posts:

        message += "❌ هیچ نتیجه‌ای دریافت نشد."

    else:

        message += f"تعداد نتایج: {len(posts)}\n\n"

        for i, post in enumerate(posts[:10], 1):

            message += (
                f"{i}. {post['title']}\n"
                f"💰 {post['price']}\n"
                f"📍 {post['location']}\n"
                f"🔑 {post['token']}\n\n"
            )

    send_telegram(message)


if __name__ == "__main__":
    main()
