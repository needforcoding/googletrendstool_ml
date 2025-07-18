import streamlit as st
import json
import pandas as pd
import plotly.express as px
from utils import analyze_keywords, load_manual_categories, save_feedback
from ml_model import update_model_with_feedback

st.set_page_config(page_title="Google Trends Pro Analiz Aracı", layout="wide")

with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.title("📊 Google Trends Toplu Analiz & Kategorilendirme")
st.markdown("**Makine öğrenimi destekli kategorilendirme + geri bildirimli öğrenme** sistemiyle çalışır.")

# Kelime Girişi
input_json = st.text_area("📝 Kelime Öbeklerini JSON Formatında Girin", height=200, placeholder='["kolajen serum", "diş macunu"]')

# Manuel kategori JSON alanı (opsiyonel)
manual_json_input = st.text_area("📁 Manuel Kategoriler (İsteğe Bağlı)", height=150, placeholder='{"kolajen serum": "Cilt Bakımı"}')

# Ayarlar
st.sidebar.header("⚙️ Ayarlar")
geo = st.sidebar.selectbox("Ülke", ["TR", "DE", "US", "GB", "FR"])
timeframe = st.sidebar.selectbox("Zaman Aralığı", ["now 7-d", "today 1-m", "today 3-m", "today 12-m", "today 5-y"], index=3)

if st.button("🚀 Araştırmayı Başlat"):
    try:
        keywords = json.loads(input_json)
        manual_map = json.loads(manual_json_input) if manual_json_input else {}
        df = analyze_keywords(keywords, geo=geo, timeframe=timeframe, manual_map=manual_map)
        st.success("✅ Analiz Tamamlandı")
        st.dataframe(df)

        # Kategorilere onay sorusu
        st.subheader("🧠 Kategori Doğrulama")
        for i, row in df.iterrows():
            key = row["Kelime"]
            suggested = row["Kategori"]
            col1, col2 = st.columns([2, 3])
            with col1:
                st.markdown(f"**{key}** için önerilen kategori: `{suggested}`")
            with col2:
                confirm = st.radio(f"Bu doğru mu? ({key})", ["Evet", "Hayır"], key=f"{key}_radio")
                if confirm == "Hayır":
                    new_cat = st.text_input(f"Yeni kategori gir ({key}):", key=f"{key}_input")
                    if new_cat:
                        save_feedback(key, new_cat)
                        update_model_with_feedback(key, new_cat)
                        st.success(f"🎯 Model güncellendi: {key} → {new_cat}")
                elif confirm == "Evet":
                    save_feedback(key, suggested)

        # Grafik
        st.subheader("📈 Trend Grafiği")
        fig = px.bar(df.sort_values("Trend Skoru", ascending=False), x="Kelime", y="Trend Skoru", color="Kategori", text="Trend Skoru")
        st.plotly_chart(fig, use_container_width=True)

        # Dışa Aktarım
        st.subheader("📤 Çıktılar")
        st.download_button("📁 CSV İndir", df.to_csv(index=False), "trend_sonuclar.csv", "text/csv")
        st.download_button("📄 Markdown İndir", df.to_markdown(index=False), "trend_sonuclar.md", "text/markdown")

    except Exception as e:
        st.error(f"Hata: {e}")
