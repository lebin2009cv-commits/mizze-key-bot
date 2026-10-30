import requests
import urllib.parse
from config import LINK4M_API_KEY, YEUMONEY_API_KEY, SHRINKME_API_KEY

def create_link4m(destination_url: str) -> str | None:
    try:
        api_url = "https://link4m.co/api-shorten/v2"
        # Mã hóa URL để tránh lỗi ký tự đặc biệt
        encoded_url = urllib.parse.quote(destination_url, safe='')
        params = {"api": LINK4M_API_KEY, "url": encoded_url}
        res = requests.get(api_url, params=params, timeout=15)
        data = res.json()
        if data.get("status") == "success":
            return data.get("shortenedUrl")
        print("Link4m lỗi:", data)
        return None
    except Exception as e:
        print("Lỗi tạo link Link4m:", e)
        return None

def create_yeumoney(destination_url: str) -> str | None:
    try:
        api_url = "https://yeumoney.com/QL_api.php"
        encoded_url = urllib.parse.quote(destination_url, safe='')
        params = {"token": YEUMONEY_API_KEY, "url": encoded_url, "format": "json"}
        res = requests.get(api_url, params=params, timeout=15)
        data = res.json()
        if data.get("status") == "success":
            return data.get("shortenedUrl")
        print("YeuMoney lỗi:", data)
        return None
    except Exception as e:
        print("Lỗi tạo link YeuMoney:", e)
        return None

def create_shrinkme(destination_url: str) -> str | None:
    try:
        api_url = "https://shrinkme.io/api"
        encoded_url = urllib.parse.quote(destination_url, safe='')
        params = {"api": SHRINKME_API_KEY, "url": encoded_url}
        res = requests.get(api_url, params=params, timeout=15)
        data = res.json()
        if data.get("status") == "success":
            return data.get("shortenedUrl")
        print("ShrinkMe lỗi:", data)
        return None
    except Exception as e:
        print("Lỗi tạo link ShrinkMe:", e)
        return None