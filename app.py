import streamlit as st
import json
import pandas as pd
import plotly.express as px
from utils import analyze_keywords, load_manual_categories
from ml_model import update_model_with_feedback, reset_model
import logging
import time

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
use_proxy = st.sidebar.checkbox("🌐 Proxy kullan", value=st.session_state.get("use_proxy", True), help="İşaretlendiğinde, `proxies.json` dosyasından rastgele bir proxy seçilir. Sayfanın yeniden yüklenmesi normaldir. Ayar, 'Analize Başla' butonuna basıldığında uygulanır.")
st.session_state["use_proxy"] = use_proxy

# 🔁 Modeli Sıfırla
with st.sidebar:
    if st.button("🧨 Modeli ve Geri Bildirimleri Sıfırla"):
        # Bu butona basıldığında, ana alanda bir onay kutusu görünecek.
        # Ancak Streamlit'in akışı nedeniyle, bunu doğrudan yönetmek zor.
        # En basit yaklaşım, doğrudan st.confirm kullanmaktır.
        # Bu, sidebar'da olmasa da işlevseldir.
        st.session_state['reset_triggered'] = True

if st.session_state.get('reset_triggered'):
    st.warning("Modeli ve tüm geri bildirimleri sıfırlamak üzeresiniz.")
    if st.button("Evet, Sıfırla"):
        reset_model()
        st.success("✅ Model ve geri bildirimler sıfırlandı.")
        st.info("Değişikliklerin yansıması için uygulama birkaç saniye içinde yeniden başlatılacak...")
        del st.session_state['reset_triggered'] # State'i temizle
        time.sleep(3)
        st.experimental_rerun()
    if st.button("Hayır, İptal Et"):
        del st.session_state['reset_triggered'] # State'i temizle
        st.experimental_rerun()

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

                    # Geri bildirimleri yeni sisteme göre kaydet
                    update_model_with_feedback(keys, values)

                    st.success("🎉 Geri bildirimleriniz kaydedildi! Model, uygulama bir sonraki yeniden başlatıldığında veya manuel olarak sıfırlandığında bu verilerle güncellenecektir.")
                except Exception as e:
                    st.error(f"Geri bildirim kaydedilirken hata oluştu: {e}")
                    logging.error(f"Geri bildirim kaydetme hatası: {e}", exc_info=True)

        # 📈 Grafik
        st.subheader("📈 Trend Grafiği")
        fig = px.bar(df.sort_values("Trend Skoru", ascending=False), x="Kelime", y="Trend Skoru", color="Kategori")
        st.plotly_chart(fig, use_container_width=True)

        # 📤 Dışa Aktar
        st.subheader("📤 Dışa Aktar")
        st.download_button("📥 CSV İndir", df.to_csv(index=False), "trend_sonuclar.csv", "text/csv")
        st.download_button("📥 Markdown İndir", df.to_markdown(index=False), "trend_sonuclar.md", "text/markdown")

        # ⚠️ Hataları göster
        if st.session_state.get("trend_errors"):
            st.warning("⚠️ Analiz sırasında bazı hatalar oluştu. Detaylar aşağıda ve log dosyasındadır.")
            with st.expander("Hata Detaylarını Gör"):
                for err in st.session_state["trend_errors"]:
                    st.error(err)

        # 📜 Logları Göster
        st.subheader("📜 Uygulama Logları")
        try:
            with open("app.log", "r", encoding="utf-8") as f:
                log_content = f.read()
            st.code(log_content, language="log")
            st.download_button("📥 Log Dosyasını İndir", log_content, "app.log", "text/plain")
        except FileNotFoundError:
            st.info("Henüz bir log kaydı oluşturulmadı.")

    except Exception as e:
        st.error(f"⛔ Beklenmedik bir hata oluştu: {e}")
        logging.error(f"Uygulama çökmesi: {e}", exc_info=True)
