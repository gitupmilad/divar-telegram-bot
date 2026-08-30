import os
import re
import statistics
from datetime import datetime

import requests


# =========================
# Configuration
# =========================

CITY = "isfahan"

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}


# =========================
# Telegram
# =========================

def send_telegram(message):
    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )

    response.raise_for_status()


# =========================
# Divar
# =========================

def get_divar_page():
    url = f"https://divar.ir/s/{CITY}"

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    return response.text


# =========================
# Persian numbers
# =========================

def normalize_digits(text):
    if not text:
        return text

    translation = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789",
    )

    return text.translate(translation)


# =========================
# Price extraction
# =========================

def extract_prices(text):
    text = normalize_digits(text)

    prices = []

    patterns = [
        r"(\d[\d,]*)\s*(?:تومان|میلیون)",
        r"(\d[\d,]*)\s*میلیارد",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text):
            try:
                value = int(match.replace(",", ""))

                if "میلیارد" in pattern:
                    value *= 1000

                if 50 <= value <= 5000:
                    prices.append(value)

            except ValueError:
                pass

    return prices


# =========================
# Main
# =========================

def main():

    try:

        print("Connecting to Divar...")

        html = get_divar_page()

        print("Divar HTTP request successful.")
        print("Page size:", len(html))

        prices = extract_prices(html)

        # Remove duplicates
        prices = sorted(set(prices))

        print("Detected prices:", prices)

        if not prices:

            message = (
                "⚠️ پایش دیوار\n\n"
                "امروز نتوانستم قیمت معتبر تیبا ۲ مدل ۱۴۰۰ "
                "را از داده‌های دیوار استخراج کنم.\n\n"
                "احتمالاً ساختار داده دیوار تغییر کرده است."
            )

            send_telegram(message)
            return

        average = statistics.mean(prices)
        median = statistics.median(prices)
        minimum = min(prices)
        maximum = max(prices)

        message = (
            "🚗 گزارش روزانه دیوار\n\n"
            "📍 اصفهان\n"
            "🚘 تیبا ۲\n"
            "📅 مدل ۱۴۰۰\n\n"
            "━━━━━━━━━━━━━━\n\n"
            f"🔎 تعداد قیمت‌های شناسایی‌شده: {len(prices)}\n\n"
            f"💰 میانگین: {average:,.0f} میلیون تومان\n"
            f"📊 Median: {median:,.0f} میلیون تومان\n"
            f"⬇️ کمترین: {minimum:,.0f} میلیون تومان\n"
            f"⬆️ بیشترین: {maximum:,.0f} میلیون تومان\n\n"
            "━━━━━━━━━━━━━━\n\n"
            "⚠️ این نسخه اولیه است و در مرحله بعد "
            "استخراج دقیق آگهی‌ها، مدل خودرو و لینک آگهی‌ها "
            "اضافه می‌شود."
        )

        send_telegram(message)

        print("Telegram report sent successfully.")

    except Exception as e:

        print("ERROR:", repr(e))

        try:
            send_telegram(
                "❌ خطا در اجرای پایش دیوار\n\n"
                f"{type(e).__name__}: {e}"
            )
        except Exception:
            pass

        raise


if __name__ == "__main__":
    main()
