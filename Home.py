import streamlit as st

st.set_page_config(page_title="Milk Run Optimizer", layout="wide")
st.title("🧭 เลือกประเภท Optimizer")

st.markdown("เลือกเครื่องมือที่คุณต้องการใช้เพื่อคำนวณเส้นทางที่ดีที่สุด")

st.page_link("pages/01_tsp_optimizer.py", label="🚛 TSP-based Optimizer", icon="📍")
st.page_link("pages/02_savings_optimizer.py", label="🧠 Savings-based Optimizer", icon="🧮")
