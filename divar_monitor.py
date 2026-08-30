import os
import re
import json
import statistics
import time

import requests


# ============================================================
# تنظیمات
# ============================================================

SEARCH_URL = "https://api.divar.ir/v8/postlist/w/search"
DETAIL_URL = "https://api.divar.ir/v8/posts-v2/web/{}"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# اصفهان
CITY_ID = "4"

# عبارت جستجوی اصلی
SEARCH_QUERY = "تیبا 2 مدل 1400"

# حداکثر تعداد نتایج برای بررسی
# None یعنی همه نتایج برگشتی Divar بررسی شوند.
MAX_RESULTS = None

# محدوده منطقی قیمت خودرو
# قیمت‌ها به ریال هستند.
MIN_VALID_PRICE = 100_000_000
MAX_VALID_PRICE = 5_000_000_000

# محدوده منطقی کارکرد
MIN_VALID_MILEAGE = 0
MAX_VALID_MILEAGE = 1_000_000


HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://divar.ir",
    "Referer": "https://divar.ir/",
}


# ============================================================
# ابزارهای عمومی
# ============================================================

def normalize(text):
    """
    تبدیل اعداد فارسی/عربی به انگلیسی و یکسان‌سازی متن.
    """

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


def clean_number(value):
    """
    تبدیل عدد فارسی/عربی/رشته‌ای به int یا float.
    """

    if value is None:
        return None

    text = normalize(value)

    text = (
        text
        .replace(",", "")
        .replace("٬", "")
        .replace("٫", ".")
        .strip()
    )

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        text
    )

    if not match:
        return None

    try:
        number = float(match.group(0))

        if number.is_integer():
            return int(number)

        return number

    except Exception:
        return None


# ============================================================
# تلگرام
# ============================================================

def send_telegram(text):
    """
    ارسال پیام به تلگرام.
    """

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

    if not response.ok:
        print("Telegram HTTP status:", response.status_code)
        print("Telegram response:", response.text)

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"Telegram API error: {result}"
        )

    print("Telegram message sent.")


# ============================================================
# جستجوی Divar
# ============================================================

