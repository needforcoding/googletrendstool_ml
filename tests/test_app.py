import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Test edilecek modülleri import etmeden önce environment variable ayarla
os.environ['STREAMLIT_SERVER_MODE'] = 'test'

from ml_model import train_model, load_model, predict_category, reset_model, default_data
from utils import analyze_keywords, load_proxies, read_json_file
from app import init_session_state

# --- Test Kurulumu ---

@pytest.fixture(scope="module")
def setup_test_environment():
    """Testler için gerekli dosyaları ve başlangıç durumunu oluşturur."""
    # Test için sahte dosyalar oluştur
    with open("test_proxies.json", "w") as f:
        f.write('["1.1.1.1:8080", "2.2.2.2:8080"]')
    with open("test_manual_categories.json", "w") as f:
        f.write('{"test kelime": "test kategori"}')

    # Modeli eğit
    train_model(default_data)

    yield

    # Test sonrası temizlik
    files_to_remove = [
        "test_proxies.json", "test_manual_categories.json",
        "model.joblib", "vectorizer.joblib", "feedback_history.json", "app.log"
    ]
    for f in files_to_remove:
        if os.path.exists(f):
            os.remove(f)

# --- ml_model.py Testleri ---

def test_train_and_load_model(setup_test_environment):
    """Modelin eğitilip başarıyla yüklendiğini test eder."""
    assert os.path.exists("model.joblib")
    assert os.path.exists("vectorizer.joblib")
    model, vectorizer = load_model()
    assert model is not None
    assert vectorizer is not None

def test_predict_category(setup_test_environment):
    """Kategori tahmin fonksiyonunu test eder."""
    category = predict_category("dijital pazarlama")
    assert category == "teknoloji"
    category_new = predict_category("yeni kelime")
    assert isinstance(category_new, str)

def test_reset_model(setup_test_environment):
    """Model sıfırlama fonksiyonunu test eder."""
    with open("feedback_history.json", "w") as f:
        f.write('{"some": "feedback"}')

    reset_model()

    assert not os.path.exists("feedback_history.json")
    # Varsayılan modelin tekrar yüklendiğini kontrol et
    category = predict_category("veri analizi")
    assert category == "teknoloji"

# --- utils.py Testleri ---

def test_read_json_file(setup_test_environment):
    """JSON okuma fonksiyonunu test eder."""
    data = read_json_file("test_manual_categories.json")
    assert data == {"test kelime": "test kategori"}

    # Mevcut olmayan dosya
    data_nonexistent = read_json_file("nonexistent.json", default_value=[])
    assert data_nonexistent == []

def test_load_proxies(setup_test_environment):
    """Proxy yükleme fonksiyonunu test eder."""
    with patch('utils.PROXIES_FILE', "test_proxies.json"):
        proxies = load_proxies()
        assert len(proxies) == 2
        assert proxies[0] == "http://1.1.1.1:8080"

@patch('utils.get_trend_score')
def test_analyze_keywords_no_proxy(mock_get_trend, setup_test_environment):
    """Proxy olmadan anahtar kelime analizini test eder."""
    # get_trend_score'u mock'la, (skor, proxy_listesi) döndürsün
    mock_get_trend.return_value = (75, None)

    keywords = ["yapay zeka", "veri bilimi"]
    df = analyze_keywords(keywords, use_proxy=False)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "Trend Skoru" in df.columns
    assert df["Trend Skoru"].iloc[0] == 75
    assert df["Kategori"].iloc[0] == "teknoloji"

# --- app.py Testleri ---

def test_init_session_state():
    """Streamlit session state başlatma fonksiyonunu test eder."""

    class MockSessionState:
        def __init__(self):
            self._data = {}

        def __contains__(self, key):
            return key in self._data

        def __setitem__(self, key, value):
            self._data[key] = value

        def __getattr__(self, key):
            if key in self._data:
                return self._data[key]
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'")

    mock_state = MockSessionState()

    with patch('app.st.session_state', mock_state):
        init_session_state()

        assert 'feedback' in mock_state
        assert 'use_proxy' in mock_state
        assert mock_state.use_proxy is True

# --- Entegrasyon Testi ---

@patch('utils.TrendReq')
def test_full_run_with_mock_api(mock_trend_req, setup_test_environment):
    """Uçtan uca bir senaryoyu mock API ile test eder."""
    # Pytrends'in davranışını taklit et
    mock_interest_df = pd.DataFrame({"test keyword": [50, 60, 70]})
    mock_trend_req.return_value.interest_over_time.return_value = mock_interest_df

    keywords = ["test keyword"]
    df = analyze_keywords(keywords, geo="TR", use_proxy=False)

    assert len(df) == 1
    assert df["Kelime"].iloc[0] == "test keyword"
    assert df["Trend Skoru"].iloc[0] == 60.0  # (50+60+70)/3
    assert df["Kategori"].iloc[0] != ""
