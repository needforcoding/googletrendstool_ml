import streamlit as st
import json
import pandas as pd
import plotly.express as px
from utils import analyze_keywords, load_manual_categories, log_feedback_history
from ml_model import update_model_with_feedback, reset_model

st.set_page_config(page_title="Google Trends ML Aracı", layout="wide")

# CSS yükle
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.title("📊 Google Trends Toplu Analiz + ML Destekli Kategorilendirme")

# Session state başlat
if "feedback" not in st.session_state:
    st.session_state["feedback"] = {}
if "trend_errors" not in st.session_state:
    st.session_state["trend_errors"] = []
if "use_proxy" not in st.session_state:
    st.session_state["use_proxy"] = True

# 🔧 Ayarlar
st.sidebar.header("⚙️ Ayarlar")
geo = st.sidebar.selectbox("Ülke", ["TR", "DE", "US"], index=0)
timeframe = st.sidebar.selectbox("Zaman Aralığı", ["now 7-d", "today 1-m", "today 3-m", "today 12-m", "today 5-y"], index=3)
st.sidebar.markdown("---")
use_proxy = st.sidebar.checkbox("🌐 Proxy kullan", value=st.session_state["use_proxy"])
st.session_state["use_proxy"] = use_proxy

# 🔁 Modeli Sıfırla
with st.sidebar:
    if st.button("🧨 Modeli Sıfırla"):
        if st.confirm("Modeli sıfırlamak istediğinize emin misiniz? Bu işlem geri alınamaz."):
            reset_model()
            st.success("✅ Model sıfırlandı ve yeniden eğitildi.")

# 🔽 Veri Girişi
with st.form("input_form"):
    input_json = st.text_area("📝 Kelime Öbeklerini JSON Girin", height=200)
    manual_input = st.text_area("📁 Manuel Kategoriler (Opsiyonel)", height=150)
    submitted = st.form_submit_button("🚀 Analize Başla")

# 📊 Analiz Başlat
if submitted:
    try:
        keywords = json.loads(input_json)
        manual_map = json.loads(manual_input) if manual_input else {}
        df = analyze_keywords(keywords, geo=geo, timeframe=timeframe, manual_map=manual_map, use_proxy=use_proxy)
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
                new_cat = st.text_input(f"{kw} → {default}", value=default, key=f"feedback_{kw}")
                st.session_state["feedback"][kw] = new_cat

            save_clicked = st.form_submit_button("✅ Geri Bildirimleri Kaydet")
            if save_clicked:
                try:
                    keys = list(st.session_state["feedback"].keys())
                    values = list(st.session_state["feedback"].values())
                    update_model_with_feedback(keys, values)
                    for k, v in zip(keys, values):
                        log_feedback_history(k, v)
                    st.success("🎉 Model güncellendi ve geçmişe kaydedildi.")
                except Exception as e:
                    st.error(f"Hata: {e}")

        # 📈 Grafik
        st.subheader("📈 Trend Grafiği")
        fig = px.bar(df.sort_values("Trend Skoru", ascending=False), x="Kelime", y="Trend Skoru", color="Kategori")
        st.plotly_chart(fig, use_container_width=True)

        # 📤 Dışa Aktar
        st.subheader("📤 Dışa Aktar")
        st.download_button("📥 CSV İndir", df.to_csv(index=False), "trend_sonuclar.csv", "text/csv")
        st.download_button("📥 Markdown İndir", df.to_markdown(index=False), "trend_sonuclar.md", "text/markdown")

        # ⚠️ Proxy hataları varsa göster
        if st.session_state["trend_errors"]:
            st.warning("⚠️ Hatalar oluştu. Detaylar:")
            for err in st.session_state["trend_errors"]:
                st.code(err)

    except Exception as e:
        st.error(f"⛔ Hata: {e}")
