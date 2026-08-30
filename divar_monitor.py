import requests
import json

url = "https://api.divar.ir/v8/postlist/w/search"

payload = {
    "city_ids": ["3"],
    "categories": ["light"]
}

headers = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

response = requests.post(
    url,
    json=payload,
    headers=headers,
    timeout=30
)

print("STATUS:", response.status_code)
print("CONTENT TYPE:", response.headers.get("content-type"))

print(json.dumps(
    response.json(),
    ensure_ascii=False,
    indent=2
)[:30000])
