import time
import random
import json
import pandas as pd
import requests
from pytrends.request import TrendReq
from ml_model import predict_category
from datetime import datetime
import logging
import streamlit as st

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def load_manual_categories():
    try:
        with open("manual_categories.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning("manual_categories.json bulunamadı, boş liste kullanılıyor.")
        return {}
    except json.JSONDecodeError:
        logging.error("manual_categories.json dosyası bozuk, boş liste kullanılıyor.")
        return {}

def load_proxies():
    try:
        with open("proxies.json", "r", encoding="utf-8") as f:
            proxies = json.load(f)
            return [p if p.startswith("http") else f"http://{p}" for p in proxies]
    except FileNotFoundError:
        logging.warning("proxies.json bulunamadı, proxy'ler kullanılmayacak.")
        return []
    except json.JSONDecodeError:
        logging.error("proxies.json dosyası bozuk, proxy'ler kullanılmayacak.")
        return []

def check_proxy(proxy):
    """Verilen proxy'nin çalışıp çalışmadığını test eder."""
    proxy_dict = {"http": proxy, "https": proxy}
    try:
        response = requests.get("https://www.google.com", proxies=proxy_dict, timeout=5)
        if response.status_code == 200:
            logging.info(f"Proxy {proxy} çalışıyor.")
            return True
    except requests.exceptions.RequestException as e:
        logging.warning(f"Proxy {proxy} çalışmıyor: {e}")
    return False

def get_random_proxy(max_tries=5):
    """Çalışan bir proxy bulana kadar rastgele proxy'ler dener."""
    proxies = load_proxies()
    if not proxies:
        return None

    tried_proxies = set()
    for _ in range(max_tries):
        if len(tried_proxies) == len(proxies):
            logging.warning("Tüm proxy'ler denendi, çalışan bulunamadı.")
            return None # Denenecek yeni proxy kalmadı.

        proxy = random.choice(proxies)
        if proxy in tried_proxies:
            continue

        tried_proxies.add(proxy)
        if check_proxy(proxy):
            return proxy

    logging.error(f"{max_tries} denemeden sonra çalışan proxy bulunamadı.")
    return None



def get_trend_score(keyword, geo="TR", timeframe="today 12-m", use_proxy=False):
    proxy = None
    if use_proxy:
        proxy = get_random_proxy()
        if not proxy:
            error_msg = "Çalışan bir proxy bulunamadı. Lütfen proxy listenizi kontrol edin veya proxy olmadan devam edin."
            logging.error(error_msg)
            if error_msg not in st.session_state.get("trend_errors", []):
                 st.session_state.setdefault("trend_errors", []).append(error_msg)
            return 0.0

    proxy_dict = {"https": proxy, "http": proxy} if proxy else None

    log_message = f"Trend isteği: Kelime='{keyword}', Ülke='{geo}', Proxy={proxy is not None}"
    logging.info(log_message)

    try:
        pytrends = TrendReq(hl='tr-TR', tz=180, timeout=(10, 25), proxies=proxy_dict, retries=3, backoff_factor=0.5)
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()

        if df.empty:
            logging.warning(f"'{keyword}' için Pytrends'ten boş DataFrame döndü.")
            st.session_state.setdefault("trend_errors", []).append(f"'{keyword}' için Google Trends verisi bulunamadı.")
            return 0.0

        if keyword not in df.columns:
            logging.warning(f"'{keyword}' sütunu DataFrame'de bulunamadı. Sütunlar: {df.columns.tolist()}")
            st.session_state.setdefault("trend_errors", []).append(f"'{keyword}' için gelen veride ilgili sütun bulunamadı.")
            return 0.0

        score = round(df[keyword].mean(), 2)
        logging.info(f"'{keyword}' için ortalama trend skoru: {score}")
        return score

    except TypeError as e:
        if "object of type 'NoneType' has no len()" in str(e):
            logging.warning(f"Pytrends NoneType hatası aldı ('{keyword}'). Manuel yönteme geçiliyor.")
            st.session_state.setdefault("trend_errors", []).append(f"Pytrends '{keyword}' için başarısız, manuel yöntem denendi.")

            # Yedek manuel yöntemi dene
            manual_score = get_trend_score_manual(keyword, geo=geo, timeframe=timeframe, proxy_dict=proxy_dict)
            if manual_score is not None:
                return manual_score

            # Manuel yöntem de başarısız olursa hata ver.
            error_msg = f"Pytrends ve Manuel yöntemler '{keyword}' için veri alamadı. Google API'de genel bir sorun olabilir."
            logging.error(error_msg)
            st.session_state.setdefault("trend_errors", []).append(error_msg)

        else:
            error_msg = f"Pytrends içinde beklenmedik bir tip hatası ('{keyword}'): {e}"
            logging.error(error_msg)
            st.session_state.setdefault("trend_errors", []).append(error_msg)
        return 0.0
    except Exception as e:
        error_msg = f"Pytrends genel hatası ('{keyword}'): {e}"
        logging.error(error_msg)
        st.session_state.setdefault("trend_errors", []).append(error_msg)
        return 0.0

def get_trend_score_manual(keyword, geo="TR", timeframe="today 12-m", proxy_dict=None):
    """Requests kullanarak Google Trends verisini manuel olarak çeker."""

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    }

    # Adım 1: Token almak için ilk isteği yap.
    explore_url = "https://trends.google.com/trends/api/explore"
    params = {
        "hl": "tr-TR",
        "tz": "180",
        "req": json.dumps({
            "comparisonItem": [{"keyword": keyword, "geo": geo, "time": timeframe}],
            "category": 0,
            "property": ""
        })
    }

    try:
        # Google'dan cookie almak için bir session başlat
        session = requests.Session()
        session.get("https://trends.google.com", headers=headers, proxies=proxy_dict, timeout=10)

        explore_response = session.get(explore_url, params=params, headers=headers, proxies=proxy_dict, timeout=10)

        if explore_response.status_code != 200:
            logging.error(f"Manuel Trend: Explore isteği başarısız oldu. Status: {explore_response.status_code}")
            return None

        # Yanıttan widget token'ını al
        # Google'ın yanıtı genellikle `)]}'` ile başlar, bunu temizlememiz gerekir.
        widget_data_str = explore_response.text[4:]
        widgets = json.loads(widget_data_str)["widgets"]
        token = widgets[0].get("token")

        if not token:
            logging.error("Manuel Trend: Yanıtta widget token'ı bulunamadı.")
            return None

        # Adım 2: Token ile asıl veriyi çek.
        widget_url = "https://trends.google.com/trends/api/widgetdata/multiline"
        widget_params = {
            "hl": "tr-TR",
            "tz": "180",
            "req": json.dumps({"time": timeframe, "resolution": "WEEK", "locale": "tr", "comparisonItem": [{"geo": {"country": geo}, "complexKeywordsRestriction": {"keyword": [{"type": "BROAD", "value": keyword}]}}], "requestOptions": {"property": "", "backend": "IZG", "category": 0}}),
            "token": token
        }

        data_response = session.get(widget_url, params=widget_params, headers=headers, proxies=proxy_dict, timeout=10)

        if data_response.status_code != 200:
            logging.error(f"Manuel Trend: Veri isteği başarısız oldu. Status: {data_response.status_code}")
            return None

        # Veriyi işle ve ortalamayı hesapla
        data_str = data_response.text[5:] # Bu da `)]}'\n` ile başlayabilir
        data = json.loads(data_str)

        time_series = data.get("default", {}).get("timelineData", [])
        if not time_series:
            logging.warning(f"Manuel Trend: '{keyword}' için zaman serisi verisi bulunamadı.")
            return 0.0

        avg_score = sum(point.get("value", [0])[0] for point in time_series) / len(time_series)
        logging.info(f"Manuel Trend: '{keyword}' için ortalama skor: {round(avg_score, 2)}")
        return round(avg_score, 2)

    except requests.exceptions.RequestException as e:
        logging.error(f"Manuel Trend: İstek sırasında hata: {e}")
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logging.error(f"Manuel Trend: Yanıt işlenirken hata: {e}")
        return None


def analyze_keywords(keywords, geo="TR", timeframe="today 12-m", manual_map={}, use_proxy=False):
    results = []
    st.session_state["trend_errors"] = [] # Her analiz öncesi hataları sıfırla

    for kw in keywords:
        score = get_trend_score(kw, geo=geo, timeframe=timeframe, use_proxy=use_proxy)
        category = manual_map.get(kw) or predict_category(kw)
        results.append({
            "Kelime": kw,
            "Kategori": category,
            "Ülke": geo,
            "Zaman Aralığı": timeframe,
            "Trend Skoru": score
        })
        time.sleep(random.uniform(2, 5)) # Rate limit için bekleme süresi biraz kısıldı
    return pd.DataFrame(results)
