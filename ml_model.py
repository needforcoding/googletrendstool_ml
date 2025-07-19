import os
import json
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import logging

logger = logging.getLogger("GoogleTrendsApp")

MODEL_FILE = "model.joblib"
VECTORIZER_FILE = "vectorizer.joblib"
FEEDBACK_FILE = "feedback_history.json"

# Varsayılan eğitim verisi
default_data = {
    "moda": "kozmetik", "el kremi": "kozmetik", "şampuan": "kozmetik",
    "cilt bakımı": "kozmetik", "ayak bakımı": "kozmetik",
    "endüstriyel robot": "makine", "cnc tezgah": "makine", "torna makinesi": "makine",
    "hidrolik pompa": "makine", "redüktör": "makine",
    "dijital pazarlama": "teknoloji", "veri analizi": "teknoloji",
    "yapay zeka": "teknoloji", "e-ticaret": "teknoloji"
}

def train_model(data):
    """Verilen veriye göre modeli eğitir ve dosyaları kaydeder."""
    X = list(data.keys())
    y = list(data.values())

    vectorizer = TfidfVectorizer()
    X_vec = vectorizer.fit_transform(X)

    model = MultinomialNB()
    model.fit(X_vec, y)

    try:
        joblib.dump(model, MODEL_FILE)
        joblib.dump(vectorizer, VECTORIZER_FILE)
        logger.info("Model ve vectorizer dosyaları başarıyla kaydedildi.")
    except Exception as e:
        logger.error(f"Model kaydedilirken hata oluştu: {e}")

    return model, vectorizer

def load_model():
    """Mevcut modeli ve vectorizer'ı yükler, yoksa yeniden eğitir."""
    if os.path.exists(MODEL_FILE) and os.path.exists(VECTORIZER_FILE):
        try:
            model = joblib.load(MODEL_FILE)
            vectorizer = joblib.load(VECTORIZER_FILE)
            logger.info("Mevcut model ve vectorizer yüklendi.")
            return model, vectorizer
        except Exception as e:
            logger.error(f"Model yüklenirken hata oluştu, model yeniden eğitilecek: {e}")
            # Hata durumunda yeniden eğit
            return train_model(get_combined_data())
    else:
        logger.warning("Model dosyaları bulunamadı, varsayılan verilerle yeni model eğitiliyor.")
        return train_model(get_combined_data())

def get_combined_data():
    """Varsayılan verilerle geri bildirim verilerini birleştirir."""
    feedback_data = {}
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
                feedback_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"{FEEDBACK_FILE} okunurken hata, boş bir sözlükle devam ediliyor: {e}")

    combined_data = default_data.copy()
    combined_data.update(feedback_data)
    return combined_data

def predict_category(keyword):
    """Verilen anahtar kelime için kategori tahmini yapar."""
    X_test = vectorizer.transform([keyword])
    return model.predict(X_test)[0]

def update_model_with_feedback(keywords, categories):
    """Geri bildirimlere göre modeli günceller."""
    global model, vectorizer

    feedback_data = {}
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
                feedback_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"{FEEDBACK_FILE} okunurken hata, boş bir sözlükle devam ediliyor: {e}")

    # Yeni geri bildirimleri ekle/güncelle
    for kw, cat in zip(keywords, categories):
        feedback_data[kw] = cat

    try:
        with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(feedback_data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"Geri bildirim dosyası güncellenirken hata: {e}")

    logger.info(f"{len(keywords)} yeni geri bildirim ile model yeniden eğitiliyor.")
    model, vectorizer = train_model(get_combined_data())

def reset_model():
    """Modeli varsayılan duruma sıfırlar ve geri bildirim geçmişini temizler."""
    global model, vectorizer
    logger.info("Model sıfırlanıyor ve varsayılan verilerle yeniden eğitiliyor.")
    model, vectorizer = train_model(default_data)

    try:
        if os.path.exists(FEEDBACK_FILE):
            os.remove(FEEDBACK_FILE)
            logger.info(f"{FEEDBACK_FILE} başarıyla silindi.")
    except OSError as e:
        logger.error(f"{FEEDBACK_FILE} silinirken bir hata oluştu: {e}")

# Uygulama başlangıcında modeli yükle
model, vectorizer = load_model()
