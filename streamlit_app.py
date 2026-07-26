"""Interface Streamlit simulant une conversation WhatsApp avec l'assistant."""
import os
import uuid

import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Simulateur WhatsApp — Assistant Vendeur", page_icon="💬")
st.title("💬 Simulateur WhatsApp — Assistant Commercial")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_log_id" not in st.session_state:
    st.session_state.last_log_id = None

with st.sidebar:
    st.markdown("### Client")
    customer_phone = st.text_input("Numéro de téléphone", value="+2250700000000")
    st.caption(f"Session : `{st.session_state.session_id}`")
    if st.button("Nouvelle conversation"):
        st.session_state.session_id = str(uuid.uuid4())[:8]
        st.session_state.messages = []
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if prompt := st.chat_input("Écrivez comme un client sur WhatsApp..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("..."):
            try:
                resp = requests.post(
                    f"{API_BASE_URL}/chat",
                    json={
                        "session_id": st.session_state.session_id,
                        "customer_phone": customer_phone,
                        "message": prompt,
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
                st.write(data["response"])
                if data["tools_called"]:
                    st.caption(f"Outils utilisés : {', '.join(data['tools_called'])} · "
                               f"{data['latency_ms']} ms")
            except Exception as exc:
                data = {"response": f"Erreur : {exc}"}
                st.error(data["response"])

    st.session_state.messages.append({"role": "assistant", "content": data["response"]})

    col1, col2 = st.columns(2)
    if col1.button("👍 Bonne réponse"):
        st.toast("Merci pour votre retour !")
    if col2.button("👎 Mauvaise réponse"):
        st.toast("Merci, nous allons améliorer l'assistant.")
