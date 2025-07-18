import time
import random
from pytrends.request import TrendReq
import pandas as pd
import json
from ml_model import predict_category

def get_trend_score(keyword, geo="TR", timeframe="today 12-m"):
    try:
        pytrends = TrendReq(hl='tr-TR', tz=180, timeout=(10, 25))
        pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()
        if not df.empty and keyword in df.columns:
            return round(df[keyword].mean(), 2)
        else:
            return 0.0
    except:
        return 0.0

def load_manual_categories():
    try:
        with open("manual_categories.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_feedback(keyword, category):
    try:
        with open("feedback_store.json", "r+", encoding="utf-8") as f:
            data = json.load(f)
            data[keyword] = category
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
    except:
        pass

def analyze_keywords(keywords, geo="TR", timeframe="today 12-m", manual_map={}):
    results = []
    for kw in keywords:
        score = get_trend_score(kw, geo=geo, timeframe=timeframe)
        if kw in manual_map:
            category = manual_map[kw]
        else:
            category = predict_category(kw)
        results.append({
            "Kelime": kw,
            "Kategori": category,
            "Ülke": geo,
            "Zaman Aralığı": timeframe,
            "Trend Skoru": score
        })
        time.sleep(random.uniform(3, 6))
    return pd.DataFrame(results)
