import streamlit as st

st.sidebar.title("Login Simulation")
role = st.sidebar.selectbox("Select your Role:", ["junior", "admin"])

query = st.text_input("Ask a question about the company:")

if query:
    # Use the 'role' variable to filter your Vector DB search
    results = vectorstore.similarity_search(query, filter={"role": role})
    # ... send to LLM and display ...