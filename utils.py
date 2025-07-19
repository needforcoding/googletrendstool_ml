
import time
import random
import json
import pandas as pd
import os
import requests
from pytrends.request import TrendReq
from ml_model import predict_category
from datetime import datetime
import logging
import streamlit as st

logger = logging.getLogger("GoogleTrendsApp")

PROXIES_FILE = "proxies.json"
MANUAL_CATEGORIES_FILE = "manual_categories.json"
FEEDBACK_HISTORY_FILE = "feedback_history.json"

def read_json_file(filepath, default_value={}):
    """JSON dosyalarını güvenli bir şekilde okur."""
    if not os.path.exists(filepath):
        logger.warning(f"Dosya bulunamadı: {filepath}. Varsayılan değer kullanılacak.")
        return default_value
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"{filepath} okunurken hata: {e}. Varsayılan değer kullanılacak.")
        return default_value

def load_manual_categories():
    """Manuel kategori eşleştirmelerini dosyadan yükler."""
    return read_json_file(MANUAL_CATEGORIES_FILE)

def load_proxies():
    """Proxy listesini dosyadan yükler."""
    proxies_list = read_json_file(PROXIES_FILE, default_value=[])
    if not isinstance(proxies_list, list):
        logger.error(f"{PROXIES_FILE} içeriği bir liste olmalıdır.")
        return []
    logger.info(f"{len(proxies_list)} adet proxy yüklendi.")
    return [p if p.startswith("http") else f"http://{p}" for p in proxies_list]

def get_random_proxy():
    """Mevcut proxy listesinden rastgele bir proxy seçer."""
    proxies = load_proxies()
    if not proxies:
        logger.warning("Proxy listesi boş veya yüklenemedi!")
        return None
    proxy = random.choice(proxies)
    logger.info(f"Seçilen proxy: {proxy}")
    return proxy

def log_feedback_history(keyword, category):
    """Kullanıcı geri bildirimlerini bir geçmiş dosyasına kaydeder."""
    try:
        history = read_json_file(FEEDBACK_HISTORY_FILE)
        
        if keyword not in history:
            history[keyword] = []

        history[keyword].append({
            "kategori": category,
            "tarih": datetime.now().isoformat()
        })

        with open(FEEDBACK_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

        logger.info(f"Geri bildirim geçmişi güncellendi: {keyword} -> {category}")
    except IOError as e:
        logger.error(f"Geri bildirim geçmişi dosyasına yazılırken hata: {e}")

def get_trend_score(keyword, geo="TR", timeframe="today 12-m", use_proxy=False, max_retries=3, available_proxies=None):
    """
    Google Trends'den bir anahtar kelimenin ortalama trend skorunu alır.
    Oturum yönetimi ve başarısız proxy'leri atlama mekanizması içerir.
    """
    if use_proxy and available_proxies is None:
        available_proxies = load_proxies()

    # Istekler için bir oturum oluştur
    session = requests.Session()
    # Standart bir tarayıcı gibi görünmek için User-Agent ekle
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    })

    for attempt in range(max_retries):
        proxy = None
        if use_proxy and available_proxies:
            proxy = random.choice(available_proxies)
        
        # Oturumun proxy ayarlarını güncelle
        session.proxies = {"https": proxy, "http": proxy} if proxy else {}

        try:
            logger.info(
                f"[{attempt + 1}/{max_retries}] '{keyword}' için trend verisi alınıyor "
                f"(Geo: {geo}, Proxy: {proxy or 'Yok'})"
            )

            # Pytrends'e oluşturduğumuz oturumu ver
            pytrends = TrendReq(hl="tr-TR", tz=180, timeout=(10, 25), requests_args={'session': session})
            pytrends.build_payload([keyword], timeframe=timeframe, geo=geo)
            df = pytrends.interest_over_time()

            if df is not None and not df.empty and keyword in df.columns:
                score = round(df[keyword].mean(), 2)
                logger.info(f"✅ '{keyword}' için ortalama trend skoru bulundu: {score}")
                return score, available_proxies
            else:
                logger.warning(f"📉 '{keyword}' için Google Trends'den veri alınamadı veya skor 0.")
                return 0.0, available_proxies

        except Exception as e:
            error_msg = f"❌ '{keyword}' işlenirken hata (Proxy: {proxy}): {type(e).__name__} - {e}"
            logger.error(error_msg)
            
            if "trend_errors" in st.session_state:
                st.session_state.trend_errors.append(error_msg)

            if use_proxy and proxy and available_proxies:
                available_proxies.remove(proxy)
                logger.info(f"Proxy {proxy} başarısız olduğu için listeden kaldırıldı.")

            if attempt < max_retries - 1:
                wait_time = random.uniform(5, 10) # Bekleme süresini biraz artır
                logger.info(f"Yeniden denemeden önce {wait_time:.1f} saniye bekleniyor...")
                time.sleep(wait_time)

    logger.error(f"🚨 '{keyword}' için trend skoru tüm denemeler sonunda alınamadı.")
    return 0.0, available_proxies

def analyze_keywords(keywords, geo="TR", timeframe="today 12-m", manual_map={}, use_proxy=False):
    """Verilen anahtar kelime listesini analiz eder, trend skorlarını ve kategorilerini bulur."""
    logger.info(f"Analiz başlıyor: {len(keywords)} anahtar kelime, Ülke: {geo}, Zaman: {timeframe}, Proxy: {use_proxy}")
    results = []
    
    # Proxy kullanılacaksa, proxy listesini bir kere yükle
    available_proxies = load_proxies() if use_proxy else None

    with st.spinner(f"{len(keywords)} anahtar kelime analiz ediliyor..."):
        for i, kw in enumerate(keywords):
            st.info(f"[{i+1}/{len(keywords)}] '{kw}' analiz ediliyor...")

            score, updated_proxies = get_trend_score(
                kw,
                geo=geo,
                timeframe=timeframe,
                use_proxy=use_proxy,
                available_proxies=available_proxies
            )

            # Proxy listesini güncelle
            if use_proxy:
                available_proxies = updated_proxies

            category = manual_map.get(kw, predict_category(kw))

            results.append({
                "Kelime": kw,
                "Kategori": category,
                "Ülke": geo,
                "Zaman Aralığı": timeframe,
                "Trend Skoru": score
            })

            if i < len(keywords) - 1:
                wait_time = random.uniform(2, 5)
                logger.info(f"Rate limit'e takılmamak için {wait_time:.1f} saniye bekleniyor.")
                time.sleep(wait_time)

    logger.info("Analiz tamamlandı.")
    return pd.DataFrame(results)

