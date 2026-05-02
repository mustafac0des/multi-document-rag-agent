import os
import re
import yaml
import chromadb

from sentence_transformers import SentenceTransformer
from transformers import T5Tokenizer, T5ForConditionalGeneration
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

DATA_DIR = "company_documents"
USER = {"role": "engineer"}

tokenizer = T5Tokenizer.from_pretrained("google/flan-t5-small")
model = T5ForConditionalGeneration.from_pretrained("google/flan-t5-small")
embedder_model = SentenceTransformer("all-MiniLM-L6-v2")

class SentenceTransformerEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return embedder_model.encode(texts).tolist()

    def embed_query(self, text):
        return embedder_model.encode([text])[0].tolist()

embeddings = SentenceTransformerEmbeddings()

vectorstore = Chroma(
    persist_directory="./chroma_db",
    collection_name="aether_collection",
    embedding_function=embeddings,
)

def parse_markdown(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    fm_match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
    if fm_match:
        frontmatter = yaml.safe_load(fm_match.group(1)) or {}
        body = content[fm_match.end():]
    else:
        frontmatter = {}
        body = content

    body = re.sub(r"\n---\n", "\n", body)

    if not body.startswith("\n"):
        body = "\n" + body

    sections = re.split(r'\n(?=#{1,6} )', body)

    docs = []

    raw_roles = frontmatter.get("allowed_roles", [])
    roles = raw_roles if isinstance(raw_roles, list) else [raw_roles]

    for section in sections:
        section = section.strip()
        if not section:
            continue

        lines = section.split("\n")
        section_title = lines[0].strip()

        if section_title.strip("-") == "":
            continue

        docs.append(
            Document(
                page_content=(
                    f"DOCUMENT: {frontmatter.get('title', '')}\n"
                    f"SECTION: {section_title}\n"
                    f"CONTENT:\n{section}"
                ),
                metadata={
                    "section": section_title,
                    "allowed_roles": roles,
                    "access_level": frontmatter.get("access_level", ""),
                    "department": frontmatter.get("department", ""),
                    "date": frontmatter.get("date", "")
                }
            )
        )

    return docs

def ingest_documents():
    if vectorstore._collection.count() > 0:
        return

    all_docs = []

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    for file in os.listdir(DATA_DIR):
        if file.endswith(".md"):
            all_docs.extend(parse_markdown(os.path.join(DATA_DIR, file)))

    if all_docs:
        vectorstore.add_documents(all_docs)

def generate(prompt, max_new_tokens=150):
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=256)
    outputs = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=True, temperature=0.7, top_p=0.9)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)

def retrieve(query):
    return vectorstore.as_retriever(search_kwargs={"k": 3}).invoke(query)

def filter_docs(docs):
    filtered = []
    for doc in docs:
        roles = doc.metadata.get("allowed_roles", [])
        if USER["role"] in roles:
            filtered.append(doc)

    return filtered

def query_system(query):
    docs = retrieve(query)
    docs = filter_docs(docs)

    if not docs:
        return "I cannot help you with that. Try asking something else!"

    context = "\n\n---\n\n".join([d.page_content for d in docs[:2]])
    prompt = f"""You are a question-answering assistant. Use the following context to answer the question. If you don't know the answer, say, "I cannot help you with that. Try asking something else!" Provide concise and accurate answers based on the provided context.
    Context:
    {context}

    Question:
    {query}
    """

    return generate(prompt)

if __name__ == "__main__":
    print("Initializing system...")
    ingest_documents()
    print("Ready.\n")

    while True:
        q = input("Ask a question (or 'exit'): ")
        if q.lower() == "exit":
            break

        print(f"\nResponse:\n{query_system(q)}\n")