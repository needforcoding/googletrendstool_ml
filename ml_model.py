import pandas as pd
import joblib
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

MODEL_FILE = "model.pkl"
VECTORIZER_FILE = "vectorizer.pkl"

initial_data = [
    ("kolajen serum", "Cilt Bakımı"),
    ("keratin şampuan", "Saç Bakımı"),
    ("makyaj temizleme suyu", "Makyaj"),
    ("diş macunu", "Ağız ve Diş Sağlığı"),
    ("vitamin ampul", "Medikal / Sağlık"),
    ("kompresör", "Mekanik / Mühendislik"),
    ("sensor modülü", "Elektronik / Otomasyon"),
]

def train_and_save_model():
    df = pd.DataFrame(initial_data, columns=["text", "label"])
    vec = TfidfVectorizer()
    X = vec.fit_transform(df["text"])
    y = df["label"]
    model = MultinomialNB()
    model.fit(X, y)
    joblib.dump(model, MODEL_FILE)
    joblib.dump(vec, VECTORIZER_FILE)

def predict_category(text):
    if not os.path.exists(MODEL_FILE):
        train_and_save_model()
    model = joblib.load(MODEL_FILE)
    vec = joblib.load(VECTORIZER_FILE)
    X = vec.transform([text])
    return model.predict(X)[0]

def update_model_with_feedback(texts, labels):
    model = joblib.load(MODEL_FILE)
    vec = joblib.load(VECTORIZER_FILE)
    X = vec.transform(texts)
    model.partial_fit(X, labels, classes=model.classes_)
    joblib.dump(model, MODEL_FILE)

def reset_model():
    if os.path.exists(MODEL_FILE):
        os.remove(MODEL_FILE)
    if os.path.exists(VECTORIZER_FILE):
        os.remove(VECTORIZER_FILE)
    train_and_save_model()
