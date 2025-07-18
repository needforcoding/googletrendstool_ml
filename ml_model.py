import os
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import joblib

MODEL_FILE = "model.joblib"
VECTORIZER_FILE = "vectorizer.joblib"

# Eğitim verisi yedeği
default_data = {
    "moda": "kozmetik",
    "el kremi": "kozmetik",
    "şampuan": "kozmetik",
    "cilt bakımı": "kozmetik",
    "ayak bakımı": "kozmetik",
    "endüstriyel robot": "makine",
    "cnc tezgah": "makine",
    "torna makinesi": "makine",
    "hidrolik pompa": "makine",
    "redüktör": "makine",
    "dijital pazarlama": "teknoloji",
    "veri analizi": "teknoloji",
    "yapay zeka": "teknoloji",
    "e-ticaret": "teknoloji"
}

def load_model():
    if os.path.exists(MODEL_FILE) and os.path.exists(VECTORIZER_FILE):
        model = joblib.load(MODEL_FILE)
        vectorizer = joblib.load(VECTORIZER_FILE)
    else:
        model, vectorizer = train_model(default_data)
    return model, vectorizer

def train_model(data):
    X = list(data.keys())
    y = list(data.values())
    vectorizer = TfidfVectorizer()
    X_vec = vectorizer.fit_transform(X)
    model = MultinomialNB()
    model.fit(X_vec, y)
    joblib.dump(model, MODEL_FILE)
    joblib.dump(vectorizer, VECTORIZER_FILE)
    return model, vectorizer

model, vectorizer = load_model()

def predict_category(keyword):
    X_test = vectorizer.transform([keyword])
    return model.predict(X_test)[0]

def update_model_with_feedback(keywords, categories):
    global model, vectorizer
    new_data = dict(zip(keywords, categories))
    combined_data = default_data.copy()
    combined_data.update(new_data)
    model, vectorizer = train_model(combined_data)

def reset_model():
    global model, vectorizer
    model, vectorizer = train_model(default_data)
    if os.path.exists("feedback_history.json"):
        os.remove("feedback_history.json")
