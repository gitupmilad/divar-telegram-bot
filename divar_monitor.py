import requests
import json

URL = "https://api.divar.ir/v8/postlist/w/search"

payload = {
    "city_ids": ["1"],
    "search_data": {
        "query": "تیبا 2"
    }
}

headers = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

response = requests.post(
    URL,
    json=payload,
    headers=headers,
    timeout=30
)

print("STATUS:", response.status_code)

data = response.json()

for widget in data.get("list_widgets", []):

    if widget.get("widget_type") != "POST_ROW":
        continue

    item = widget.get("data", {})
    action = item.get("action", {})
    payload_data = action.get("payload", {})

    title = item.get("title", "")
    price = item.get("middle_description_text", "")
    token = payload_data.get("token", "")

    print("=" * 60)
    print("TITLE:", title)
    print("PRICE:", price)
    print("TOKEN:", token)
