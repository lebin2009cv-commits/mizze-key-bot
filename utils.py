import requests
from config import LINK4M_API_TOKEN

def create_link4m(destination_url: str) -> str | None:
    try:
        api_url = "https://link4m.co/api-shorten/v2"
        params = {"api": LINK4M_API_TOKEN, "url": destination_url}
        res = requests.get(api_url, params=params, timeout=15)
        data = res.json()
        if data.get("status") == "success":
            return data.get("shortenedUrl")
        print("Link4m lỗi:", data)
        return None
    except Exception as e:
        print("Lỗi tạo link:", e)
        return None