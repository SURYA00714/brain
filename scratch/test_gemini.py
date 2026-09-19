import os
import requests

def test_gemini():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("No key found.")
        return
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            models = [m.get("name") for m in data.get("models", [])]
            print(f"Auth valid! Found {len(models)} models.")
            for m in models:
                if "gemini" in m:
                    print("-", m)
        else:
            print(f"Failed: {res.status_code} - {res.text}")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    from models.gateway import _load_dotenv_if_present
    _load_dotenv_if_present()
    test_gemini()
