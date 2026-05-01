import streamlit as st
import os
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.llms import HuggingFaceHub
from langchain_classic.chains import RetrievalQA
from langchain_classic.prompts import PromptTemplate

# 1. Page Configuration
st.set_page_config(page_title="Aether Corp Secure Intelligence", layout="wide")

# 2. Sidebar: Simulate Employee Login
st.sidebar.image("https://img.icons8.com/fluency/48/security-shield.png")
st.sidebar.title("Employee Portal")
user_role = st.sidebar.selectbox("Current User Role:", ["junior", "admin"])
st.sidebar.divider()
st.sidebar.info(f"Viewing access: **{user_role.upper()}**")

# 3. Initialize Models & DB (Cached for performance)
@st.cache_resource
def load_resources():
    # Embeddings: Free, local, and works perfectly for semantic search
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    # Vector DB: Use 'persist_directory' to load your pre-indexed MD files
    db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    
    # LLM: Using Phi-3.5-mini via HF Free Inference API
    llm = HuggingFaceHub(
        repo_id="microsoft/Phi-3.5-mini-4k-instruct",
        huggingfacehub_api_token=os.getenv("HF_TOKEN"),
        model_kwargs={"max_new_tokens": 512, "temperature": 0.1}
    )
    return db, llm

db, llm = load_resources()

# 4. Custom Prompt for Phi-3.5
# Note the specific <|system|> tags Phi-3.5 expects
template = """<|system|>
You are an AI assistant for Aether Corp. Use only the following context chunks to answer the question. 
If the answer is not in the context, say "I do not have authorization to view this information or it does not exist."
Context: {context}<|end|>
<|user|>
{question}<|end|>
<|assistant|>"""

QA_PROMPT = PromptTemplate(template=template, input_variables=["context", "question"])

# 5. The Main UI
st.title("📂 Multi-Document Secure RAG")
query = st.text_input("Search internal strategy and handbooks:", placeholder="e.g., What are our revenue targets?")

if query:
    with st.spinner("Retrieving authorized documents..."):
        # RBAC Logic: Juniors only see 'public', Admins see 'public' + 'admin'
        allowed_tags = ["public"] if user_role == "junior" else ["public", "admin"]
        search_filter = {"visibility": {"$in": allowed_tags}}

        # Setup Chain with filtered retriever
        retriever = db.as_retriever(search_kwargs={'filter': search_filter, 'k': 3})
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": QA_PROMPT}
        )

        response = qa_chain({"query": query})

        # 6. Display Results
        st.markdown("### 🤖 AI Response")
        st.write(response["result"])

        # 7. Citations (The "Job-Winning" feature)
        with st.expander("📄 Source Citations & Metadata"):
            for i, doc in enumerate(response["source_documents"]):
                st.markdown(f"**Source {i+1}:** `{doc.metadata.get('source', 'Unknown')}`")
                st.caption(f"Access Level: {doc.metadata.get('visibility')}")
                st.text_area(f"Chunk {i+1} content:", value=doc.page_content, height=100, disabled=True)