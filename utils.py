import time
import random
import json
import pandas as pd
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

def get_random_proxy():
    proxies = load_proxies()
    return random.choice(proxies) if proxies else None



def get_trend_score(keyword, geo="TR", timeframe="today 12-m", use_proxy=False):
    proxy = get_random_proxy() if use_proxy else None
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

    except Exception as e:
        error_msg = f"Pytrends hatası ('{keyword}'): {e}"
        logging.error(error_msg)
        st.session_state.setdefault("trend_errors", []).append(error_msg)
        return 0.0

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
