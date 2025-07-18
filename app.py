import streamlit as st
import json
import pandas as pd
import plotly.express as px
from utils import analyze_keywords, load_manual_categories
from ml_model import update_model_with_feedback

st.set_page_config(page_title="Google Trends ML Aracı", layout="wide")

with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.title("📊 Google Trends Toplu Analiz + ML Destekli Kategorilendirme")

if "feedback" not in st.session_state:
    st.session_state["feedback"] = {}

# 1. Veri Girişi
input_json = st.text_area("📝 Kelime Öbeklerini JSON Girin", height=200)
manual_input = st.text_area("📁 Manuel Kategoriler (Opsiyonel)", height=150)

# 2. Ayarlar
st.sidebar.header("⚙️ Ayarlar")
geo = st.sidebar.selectbox("Ülke", ["TR", "DE", "US"], index=0)
timeframe = st.sidebar.selectbox("Zaman Aralığı", ["now 7-d", "today 1-m", "today 3-m", "today 12-m", "today 5-y"], index=3)

if st.button("🚀 Analize Başla"):
    try:
        keywords = json.loads(input_json)
        manual_map = json.loads(manual_input) if manual_input else {}
        df = analyze_keywords(keywords, geo=geo, timeframe=timeframe, manual_map=manual_map)
        st.session_state["result_df"] = df

        st.success("Analiz tamamlandı.")
        st.dataframe(df)

        st.subheader("🧠 Kategori Doğrulama")
        for i, row in df.iterrows():
            kw = row["Kelime"]
            default = row["Kategori"]
            new_cat = st.text_input(f"{kw} → {default}", value=default, key=f"feedback_{kw}")
            st.session_state["feedback"][kw] = new_cat

        st.subheader("📈 Trend Grafiği")
        fig = px.bar(df.sort_values("Trend Skoru", ascending=False), x="Kelime", y="Trend Skoru", color="Kategori")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("📤 Dışa Aktar")
        st.download_button("📥 CSV İndir", df.to_csv(index=False), "trend_sonuclar.csv", "text/csv")
        st.download_button("📥 Markdown İndir", df.to_markdown(index=False), "trend_sonuclar.md", "text/markdown")

    except Exception as e:
        st.error(f"Hata: {e}")

# KAYDET butonu en altta
if st.button("✅ Geri Bildirimleri Kaydet"):
    try:
        keys = list(st.session_state["feedback"].keys())
        values = list(st.session_state["feedback"].values())
        update_model_with_feedback(keys, values)
        st.success("🎉 Geri bildirimler başarıyla kaydedildi ve model güncellendi.")
    except Exception as e:
        st.error(f"Kaydetme sırasında hata oluştu: {e}")
