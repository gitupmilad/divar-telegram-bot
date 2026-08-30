import os
import re
import json
import time
import statistics
import requests

SEARCH_URL = "https://api.divar.ir/v8/postlist/w/search"
CITIES_URL = "https://api.divar.ir/v8/places/cities"

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def normalize(text):
    if not text:
        return ""

    return (
        text.replace("ي", "ی")
        .replace("ك", "ک")
        .replace("۲", "2")
        .replace("۱", "1")
        .replace("۳", "3")
        .replace("۴", "4")
        .replace("۵", "5")
        .replace("۶", "6")
        .replace("۷", "7")
        .replace("۸", "8")
        .replace("۹", "9")
        .replace("۰", "0")
    )


def get_city_id():
    r = requests.get(
        CITIES_URL,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    data = r.json()

    def find(obj):
        if isinstance(obj, dict):
            name = normalize(
                str(
                    obj.get("name")
                    or obj.get("title")
                    or obj.get("name_fa")
                    or ""
                )
            )

            slug = normalize(str(obj.get("slug") or ""))

            if name == "اصفهان" or slug == "isfahan":
                return (
                    obj.get("id")
                    or obj.get("city_id")
                    or obj.get("code")
                )

            for value in obj.values():
                result = find(value)
                if result:
                    return result

        elif isinstance(obj, list):
            for item in obj:
                result = find(item)
                if result:
                    return result

        return None

    city_id = find(data)

    if not city_id:
        raise RuntimeError("شناسه شهر اصفهان پیدا نشد")

    print("Isfahan city ID:", city_id)

    return str(city_id)


def search_divar(city_id):
    payload = {
        "city_ids": [city_id],
        "categories": ["light"],
        "query": "تیبا 2"
    }

    r = requests.post(
        SEARCH_URL,
        json=payload,
        headers=HEADERS,
        timeout=30
    )

    r.raise_for_status()

    return r.json()


def extract_posts(data):
    posts = []

    for widget in data.get("list_widgets", []):

        if widget.get("widget_type") != "POST_ROW":
            continue

        item = widget.get("data", {})
        action = item.get("action", {})
        payload = action.get("payload", {})

        title = item.get("title", "")
        price_text = item.get("middle_description_text", "")
        token = payload.get("token", "")

        location = (
            payload.get("web_info", {})
            .get("district_persian", "")
        )

        title_normal = normalize(title)

        # فقط تیبا 2
        if "تیبا" not in title_normal:
            continue

        if not (
            "2" in title_normal
            or "دو" in title_normal
            or "تیبا۲" in title_normal
        ):
            continue

        # مدل 1400 باید در عنوان/اطلاعات آگهی قابل تشخیص باشد
        if not re.search(r"1400|مدل\s*1400", title_normal):
            continue

        prices = re.findall(
            r"\d[\d,\.]*",
            normalize(price_text)
        )

        if not prices:
            continue

        raw_price = prices[0].replace(",", "").replace(".", "")

        try:
            price = int(raw_price)
        except ValueError:
            continue

        # تبدیل قیمت‌های تومانی به میلیون تومان
        if price > 100000:
            price_million = price / 1_000_000
        else:
            price_million = price

        posts.append({
            "title": title,
            "price": price_million,
            "location": location,
            "token": token,
            "url": f"https://divar.ir/v/{token}"
        })

    return posts


def send_telegram(text):
    url = (
        f"https://api.telegram.org/bot"
        f"{TOKEN}/sendMessage"
    )

    r = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": True
        },
        timeout=30
    )

    r.raise_for_status()


def main():

    print("Finding Isfahan city ID...")
    city_id = get_city_id()

    print("Searching Divar...")
    data = search_divar(city_id)

    posts = extract_posts(data)

    print("Matching posts:", len(posts))

    if not posts:
        send_telegram(
            "🚗 گزارش دیوار\n\n"
            "📍 اصفهان\n"
            "🚘 تیبا ۲ مدل ۱۴۰۰\n\n"
            "امروز آگهی منطبق با فیلتر پیدا نشد."
        )
        return

    prices = [p["price"] for p in posts]

    average = statistics.mean(prices)
    median = statistics.median(prices)

    minimum = min(prices)
    maximum = max(prices)

    # مرتب‌سازی ارزان‌ترین‌ها
    posts.sort(key=lambda x: x["price"])

    message = (
        "🚗 گزارش روزانه بازار\n\n"
        "📍 اصفهان\n"
        "🚘 تیبا ۲ مدل ۱۴۰۰\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🔎 تعداد آگهی: {len(posts)}\n\n"
        f"💰 میانگین: {average:,.0f} میلیون تومان\n"
        f"📊 Median: {median:,.0f} میلیون تومان\n"
        f"⬇️ کمترین: {minimum:,.0f} میلیون تومان\n"
        f"⬆️ بیشترین: {maximum:,.0f} میلیون تومان\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "🔥 ارزان‌ترین آگهی‌ها:\n\n"
    )

    for i, post in enumerate(posts[:10], 1):

        difference = (
            (median - post["price"]) / median * 100
            if median else 0
        )

        opportunity = ""

        if difference >= 10:
            opportunity = " 🔥 فرصت احتمالی"

        message += (
            f"{i}️⃣ {post['price']:,.0f} میلیون"
            f"{opportunity}\n"
            f"{post['title']}\n"
            f"📍 {post['location']}\n"
            f"🔗 {post['url']}\n\n"
        )

    message += (
        "━━━━━━━━━━━━━━\n"
        "⚠️ تحلیل فقط بر اساس قیمت آگهی است و "
        "سلامت یا ارزش واقعی خودرو را تأیید نمی‌کند."
    )

    send_telegram(message)

    print("Telegram report sent.")


if __name__ == "__main__":
    main()
