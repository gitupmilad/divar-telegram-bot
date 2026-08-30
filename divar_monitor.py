
import os
import re
import json
import statistics
import time

import requests


# =========================
# تنظیمات
# =========================

SEARCH_URL = "https://api.divar.ir/v8/postlist/w/search"
DETAIL_URL = "https://api.divar.ir/v8/posts-v2/web/{}"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

CITY_ID = "4"  # اصفهان

SEARCH_QUERY = "تیبا 2 مدل 1400"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://divar.ir",
    "Referer": "https://divar.ir/",
}


# =========================
# ابزارهای کمکی
# =========================

def normalize(text):
    """تبدیل اعداد فارسی و عربی و یکسان‌سازی متن"""

    if text is None:
        return ""

    text = str(text)

    replacements = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )

    text = text.translate(replacements)

    text = (
        text
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200c", " ")
        .replace("ـ", "")
        .lower()
    )

    return text


def json_to_text(obj):
    try:
        return json.dumps(
            obj,
            ensure_ascii=False
        )
    except Exception:
        return str(obj)


def send_telegram(text):
    """ارسال پیام به تلگرام"""

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )

    response.raise_for_status()

    print("Telegram message sent.")


# =========================
# جستجوی دیوار
# =========================

def search_divar():

    payload = {
        "city_ids": [CITY_ID],

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
                            "value": SEARCH_QUERY
                        }
                    }
                }
            },

            "server_payload": {
                "@type":
                    "type.googleapis.com/widgets.SearchData.ServerPayload",

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

    response = requests.post(
        SEARCH_URL,
        json=payload,
        headers=HEADERS,
        timeout=30,
    )

    print(
        "Divar search status:",
        response.status_code
    )

    response.raise_for_status()

    return response.json()


# =========================
# استخراج آگهی‌ها
# =========================

def extract_posts(data):

    posts = []

    for widget in data.get(
        "list_widgets",
        []
    ):

        if widget.get(
            "widget_type"
        ) != "POST_ROW":

            continue

        item = widget.get(
            "data",
            {}
        )

        action = item.get(
            "action",
            {}
        )

        payload = action.get(
            "payload",
            {}
        )

        token = payload.get(
            "token"
        )

        if not token:
            continue

        web_info = payload.get(
            "web_info",
            {}
        )

        posts.append({

            "title":
                item.get(
                    "title",
                    ""
                ),

            "price_text":
                item.get(
                    "middle_description_text",
                    ""
                ),

            "location":
                item.get(
                    "bottom_description_text",
                    ""
                ),

            "time_text":
                item.get(
                    "top_description_text",
                    ""
                ),

            "token":
                token,

            "district":
                web_info.get(
                    "district_persian",
                    ""
                ),

            "city":
                web_info.get(
                    "city_persian",
                    "اصفهان"
                ),

            "image_url":
                item.get(
                    "image_url",
                    ""
                ),

            "image_count":
                item.get(
                    "image_count",
                    0
                ),
        })

    return posts


# =========================
# جزئیات آگهی
# =========================

def get_details(token):

    url = DETAIL_URL.format(
        token
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )

        if response.status_code != 200:

            print(
                f"Detail HTTP "
                f"{response.status_code}: "
                f"{token}"
            )

            return {}

        return response.json()

    except Exception as error:

        print(
            f"Detail error "
            f"{token}: {error}"
        )

        return {}


# =========================
# تشخیص تیبا ۲
# =========================

def is_tiba_2(text):

    text = normalize(text)

    # تیبا پلاس را جدا می‌کنیم
    if re.search(
        r"تیبا\s*پلاس",
        text
    ):
        return False

    patterns = [
        r"تیبا\s*2",
        r"تیبا\s*۲",
        r"tiba\s*2",
        r"تیبا\s*دو",
    ]

    return any(
        re.search(
            pattern,
            text
        )
        for pattern in patterns
    )


# =========================
# تشخیص مدل ۱۴۰۰
# =========================

def is_model_1400(text):

    text = normalize(text)

    patterns = [

        r"مدل\s*1400",

        r"سال\s*1400",

        r"تیبا\s*2\s*مدل\s*1400",

        r"تیبا\s*۲\s*مدل\s*1400",

        r"تیبا\s*دو\s*مدل\s*1400",

        r"\b1400\b",
    ]

    return any(
        re.search(
            pattern,
            text
        )
        for pattern in patterns
    )


# =========================
# استخراج قیمت
# =========================

def extract_price(text):

    text = normalize(text)

    if not text:
        return None

    # قیمت‌های چندبخشی
    numbers = re.findall(
        r"\d[\d,]*",
        text
    )

    if not numbers:
        return None

    # بزرگ‌ترین عدد را در نظر می‌گیریم
    values = []

    for number in numbers:

        try:

            value = int(
                number.replace(
                    ",",
                    ""
                )
            )

            if value >= 100_000_000:
                values.append(
                    value
                )

        except ValueError:
            pass

    if not values:
        return None

    return max(values)


# =========================
# استخراج کارکرد
# =========================

def extract_mileage(obj):

    text = normalize(
        json_to_text(obj)
    )

    patterns = [

        r"کارکرد.{0,30}?(\d[\d,]*)",

        r"کارکرد.{0,30}?(\d+)\s*کیلومتر",

        r"(\d[\d,]*)\s*کیلومتر",

        r"(\d[\d,]*)\s*km",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if match:

            value = (
                match.group(1)
                .replace(",", "")
            )

            try:

                return int(value)

            except ValueError:

                pass

    return None


# =========================
# استخراج زمان آگهی
# =========================

def extract_time(post, details):

    candidates = [

        post.get(
            "time_text",
            ""
        ),

        post.get(
            "location",
            ""
        ),

        json_to_text(details),
    ]

    for candidate in candidates:

        text = normalize(
            candidate
        )

        patterns = [

            r"لحظاتی پیش",

            r"دقایقی پیش",

            r"\d+\s*دقیقه پیش",

            r"\d+\s*ساعت پیش",

            r"دیروز",

            r"پریروز",

            r"\d+\s*روز پیش",

            r"هفته",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text
            )

            if match:
                return match.group(0)

    return "نامشخص"


# =========================
# فرمت قیمت
# =========================

def format_price(value):

    if value is None:
        return "نامشخص"

    million = value / 1_000_000

    if million.is_integer():

        return (
            f"{int(million):,} "
            f"میلیون تومان"
        )

    return (
        f"{million:,.1f} "
        f"میلیون تومان"
    )


# =========================
# فرمت کارکرد
# =========================

def format_mileage(value):

    if value is None:
        return "نامشخص"

    return (
        f"{value:,} کیلومتر"
    )


# =========================
# ساخت لینک
# =========================

def post_url(token):

    return (
        "https://divar.ir/v/"
        + token
    )


# =========================
# اصلی
# =========================

def main():

    print()
    print(
        "===================================="
    )
    print(
        "Divar Tiba 2 Model 1400 Monitor"
    )
    print(
        "===================================="
    )

    print(
        "Searching Divar..."
    )

    data = search_divar()

    posts = extract_posts(
        data
    )

    print(
        "Total search results:",
        len(posts)
    )

    all_results = []

    for index, post in enumerate(
        posts,
        1
    ):

        print(
            f"[{index}/{len(posts)}] "
            f"{post['title']}"
        )

        details = get_details(
            post["token"]
        )

        # متن کامل آگهی
        full_text = (
            normalize(
                post["title"]
            )
            + " "
            + normalize(
                json_to_text(details)
            )
        )

        # فیلتر تیبا ۲
        if not is_tiba_2(
            full_text
        ):

            print(
                "  -> Not Tiba 2"
            )

            continue

        # فیلتر مدل ۱۴۰۰
        if not is_model_1400(
            full_text
        ):

            print(
                "  -> Not Model 1400"
            )

            continue

        price = extract_price(
            post["price_text"]
        )

        # اگر قیمت از ردیف پیدا نشد
        if price is None:

            price = extract_price(
                json_to_text(
                    details
                )
            )

        mileage = extract_mileage(
            details
        )

        time_text = extract_time(
            post,
            details
        )

        district = (
            post.get(
                "district"
            )
            or post.get(
                "location"
            )
            or "نامشخص"
        )

        result = {

            "title":
                post["title"],

            "price":
                price,

            "mileage":
                mileage,

            "district":
                district,

            "time":
                time_text,

            "token":
                post["token"],

            "url":
                post_url(
                    post["token"]
                ),
        }

        all_results.append(
            result
        )

        print(
            "  -> MATCH"
        )

        print(
            "     Price:",
            format_price(price)
        )

        print(
            "     Mileage:",
            format_mileage(mileage)
        )

        time.sleep(0.2)

    print()
    print(
        "FILTERED RESULTS:",
        len(all_results)
    )

    # =========================
    # آمار کل نتایج
    # =========================

    priced_results = [
        item
        for item in all_results
        if item["price"] is not None
    ]

    if priced_results:

        prices = [
            item["price"]
            for item in priced_results
        ]

        minimum = min(
            prices
        )

        maximum = max(
            prices
        )

        average = statistics.mean(
            prices
        )

        median = statistics.median(
            prices
        )

    else:

        minimum = None
        maximum = None
        average = None
        median = None

    # =========================
    # گزارش
    # =========================

    header = (
        "🚗 گزارش بازار خودرو\n\n"
        "📍 اصفهان\n"
        "🚘 تیبا ۲ مدل ۱۴۰۰\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🔎 تعداد کل آگهی‌های "
        f"منطبق: {len(all_results)}\n"
        f"💵 دارای قیمت: "
        f"{len(priced_results)}\n\n"
    )

    if priced_results:

        header += (
            "📊 آمار کل نتایج\n\n"
            f"⬇️ کمترین قیمت: "
            f"{format_price(minimum)}\n"
            f"⬆️ بیشترین قیمت: "
            f"{format_price(maximum)}\n"
            f"💰 میانگین قیمت: "
            f"{format_price(average)}\n"
            f"📊 میانه قیمت: "
            f"{format_price(median)}\n\n"
            "━━━━━━━━━━━━━━\n\n"
        )

    else:

        header += (
            "❌ برای آگهی‌های منطبق "
            "قیمت قابل محاسبه پیدا نشد.\n\n"
            "━━━━━━━━━━━━━━\n\n"
        )

    header += (
        "📋 تمام آگهی‌های منطبق:\n\n"
    )

    # =========================
    # اضافه کردن تمام آگهی‌ها
    # =========================

    messages = []

    current_message = header

    for index, item in enumerate(
        all_results,
        1
    ):

        price_text = format_price(
            item["price"]
        )

        mileage_text = format_mileage(
            item["mileage"]
        )

        block = (
            f"{index}. 🚘 "
            f"{item['title']}\n"
            f"💰 قیمت: "
            f"{price_text}\n"
            f"🛣 کارکرد: "
            f"{mileage_text}\n"
            f"📍 {item['district']}\n"
            f"⏰ {item['time']}\n"
            f"🔗 {item['url']}\n\n"
        )

        # محدودیت تلگرام حدود 4096 کاراکتر است
        if (
            len(current_message)
            + len(block)
            > 3800
        ):

            messages.append(
                current_message
            )

            current_message = (
                "📋 ادامه آگهی‌ها:\n\n"
            )

        current_message += block

    if current_message.strip():

        messages.append(
            current_message
        )

    # =========================
    # ارسال
    # =========================

    if not messages:

        send_telegram(
            "🚗 گزارش دیوار\n\n"
            "📍 اصفهان\n"
            "🚘 تیبا ۲ مدل ۱۴۰۰\n\n"
            "❌ هیچ آگهی منطبقی پیدا نشد."
        )

    else:

        for message in messages:

            send_telegram(
                message
            )

            time.sleep(1)

    print()
    print(
        "===================================="
    )
    print(
        "REPORT COMPLETED"
    )
    print(
        "===================================="
    )


if __name__ == "__main__":
    main()

