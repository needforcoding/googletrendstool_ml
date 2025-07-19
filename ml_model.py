import os
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import joblib
import logging

MODEL_FILE = "model.joblib"
VECTORIZER_FILE = "vectorizer.joblib"
FEEDBACK_FILE = "feedback_store.json"
DEFAULT_DATA_FILE = "default_training_data.json"

def load_training_data():
    """Varsayılan ve geri bildirim verilerini birleştirir."""
    # Varsayılan veriyi yükle
    try:
        with open(DEFAULT_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error(f"{DEFAULT_DATA_FILE} bulunamadı veya bozuk. Boş veri setiyle başlanıyor.")
        data = {}

    # Geri bildirim verisini yükle ve birleştir
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            feedback_data = json.load(f)
        data.update(feedback_data)
        logging.info(f"{len(feedback_data)} geri bildirim verisi yüklendi.")
    except (FileNotFoundError, json.JSONDecodeError):
        logging.info("Geri bildirim dosyası bulunamadı, sadece varsayılan veriyle model eğitilecek.")
        pass # Geri bildirim dosyası olmayabilir, bu bir hata değil.

    return data

def train_model(data):
    """Verilen veriyle modeli eğitir ve kaydeder."""
    if not data or len(set(data.values())) < 2:
        logging.warning("Eğitim için yetersiz veri. En az 2 farklı kategori olmalı. Model eğitilmedi.")
        return None, None

    X = list(data.keys())
    y = list(data.values())

    vectorizer = TfidfVectorizer()
    X_vec = vectorizer.fit_transform(X)

    model = MultinomialNB()
    model.fit(X_vec, y)

    joblib.dump(model, MODEL_FILE)
    joblib.dump(vectorizer, VECTORIZER_FILE)

    logging.info(f"Model {len(X)} örnekle eğitildi ve kaydedildi.")
    return model, vectorizer

def load_model():
    """Kaydedilmiş modeli ve vectorizer'ı yükler veya yeniden eğitir."""
    if os.path.exists(MODEL_FILE) and os.path.exists(VECTORIZER_FILE):
        model = joblib.load(MODEL_FILE)
        vectorizer = joblib.load(VECTORIZER_FILE)
        logging.info("Kaydedilmiş model ve vectorizer yüklendi.")
    else:
        logging.info("Kaydedilmiş model bulunamadı. Veri setinden yeniden eğitiliyor.")
        training_data = load_training_data()
        model, vectorizer = train_model(training_data)
    return model, vectorizer

# Modeli global kapsamda yükle
model, vectorizer = load_model()

def predict_category(keyword):
    """Bir anahtar kelimenin kategorisini tahmin eder."""
    if not model or not vectorizer:
        return "N/A" # Model eğitilmemişse tahmin yapma
    try:
        X_test = vectorizer.transform([keyword])
        return model.predict(X_test)[0]
    except Exception as e:
        logging.error(f"Kategori tahmini sırasında hata: {e}")
        return "Hata"

def update_model_with_feedback(keywords, categories):
    """Geri bildirimleri bir dosyada saklar. Model yeniden eğitilmez."""
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            feedback_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        feedback_data = {}

    new_data = dict(zip(keywords, categories))
    feedback_data.update(new_data)

    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(feedback_data, f, ensure_ascii=False, indent=4)
    logging.info(f"{len(new_data)} yeni geri bildirim `feedback_store.json` dosyasına kaydedildi.")

def reset_model():
    """Geri bildirimleri siler ve modeli varsayılan veriyle yeniden eğitir."""
    global model, vectorizer

    # Geri bildirim dosyasını sil
    if os.path.exists(FEEDBACK_FILE):
        os.remove(FEEDBACK_FILE)
        logging.info(f"{FEEDBACK_FILE} silindi.")

    # Modeli sadece varsayılan veriyle yeniden eğit
    default_data = load_training_data() # Bu artık sadece default datayı okuyacak
    model, vectorizer = train_model(default_data)
    logging.info("Model sıfırlandı ve varsayılan veriyle yeniden eğitildi.")