def search_divar():

    payload = {
        "city_ids": [
            CITY_ID
        ],

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


# ============================================================
# استخراج آگهی‌های جستجو
# ============================================================

def extract_posts(data):

    posts = []

    widgets = data.get(
        "list_widgets",
        []
    )

    for widget in widgets:

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

            # این مقدار منبع اصلی قیمت است
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


# ============================================================
# جزئیات آگهی
# ============================================================

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


# ============================================================
# تشخیص تیبا ۲
# ============================================================

def is_tiba_2(text):

    text = normalize(text)

    # تیبا پلاس نباید جزو نتایج باشد
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

    for pattern in patterns:

        if re.search(
            pattern,
            text
        ):
            return True

    return False


# ============================================================
# تشخیص مدل ۱۴۰۰
# ============================================================

def is_model_1400(text):

    text = normalize(text)

    # حالت‌های مختلف نوشتن مدل 1400
    patterns = [

        r"مدل\s*1400",

        r"مدل\s*۱۴۰۰",

        r"سال\s*1400",

        r"سال\s*۱۴۰۰",

        r"تیبا\s*2\s*مدل\s*1400",

        r"تیبا\s*۲\s*مدل\s*1400",

        r"تیبا\s*دو\s*مدل\s*1400",

        r"تیبا\s*2\s*مدل\s*۱۴۰۰",

        r"تیبا\s*۲\s*مدل\s*۱۴۰۰",

        r"تیبا\s*دو\s*مدل\s*۱۴۰۰",

        r"\b1400\b",
    ]

    for pattern in patterns:

        if re.search(
            pattern,
            text
        ):
            return True

    return False


# ============================================================
# استخراج قیمت از متن نتیجه جستجو
# ============================================================

def extract_price_from_search_text(text):

    """
    فقط از متن قیمت خود POST_ROW قیمت را استخراج می‌کنیم.

    نکته مهم:
    قبلاً کل JSON جزئیات آگهی به این تابع داده می‌شد
    و بزرگ‌ترین عدد به عنوان قیمت انتخاب می‌شد.
    این باعث خطای 776,138.9 میلیون شده بود.

    این تابع فقط قیمت‌های مشخص‌شده در متن نتیجه جستجو را
    قبول می‌کند.
    """

    if text is None:
        return None

    text = normalize(text)

    if not text:
        return None

    # آگهی‌هایی که قیمت ندارند
    invalid_words = [
        "توافقی",
        "رایگان",
        "معاوضه",
        "نامشخص",
        "none",
    ]

    for word in invalid_words:

        if word in text:
            return None

    # حذف کلمات غیرعددی
    numbers = re.findall(
        r"\d+(?:,\d+)*(?:\.\d+)?",
        text
    )

    if not numbers:
        return None

    candidates = []

    for number in numbers:

        value = clean_number(
            number
        )

        if value is None:
            continue

        # اگر متن بر اساس میلیون نوشته شده باشد
        if "میلیون" in text:

            value = float(value) * 1_000_000

        # اگر میلیارد باشد
        elif "میلیارد" in text:

            value = float(value) * 1_000_000_000

        # اگر قیمت مستقیم ریالی باشد
        else:

            # اعداد خیلی کوچک احتمالاً قیمت نیستند
            if value < 1_000_000:
                continue

        value = int(value)

        if (
            MIN_VALID_PRICE
            <= value
            <= MAX_VALID_PRICE
        ):
            candidates.append(
                value
            )

    if not candidates:
        return None

    # در متن قیمت، آخرین مقدار معتبر را برمی‌گردانیم
    return candidates[-1]


# ============================================================
# استخراج قیمت از فیلدهای صریح JSON
# ============================================================

def extract_price_from_explicit_fields(obj):

    """
    فقط فیلدهایی که نامشان به قیمت مربوط است بررسی می‌شوند.

    هرگز کل JSON را به صورت عددی اسکن نمی‌کنیم.
    """

    price_keys = {
        "price",
        "pricevalue",
        "price_value",
        "amount",
        "amountvalue",
        "amount_value",
        "value",
    }

    results = []

    def walk(value, parent_key=""):

        if isinstance(value, dict):

            for key, child in value.items():

                key_normalized = normalize(key)
                key_normalized = (
                    key_normalized
                    .replace("_", "")
                    .replace("-", "")
                )

                # فقط فیلدهایی که در مسیر قیمت هستند
                is_price_key = (
                    key_normalized in price_keys
                    or "price" in key_normalized
                    or "amount" in key_normalized
                )

                if is_price_key:

                    numeric = clean_number(
                        child
                    )

                    if numeric is not None:

                        # بعضی APIها مقدار را میلیون یا ریال می‌دهند.
                        # فقط مقادیر منطقی را قبول می‌کنیم.

                        numeric = float(
                            numeric
                        )

                        if (
                            MIN_VALID_PRICE
                            <= numeric
                            <= MAX_VALID_PRICE
                        ):
                            results.append(
                                int(numeric)
                            )

                        # اگر مقدار به میلیون باشد
                        elif (
                            100
                            <= numeric
                            <= 5000
                        ):
                            results.append(
                                int(
                                    numeric
                                    * 1_000_000
                                )
                            )

                walk(
                    child,
                    key_normalized
                )

        elif isinstance(value, list):

            for child in value:

                walk(
                    child,
                    parent_key
                )

    walk(obj)

    if not results:
        return None

    # اگر چند مقدار قیمت وجود داشت،
    # مقداری را که در محدوده منطقی خودرو است انتخاب می‌کنیم.
    valid = [
        value
        for value in results
        if (
            MIN_VALID_PRICE
            <= value
            <= MAX_VALID_PRICE
        )
    ]

    if not valid:
        return None

    # نزدیک‌ترین مقدار به محدوده معمول خودرو
    # در این پروژه بزرگ‌ترین مقدار معتبر معمولاً قیمت نهایی است.
    return max(valid)


# ============================================================
# استخراج کارکرد
# ============================================================

def extract_mileage(obj):

    text = normalize(
        json_to_text(obj)
    )

    if not text:
        return None

    patterns = [

        r"کارکرد.{0,50}?(\d[\d,]*)\s*کیلومتر",

        r"کارکرد.{0,50}?(\d[\d,]*)",

        r"(\d[\d,]*)\s*کیلومتر",

        r"(\d[\d,]*)\s*km",
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text
        )

        for value_text in matches:

            value = clean_number(
                value_text
            )

            if value is None:
                continue

            value = int(value)

            if (
                MIN_VALID_MILEAGE
                <= value
                <= MAX_VALID_MILEAGE
            ):
                return value

    return None


# ============================================================
# استخراج زمان
# ============================================================

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

    for candidate in candidates:

        text = normalize(
            candidate
        )

        for pattern in patterns:

            match = re.search(
                pattern,
                text
            )

            if match:

                return match.group(0)

    return "نامشخص"


# ============================================================
# فرمت قیمت
# ============================================================

def format_price(value):

    if value is None:
        return "نامشخص"

    million = float(value) / 1_000_000

    if million.is_integer():

        return (
            f"{int(million):,} "
            f"میلیون تومان"
        )

    return (
        f"{million:,.1f} "
        f"میلیون تومان"
    )


# ============================================================
# فرمت کارکرد
# ============================================================

def format_mileage(value):

    if value is None:
        return "نامشخص"

    return (
        f"{value:,} کیلومتر"
    )


# ============================================================
# لینک آگهی
# ============================================================

def post_url(token):

    return (
        "https://divar.ir/v/"
        + token
    )


# ============================================================
# حذف آگهی‌های تکراری
# ============================================================

def deduplicate_posts(posts):

    unique = []
    seen = set()

    for post in posts:

        token = post.get(
            "token"
        )

        if not token:
            continue

        if token in seen:
            continue

        seen.add(token)

        unique.append(
            post
        )

    return unique


# ============================================================
# ساخت گزارش آماری
# ============================================================

def calculate_statistics(results):

    prices = [
        item["price"]
        for item in results
        if (
            item.get("price") is not None
            and
            MIN_VALID_PRICE
            <= item["price"]
            <= MAX_VALID_PRICE
        )
    ]

    if not prices:

        return {
            "count": len(results),
            "priced_count": 0,
            "minimum": None,
            "maximum": None,
            "average": None,
            "median": None,
        }

    return {
        "count": len(results),

        "priced_count":
            len(prices),

        "minimum":
            min(prices),

        "maximum":
            max(prices),

        "average":
            statistics.mean(prices),

        "median":
            statistics.median(prices),
    }


# ============================================================
# ساخت متن گزارش
# ============================================================

def build_report(results):

    stats = calculate_statistics(
        results
    )

    header = (
        "🚗 گزارش بازار خودرو\n\n"
        "📍 اصفهان\n"
        "🚘 تیبا ۲ مدل ۱۴۰۰\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🔎 تعداد کل آگهی‌های منطبق: "
        f"{stats['count']}\n"
        f"💵 دارای قیمت معتبر: "
        f"{stats['priced_count']}\n\n"
    )

    if stats["priced_count"]:

        header += (
            "📊 آمار کل نتایج\n\n"

            f"⬇️ کمترین قیمت: "
            f"{format_price(stats['minimum'])}\n"

            f"⬆️ بیشترین قیمت: "
            f"{format_price(stats['maximum'])}\n"

            f"💰 میانگین قیمت: "
            f"{format_price(stats['average'])}\n"

            f"📊 میانه قیمت: "
            f"{format_price(stats['median'])}\n\n"

            "━━━━━━━━━━━━━━\n\n"
        )

    else:

        header += (
            "❌ قیمت معتبر برای آگهی‌ها پیدا نشد.\n\n"
            "━━━━━━━━━━━━━━\n\n"
        )

    header += (
        "📋 تمام آگهی‌های منطبق:\n\n"
    )

    messages = []

    current_message = header

    for index, item in enumerate(
        results,
        1
    ):

        block = (
            f"{index}. 🚘 "
            f"{item['title']}\n"

            f"💰 قیمت: "
            f"{format_price(item['price'])}\n"

            f"🛣 کارکرد: "
            f"{format_mileage(item['mileage'])}\n"

            f"📍 {item['district']}\n"

            f"⏰ {item['time']}\n"

            f"🔗 {item['url']}\n\n"
        )

        # Telegram limit = 4096
        # کمی حاشیه امن در نظر می‌گیریم.
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

    return messages


# ============================================================
# اجرای اصلی
# ============================================================

def main():

    print()
    print(
        "========================================"
    )
    print(
        "Divar Tiba 2 Model 1400 Monitor"
    )
    print(
        "========================================"
    )

    print(
        "City ID:",
        CITY_ID
    )

    print(
        "Search:",
        SEARCH_QUERY
    )

    print()
    print(
        "Searching Divar..."
    )

    # --------------------------------------------------------
    # جستجو
    # --------------------------------------------------------

    data = search_divar()

    posts = extract_posts(
        data
    )

    print(
        "Raw search results:",
        len(posts)
    )

    # حذف تکراری‌ها
    posts = deduplicate_posts(
        posts
    )

    print(
        "Unique search results:",
        len(posts)
    )

    if MAX_RESULTS is not None:

        posts = posts[
            :MAX_RESULTS
        ]

    # --------------------------------------------------------
    # پردازش
    # --------------------------------------------------------

    all_results = []

    for index, post in enumerate(
        posts,
        1
    ):

        print()
        print(
            f"[{index}/{len(posts)}]"
        )

        print(
            "Title:",
            post["title"]
        )

        # ----------------------------------------------------
        # ابتدا عنوان را بررسی می‌کنیم
        # ----------------------------------------------------

        title_text = normalize(
            post["title"]
        )

        if not is_tiba_2(
            title_text
        ):

            print(
                " -> Not Tiba 2"
            )

            continue

        # اگر عنوان مدل 1400 داشت، نیازی نیست
        # برای تشخیص مدل فقط به JSON متکی باشیم.
        title_has_model = is_model_1400(
            title_text
        )

        # ----------------------------------------------------
        # جزئیات
        # ----------------------------------------------------

        details = get_details(
            post["token"]
        )

        detail_text = normalize(
            json_to_text(details)
        )

        full_text = (
            title_text
            + " "
            + detail_text
        )

        # ----------------------------------------------------
        # مدل 1400
        # ----------------------------------------------------

        if not title_has_model:

            if not is_model_1400(
                full_text
            ):

                print(
                    " -> Not Model 1400"
                )

                continue

        # ----------------------------------------------------
        # قیمت
        # ----------------------------------------------------

        # مهم:
        # ابتدا فقط قیمت POST_ROW را می‌خوانیم.
        price = extract_price_from_search_text(
            post["price_text"]
        )

        # اگر نبود، فقط فیلدهای صریح قیمت JSON بررسی می‌شوند.
        if price is None:

            price = extract_price_from_explicit_fields(
                details
            )

        # قیمت غیرمنطقی را حذف می‌کنیم.
        if price is not None:

            if not (
                MIN_VALID_PRICE
                <= price
                <= MAX_VALID_PRICE
            ):

                print(
                    " -> Invalid price:",
                    price
                )

                price = None

        # ----------------------------------------------------
        # کارکرد
        # ----------------------------------------------------

        mileage = extract_mileage(
            details
        )

        # ----------------------------------------------------
        # زمان
        # ----------------------------------------------------

        time_text = extract_time(
            post,
            details
        )

        # ----------------------------------------------------
        # منطقه
        # ----------------------------------------------------

        district = (
            post.get(
                "district"
            )
            or post.get(
                "location"
            )
            or "نامشخص"
        )

        # ----------------------------------------------------
        # نتیجه
        # ----------------------------------------------------

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
            " -> MATCH"
        )

        print(
            "    Price:",
            format_price(price)
        )

        print(
            "    Mileage:",
            format_mileage(mileage)
        )

        print(
            "    District:",
            district
        )

        time.sleep(0.15)

    # --------------------------------------------------------
    # حذف تکراری‌های نهایی
    # --------------------------------------------------------

    unique_results = []

    seen_tokens = set()

    for item in all_results:

        token = item["token"]

        if token in seen_tokens:
            continue

        seen_tokens.add(
            token
        )

        unique_results.append(
            item
        )

    all_results = unique_results

    # --------------------------------------------------------
    # آمار
    # --------------------------------------------------------

    stats = calculate_statistics(
        all_results
    )

    print()
    print(
        "========================================"
    )

    print(
        "MATCHING POSTS:",
        stats["count"]
    )

    print(
        "PRICED POSTS:",
        stats["priced_count"]
    )

    if stats["priced_count"]:

        print(
            "MIN:",
            format_price(
                stats["minimum"]
            )
        )

        print(
            "MAX:",
            format_price(
                stats["maximum"]
            )
        )

        print(
            "AVERAGE:",
            format_price(
                stats["average"]
            )
        )

        print(
            "MEDIAN:",
            format_price(
                stats["median"]
            )
        )

    print(
        "========================================"
    )

    # --------------------------------------------------------
    # گزارش تلگرام
    # --------------------------------------------------------

    if not all_results:

        message = (
            "🚗 گزارش دیوار\n\n"

            "📍 اصفهان\n"

            "🚘 تیبا ۲ مدل ۱۴۰۰\n\n"

            "❌ هیچ آگهی منطبقی پیدا نشد."
        )

        send_telegram(
            message
        )

    else:

        messages = build_report(
            all_results
        )

        print(
            "Telegram messages:",
            len(messages)
        )

        for message in messages:

            send_telegram(
                message
            )

            time.sleep(1)

    print()
    print(
        "========================================"
    )
    print(
        "REPORT COMPLETED"
    )
    print(
        "========================================"
    )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()
