import time
import random
import json
import pandas as pd
from pytrends.request import TrendReq
from ml_model import predict_category
from datetime import datetime

# Proxy kontrolü için Streamlit durumunu saklayacağız
import streamlit as st

def load_manual_categories():
    try:
        with open("manual_categories.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def load_proxies():
    try:
        with open("proxies.json", "r") as f:
            proxies = json.load(f)
            return [p if p.startswith("http") else f"http://{p}" for p in proxies]
    except:
        return []

def get_random_proxy():
    proxies = load_proxies()
    return random.choice(proxies) if proxies else None

def log_feedback_history(keyword, category):
    try:
        with open("feedback_history.json", "r+", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                data = {}
            if keyword not in data:
                data[keyword] = []
            data[keyword].append({"kategori": category, "tarih": datetime.now().isoformat()})
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
    except:
        pass

def get_trend_score(keyword, geo="TR", timeframe="today 12-m", use_proxy=False):
    proxy = get_random_proxy() if use_proxy else None
    proxy_dict = {"https": proxy, "http": proxy} if proxy else None
    try:
        pytrends = TrendReq(hl='tr-TR', tz=180, timeout=(10, 25), proxies=proxy_dict)
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()
        if not df.empty and keyword in df.columns:
            return round(df[keyword].mean(), 2)
    except Exception as e:
        st.session_state.setdefault("trend_errors", []).append(f"[Trend Error] {keyword}: {e}")
    return 0.0

def analyze_keywords(keywords, geo="TR", timeframe="today 12-m", manual_map={}, use_proxy=False):
    results = []
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
        time.sleep(random.uniform(4, 8))
    return pd.DataFrame(results)
