import os
import re
import statistics
import time

import requests


SEARCH_URL = "https://api.divar.ir/v8/postlist/w/search"
DETAIL_URL = "https://api.divar.ir/v8/posts-v2/web/{}"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://divar.ir",
    "Referer": "https://divar.ir/",
}


def normalize(text):
    if not text:
        return ""

    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹",
        "0123456789"
    )

    return (
        str(text)
        .translate(table)
        .replace("ي", "ی")
        .replace("ك", "ک")
        .lower()
    )


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
                            "value": "تیبا 2 مدل 1400"
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

    print("Divar search status:", r.status_code)

    r.raise_for_status()

    return r.json()


def get_posts(data):

    posts = []

    for widget in data.get("list_widgets", []):

        if widget.get("widget_type") != "POST_ROW":
            continue

        item = widget.get("data", {})
        action = item.get("action", {})
        payload = action.get("payload", {})

        token = payload.get("token")

        if not token:
            continue

        posts.append({
            "title": item.get("title", ""),
            "price_text": item.get(
                "middle_description_text",
                ""
            ),
            "location": item.get(
                "bottom_description_text",
                ""
            ),
            "token": token,
        })

    return posts


def get_details(token):

    url = DETAIL_URL.format(token)

    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )

        if r.status_code != 200:
            print(
                f"Detail request failed: {token} "
                f"HTTP {r.status_code}"
            )
            return {}

        return r.json()

    except Exception as e:

        print(
            f"Detail error for {token}: {e}"
        )

        return {}


def contains_model_1400(obj):

    text = normalize(obj)

    patterns = [
        r"\b1400\b",
        r"مدل\s*1400",
        r"سال\s*1400",
        r"تیبا\s*2\s*مدل\s*1400",
        r"تیبا\s*۲\s*مدل\s*۱۴۰۰",
    ]

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def is_tiba_2(text):

    text = normalize(text)

    patterns = [
        r"تیبا\s*2",
        r"تیبا\s*۲",
        r"tiba\s*2",
    ]

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def extract_price(text):

    if not text:
        return None

    text = normalize(text)

    numbers = re.findall(
        r"\d[\d,]*",
        text
    )

    if not numbers:
        return None

    try:

        value = int(
            numbers[0].replace(",", "")
        )

    except ValueError:

        return None

    # قیمت‌های خودرو در Divar معمولاً تومان هستند.
    # تبدیل به میلیون تومان
    if value >= 100_000_000:
        return value / 1_000_000

    return None


def main():

    print("================================")
    print("Divar Tiba 2 Model 1400 Monitor")
    print("================================")

    print("Searching Divar...")

    data = search_divar()

    posts = get_posts(data)

    print(
        "Search results:",
        len(posts)
    )

    matches = []

    for index, post in enumerate(
        posts,
        1
    ):

        title = post["title"]

        print(
            f"[{index}/{len(posts)}] {title}"
        )

        # ابتدا عنوان را بررسی می‌کنیم
        title_is_tiba = is_tiba_2(title)
        title_is_1400 = contains_model_1400(
            title
        )

        # اگر عنوان کاملاً منطبق بود
        if title_is_tiba and title_is_1400:

            details = {}

        else:

            # جزئیات آگهی را می‌گیریم
            details = get_details(
                post["token"]
            )

        # متن کامل برای بررسی
        detail_text = normalize(
            json_to_text(details)
        )

        # بررسی تیبا 2
        tiba_match = (
            title_is_tiba
            or is_tiba_2(detail_text)
        )

        # بررسی مدل 1400
        model_match = (
            title_is_1400
            or contains_model_1400(
                detail_text
            )
        )

        if not tiba_match:
            print("  -> Not Tiba 2")
            continue

        if not model_match:
            print("  -> Not Model 1400")
            continue

        price = extract_price(
            post["price_text"]
        )

        if not price:

            print(
                "  -> Price not found"
            )

            continue

        matches.append({
            "title": title,
            "price": price,
            "location": post["location"],
            "token": post["token"],
            "url": (
                "https://divar.ir/v/"
                + post["token"]
            ),
        })

        print(
            f"  -> MATCH: "
            f"{price:,.0f} million"
        )

        time.sleep(0.2)

    print()
    print(
        "MATCHING POSTS:",
        len(matches)
    )

    # اگر نتیجه‌ای نبود
    if not matches:

        message = (
            "🚗 گزارش دیوار\n\n"
            "📍 اصفهان\n"
            "🚘 تیبا ۲ مدل ۱۴۰۰\n\n"
            "❌ امروز آگهی منطبق "
            "با فیلتر پیدا نشد."
        )

        send_telegram(message)

        print(
            "No matching posts."
        )

        return

    # قیمت‌ها
    prices = [
        item["price"]
        for item in matches
    ]

    average = statistics.mean(
        prices
    )

    median = statistics.median(
        prices
    )

    minimum = min(prices)
    maximum = max(prices)

    # مرتب‌سازی از ارزان به گران
    matches.sort(
        key=lambda x: x["price"]
    )

    message = (
        "🚗 گزارش روزانه بازار خودرو\n\n"
        "📍 اصفهان\n"
        "🚘 تیبا ۲ مدل ۱۴۰۰\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🔎 تعداد آگهی: "
        f"{len(matches)}\n\n"
        f"💰 میانگین قیمت: "
        f"{average:,.0f} میلیون تومان\n"
        f"📊 میانه قیمت: "
        f"{median:,.0f} میلیون تومان\n"
        f"⬇️ کمترین قیمت: "
        f"{minimum:,.0f} میلیون تومان\n"
        f"⬆️ بیشترین قیمت: "
        f"{maximum:,.0f} میلیون تومان\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "📋 آگهی‌های منطبق:\n\n"
    )

    for i, item in enumerate(
        matches[:15],
        1
    ):

        message += (
            f"{i}. "
            f"{item['price']:,.0f} میلیون تومان\n"
            f"🚘 {item['title']}\n"
            f"📍 {item['location']}\n"
            f"🔗 {item['url']}\n\n"
        )

    send_telegram(message)

    print(
        "Report successfully sent "
        "to Telegram."
    )


def json_to_text(obj):

    if not obj:
        return ""

    try:
        return json.dumps(
            obj,
            ensure_ascii=False
        )
    except Exception:
        return str(obj)


if __name__ == "__main__":
    main()
