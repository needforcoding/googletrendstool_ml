import streamlit as st
import json
import pandas as pd
import plotly.express as px
import os
import logging
from utils import analyze_keywords, log_feedback_history
from ml_model import update_model_with_feedback, reset_model

# --- Loglama Ayarları ---
LOG_FILE = "app.log"
# Log dosyasının her başlangıçta temizlenmesi için (isteğe bağlı)
if os.path.exists(LOG_FILE):
    open(LOG_FILE, 'w').close()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GoogleTrendsApp")

# --- Streamlit Sayfa Yapılandırması ---
st.set_page_config(page_title="Google Trends ML Aracı", layout="wide")

# --- CSS Yükleme ---
def load_css(file_path="styles.css"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        logger.warning(f"{file_path} dosyası bulunamadı.")
    except Exception as e:
        logger.error(f"CSS dosyası yüklenemedi: {e}")

# --- Session State Başlatma ---
def init_session_state():
    defaults = {
        "feedback": {},
        "trend_errors": [],
        "use_proxy": True,
        "result_df": pd.DataFrame(),
        "analysis_running": False
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# --- UI Fonksiyonları ---
def toggle_proxy():
    st.session_state.use_proxy = not st.session_state.use_proxy
    logger.info(f"Proxy durumu değiştirildi: {'AÇIK' if st.session_state.use_proxy else 'KAPALI'}")

def render_sidebar():
    with st.sidebar:
        st.header("⚙️ Ayarlar")
        geo = st.selectbox("Ülke", ["TR", "DE", "US", "GB", "FR"], index=0, key="geo")
        timeframe = st.selectbox(
            "Zaman Aralığı",
            ["now 7-d", "today 1-m", "today 3-m", "today 12-m", "today 5-y"],
            index=3, key="timeframe"
        )

        st.markdown("---")
        proxy_status = "AÇIK ✅" if st.session_state.use_proxy else "KAPALI ❌"
        st.button(f"🌐 Proxy {proxy_status}", on_click=toggle_proxy)
        st.caption(f"Proxy şu anda {'etkin' if st.session_state.use_proxy else 'devre dışı'}.")

        st.markdown("---")
        if st.button("🧨 Modeli Sıfırla"):
            try:
                reset_model()
                st.success("✅ Model sıfırlandı ve geri bildirimler temizlendi.")
                logger.info("Model başarıyla sıfırlandı.")
                st.session_state.result_df = pd.DataFrame() # Sonuçları temizle
            except Exception as e:
                st.error(f"Model sıfırlanırken hata: {e}")
                logger.error(f"Model sıfırlama hatası: {e}", exc_info=True)

        st.markdown("---")
        st.subheader("📝 Loglar")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                log_content = f.read()
                st.download_button("📥 Log Dosyasını İndir", log_content, "app.log", "text/plain")
            with st.expander("Logları Görüntüle"):
                st.code(log_content)

def render_main_content():
    st.title("📊 Google Trends Toplu Analiz + ML Destekli Kategorilendirme")

    with st.form("input_form"):
        input_json = st.text_area(
            "📝 Anahtar Kelimeleri JSON Dizisi Olarak Girin",
            '["yapay zeka", "makine öğrenmesi", "veri bilimi", "streamlit", "python"]',
            height=150, key="input_json"
        )
        manual_input = st.text_area(
            "📁 Manuel Kategoriler (Opsiyonel, JSON Formatında)",
            '{"streamlit": "teknoloji", "python": "teknoloji"}',
            height=100, key="manual_input"
        )
        submitted = st.form_submit_button("🚀 Analize Başla")

    if submitted and not st.session_state.analysis_running:
        handle_analysis(input_json, manual_input)

    if not st.session_state.result_df.empty:
        render_results()

def handle_analysis(input_json, manual_input):
    st.session_state.analysis_running = True
    st.session_state.trend_errors = []

    try:
        keywords = json.loads(input_json)
        assert isinstance(keywords, list), "Anahtar kelimeler JSON formatında bir liste olmalıdır!"
    except (json.JSONDecodeError, AssertionError) as e:
        st.error(f"❌ Geçersiz anahtar kelime formatı: {e}")
        st.session_state.analysis_running = False
        return

    try:
        manual_map = json.loads(manual_input) if manual_input.strip() else {}
        assert isinstance(manual_map, dict), "Manuel kategoriler JSON formatında bir sözlük olmalıdır!"
    except (json.JSONDecodeError, AssertionError) as e:
        st.error(f"❌ Geçersiz manuel kategori formatı: {e}")
        st.session_state.analysis_running = False
        return

    if not keywords:
        st.warning("Lütfen analiz için en az bir anahtar kelime girin.")
        st.session_state.analysis_running = False
        return

    df = analyze_keywords(
        keywords,
        geo=st.session_state.geo,
        timeframe=st.session_state.timeframe,
        manual_map=manual_map,
        use_proxy=st.session_state.use_proxy
    )
    st.session_state.result_df = df
    st.session_state.feedback = {row["Kelime"]: row["Kategori"] for _, row in df.iterrows()}
    st.session_state.analysis_running = False
    st.rerun()

def render_results():
    st.success("✅ Analiz tamamlandı.")
    df = st.session_state.result_df
    st.dataframe(df)

    with st.form("feedback_form"):
        st.subheader("🧠 Kategori Doğrulama ve Model Eğitimi")
        for index, row in df.iterrows():
            st.session_state.feedback[row["Kelime"]] = st.text_input(
                f"**{row['Kelime']}** (Mevcut: *{row['Kategori']}*)",
                value=row["Kategori"],
                key=f"feedback_{index}"
            )

        if st.form_submit_button("✅ Geri Bildirimleri Kaydet ve Modeli Güncelle"):
            handle_feedback()

    render_charts_and_exports(df)
    render_error_log()

def handle_feedback():
    changes = []
    df = st.session_state.result_df
    for index, row in df.iterrows():
        original_cat = row["Kategori"]
        new_cat = st.session_state.feedback.get(row["Kelime"])
        if new_cat and new_cat != original_cat:
            changes.append((row["Kelime"], new_cat))

    if changes:
        try:
            keywords, categories = zip(*changes)
            update_model_with_feedback(list(keywords), list(categories))
            for kw, cat in changes:
                log_feedback_history(kw, cat)
            st.success(f"🎉 Model, {len(changes)} yeni geri bildirim ile güncellendi!")
            logger.info(f"{len(changes)} geri bildirim ile model güncellendi.")
        except Exception as e:
            st.error(f"Geri bildirim işlenirken hata: {e}")
            logger.error(f"Geri bildirim hatası: {e}", exc_info=True)
    else:
        st.info("ℹ️ Modelde güncellenecek yeni bir geri bildirim bulunmuyor.")

    # Geri bildirim sonrası sonuçları yenilemek için
    st.session_state.result_df = pd.DataFrame()

def render_charts_and_exports(df):
    st.subheader("📈 Trend Grafiği")
    fig = px.bar(
        df.sort_values("Trend Skoru", ascending=False),
        x="Kelime", y="Trend Skoru", color="Kategori",
        title="Anahtar Kelime Trend Skorları"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📊 Kategori Dağılımı")
    if "Kategori" in df.columns and not df["Kategori"].empty:
        cat_counts = df["Kategori"].value_counts().reset_index()
        cat_counts.columns = ["Kategori", "Sayı"]
        fig2 = px.pie(cat_counts, values="Sayı", names="Kategori", title="Kategori Dağılımı")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("📤 Dışa Aktar")
    csv = df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("📥 CSV İndir (UTF-8)", csv, "trend_sonuclar.csv", "text/csv")

def render_error_log():
    if st.session_state.trend_errors:
        st.warning("⚠️ Analiz sırasında bazı hatalar oluştu:")
        with st.expander("Hata Detaylarını Gör", expanded=True):
            for err in st.session_state.trend_errors:
                st.error(err)

# --- Ana Uygulama Akışı ---
def main():
    load_css()
    init_session_state()
    render_sidebar()
    render_main_content()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Uygulama genelinde yakalanamayan bir hata oluştu: {e}", exc_info=True)
        st.error("⛔ Beklenmeyen kritik bir hata oluştu. Lütfen logları kontrol edin.")
