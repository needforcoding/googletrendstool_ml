
import streamlit as st
import json
import pandas as pd
import plotly.express as px
import os
import logging
from utils import analyze_keywords, load_manual_categories, log_feedback_history
from ml_model import update_model_with_feedback, reset_model

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GoogleTrendsApp")

# Streamlit yapılandırması
st.set_page_config(page_title="Google Trends ML Aracı", layout="wide")

# CSS yükle
try:
    with open("styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except Exception as e:
    logger.error(f"CSS dosyası yüklenemedi: {e}")

st.title("📊 Google Trends Toplu Analiz + ML Destekli Kategorilendirme")

# Session state başlat
if "feedback" not in st.session_state:
    st.session_state["feedback"] = {}
if "trend_errors" not in st.session_state:
    st.session_state["trend_errors"] = []
if "use_proxy" not in st.session_state:
    st.session_state["use_proxy"] = True

# Proxy durumunu değiştirme işlevi - sayfa yenilemeden
def toggle_proxy():
    st.session_state["use_proxy"] = not st.session_state["use_proxy"]
    logger.info(f"Proxy durumu değiştirildi: {st.session_state['use_proxy']}")

# 🔧 Ayarlar
st.sidebar.header("⚙️ Ayarlar")
geo = st.sidebar.selectbox("Ülke", ["TR", "DE", "US"], index=0)
timeframe = st.sidebar.selectbox("Zaman Aralığı", 
                               ["now 7-d", "today 1-m", "today 3-m", "today 12-m", "today 5-y"], 
                               index=3)

st.sidebar.markdown("---")
st.sidebar.button(
    "🌐 Proxy " + ("AÇIK ✅" if st.session_state["use_proxy"] else "KAPALI ❌"), 
    on_click=toggle_proxy,
    key="proxy_toggle"
)
st.sidebar.caption(f"Proxy şu anda {'etkin' if st.session_state['use_proxy'] else 'devre dışı'}")

# 🔁 Modeli Sıfırla
with st.sidebar:
    if st.button("🧨 Modeli Sıfırla"):
        try:
            reset_model()
            st.success("✅ Model sıfırlandı ve yeniden eğitildi.")
            logger.info("Model sıfırlandı ve yeniden eğitildi.")
        except Exception as e:
            st.error(f"Model sıfırlanırken hata oluştu: {e}")
            logger.error(f"Model sıfırlanırken hata: {e}")

# 🔽 Veri Girişi
with st.form("input_form"):
    input_json = st.text_area("📝 Kelime Öbeklerini JSON Girin", height=200)
    manual_input = st.text_area("📁 Manuel Kategoriler (Opsiyonel)", height=150)
    submitted = st.form_submit_button("🚀 Analize Başla")

# 📊 Analiz Başlat
if submitted:
    try:
        # JSON doğrulama
        try:
            keywords = json.loads(input_json)
            if not isinstance(keywords, list):
                st.error("❌ JSON içeriği bir liste olmalıdır!")
                keywords = []
        except json.JSONDecodeError:
            st.error("❌ Geçersiz JSON formatı!")
            keywords = []
        
        # Manuel harita doğrulama
        try:
            manual_map = json.loads(manual_input) if manual_input else {}
            if not isinstance(manual_map, dict):
                st.error("❌ Manuel kategoriler bir sözlük olmalıdır!")
                manual_map = {}
        except json.JSONDecodeError:
            st.error("❌ Geçersiz manuel kategori JSON formatı!")
            manual_map = {}

        if keywords:
            with st.spinner("🔍 Anahtar kelimeler analiz ediliyor..."):
                logger.info(f"Analiz başlıyor: {len(keywords)} anahtar kelime")
                df = analyze_keywords(
                    keywords, 
                    geo=geo, 
                    timeframe=timeframe, 
                    manual_map=manual_map, 
                    use_proxy=st.session_state["use_proxy"]
                )
                st.session_state["result_df"] = df
                st.session_state["feedback"] = {}

            st.success("✅ Analiz tamamlandı.")
            st.dataframe(df)

            # 🧠 Geri Bildirim Formu
            with st.form("feedback_form"):
                st.subheader("🧠 Kategori Doğrulama")
                
                for i, row in df.iterrows():
                    kw = row["Kelime"]
                    default = row["Kategori"]
                    new_cat = st.text_input(
                        f"{kw} → {default}", 
                        value=default, 
                        key=f"feedback_{kw}"
                    )
                    st.session_state["feedback"][kw] = new_cat

                save_clicked = st.form_submit_button("✅ Geri Bildirimleri Kaydet")
                
                if save_clicked and st.session_state["feedback"]:
                    try:
                        keys = list(st.session_state["feedback"].keys())
                        values = list(st.session_state["feedback"].values())
                        
                        # Sadece değişiklik olan geri bildirimleri kaydet
                        changes = []
                        for i, (k, v) in enumerate(zip(keys, values)):
                            original = df[df["Kelime"] == k]["Kategori"].values[0]
                            if v != original:
                                changes.append((k, v))
                                
                        if changes:
                            change_keys = [c[0] for c in changes]
                            change_values = [c[1] for c in changes]
                            
                            update_model_with_feedback(change_keys, change_values)
                            for k, v in changes:
                                log_feedback_history(k, v)
                                
                            st.success(f"🎉 Model güncellendi ve {len(changes)} değişiklik kaydedildi.")
                            logger.info(f"Model güncellendi ve {len(changes)} değişiklik kaydedildi.")
                        else:
                            st.info("ℹ️ Değişiklik yapılmadı.")
                    except Exception as e:
                        st.error(f"⚠️ Hata: {e}")
                        logger.error(f"Geri bildirim kaydedilirken hata: {e}")

            # 📈 Grafik
            st.subheader("📈 Trend Grafiği")
            fig = px.bar(
                df.sort_values("Trend Skoru", ascending=False), 
                x="Kelime", 
                y="Trend Skoru", 
                color="Kategori",
                title="Anahtar Kelime Trend Skorları"
            )
            st.plotly_chart(fig, use_container_width=True)

            # 📊 Kategori Dağılımı
            st.subheader("📊 Kategori Dağılımı")
            cat_counts = df["Kategori"].value_counts().reset_index()
            cat_counts.columns = ["Kategori", "Anahtar Kelime Sayısı"]
            fig2 = px.pie(
                cat_counts, 
                values="Anahtar Kelime Sayısı", 
                names="Kategori",
                title="Kategori Dağılımı"
            )
            st.plotly_chart(fig2, use_container_width=True)

            # 📤 Dışa Aktar
            st.subheader("📤 Dışa Aktar")
            csv = df.to_csv(index=False, encoding="utf-8")
            st.download_button("📥 CSV İndir", csv, "trend_sonuclar.csv", "text/csv")
            
            md = df.to_markdown(index=False)
            st.download_button("📥 Markdown İndir", md, "trend_sonuclar.md", "text/markdown")

            # Log dosyasını indir
            if os.path.exists("app.log"):
                with open("app.log", "r", encoding="utf-8") as log_file:
                    log_content = log_file.read()
                st.download_button("📥 Log Dosyasını İndir", log_content, "app_log.txt", "text/plain")

            # ⚠️ Proxy hataları varsa göster
            if st.session_state["trend_errors"]:
                st.warning("⚠️ Hatalar oluştu. Detaylar:")
                for err in st.session_state["trend_errors"]:
                    st.code(err)

    except Exception as e:
        st.error(f"⛔ Beklenmeyen hata: {e}")
        logger.error(f"Beklenmeyen hata: {e}", exc_info=True)

