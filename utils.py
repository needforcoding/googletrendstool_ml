
import time
import random
import json
import pandas as pd
import os
from pytrends.request import TrendReq
from ml_model import predict_category
from datetime import datetime
import logging
import streamlit as st

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GoogleTrendsApp")

def load_manual_categories():
    try:
        with open("manual_categories.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Manuel kategoriler yüklenemedi: {e}")
        return {}

def load_proxies():
    try:
        with open("proxies.json", "r", encoding="utf-8") as f:
            proxies = json.load(f)
            logger.info(f"{len(proxies)} adet proxy yüklendi")
            return [p if p.startswith("http") else f"http://{p}" for p in proxies]
    except Exception as e:
        logger.error(f"Proxy listesi yüklenemedi: {e}")
        return []

def get_random_proxy():
    proxies = load_proxies()
    if not proxies:
        logger.warning("Proxy listesi boş!")
        return None
    proxy = random.choice(proxies)
    logger.info(f"Seçilen proxy: {proxy}")
    return proxy

def log_feedback_history(keyword, category):
    try:
        # Dosya yoksa oluştur
        if not os.path.exists("feedback_history.json"):
            with open("feedback_history.json", "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        
        with open("feedback_history.json", "r+", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                logger.warning("feedback_history.json dosyası bozuk, yeniden oluşturuluyor")
                data = {}
                
            if keyword not in data:
                data[keyword] = []
            data[keyword].append({
                "kategori": category, 
                "tarih": datetime.now().isoformat()
            })
            
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
            logger.info(f"Geri bildirim kaydedildi: {keyword} -> {category}")
    except Exception as e:
        logger.error(f"Geri bildirim kaydedilirken hata: {e}")

def get_trend_score(keyword, geo="TR", timeframe="today 12-m", use_proxy=False, max_retries=3):
    # Google Trends API ile anahtar kelimelerin trend skorunu alır
    for attempt in range(max_retries):
        proxy = get_random_proxy() if use_proxy else None
        proxy_dict = {"https": proxy, "http": proxy} if proxy else None
        
        try:
            logger.info(f"[{attempt+1}/{max_retries}] '{keyword}' için trend skoru alınıyor..." + 
                      (f" (Proxy: {proxy})" if proxy else ""))
            
            pytrends = TrendReq(hl="tr-TR", tz=180, timeout=(10, 25), proxies=proxy_dict)
            pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
            df = pytrends.interest_over_time()
            
            if not df.empty and keyword in df.columns:
                score = round(df[keyword].mean(), 2)
                logger.info(f"'{keyword}' için trend skoru: {score}")
                return score
            else:
                logger.warning(f"'{keyword}' için boş sonuç döndü. Tekrar deneniyor...")
        except Exception as e:
            error_msg = f"[{attempt+1}/{max_retries}] '{keyword}': {str(e)}"
            logger.error(error_msg)
            st.session_state.setdefault("trend_errors", []).append(error_msg)
            
        # Başarısız olursa biraz bekle ve tekrar dene
        if attempt < max_retries - 1:
            wait_time = 5 + random.uniform(2, 5)
            logger.info(f"Yeniden denemeden önce {wait_time:.1f} saniye bekleniyor...")
            time.sleep(wait_time)
    
    logger.error(f"'{keyword}' için trend skoru alınamadı, tüm denemeler başarısız.")
    return 0.0

def analyze_keywords(keywords, geo="TR", timeframe="today 12-m", manual_map={}, use_proxy=False):
    # Anahtar kelimeleri analiz eder ve sonuçları döndürür
    logger.info(f"Analiz başlıyor: {len(keywords)} anahtar kelime, Ülke: {geo}, Zaman: {timeframe}")
    results = []
    
    for i, kw in enumerate(keywords):
        logger.info(f"[{i+1}/{len(keywords)}] '{kw}' analiz ediliyor...")
        score = get_trend_score(kw, geo=geo, timeframe=timeframe, use_proxy=use_proxy)
        category = manual_map.get(kw) or predict_category(kw)
        
        results.append({
            "Kelime": kw,
            "Kategori": category,
            "Ülke": geo,
            "Zaman Aralığı": timeframe,
            "Trend Skoru": score
        })
        
        # Rate limiting - çok hızlı istek göndermemek için
        if i < len(keywords) - 1:
            wait_time = random.uniform(4, 8)
            logger.info(f"Sonraki kelime için {wait_time:.1f} saniye bekleniyor...")
            time.sleep(wait_time)
    
    logger.info(f"Analiz tamamlandı: {len(results)} sonuç")
    return pd.DataFrame(results)

