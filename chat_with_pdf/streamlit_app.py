import os
import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from groq import Groq
import tempfile

from dotenv import load_dotenv
load_dotenv()

os.environ["GOOGLE_API_KEY"]=os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY=os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

st.set_page_config(page_title="Chat with PDF", page_icon="📄", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #0f1117; }
    .stTextInput>div>div>input {
        background-color: #1e1e2e;
        color: white;
        border-radius: 10px;
        padding: 10px;
    }
    .stFileUploader { background-color: #1e1e2e; border-radius: 10px; padding: 10px; }
    .answer-box {
        background-color: #1e1e2e;
        padding: 20px;
        border-radius: 15px;
        border-left: 4px solid #7c3aed;
        color: white;
        margin-top: 20px;
    }
    .title { text-align: center; color: white; font-size: 2.5rem; font-weight: 800; }
    .subtitle { text-align: center; color: #9ca3af; font-size: 1rem; margin-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="title">📄 Chat with your PDF</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Upload any PDF and ask questions about it instantly</p>', unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload your PDF", type="pdf")

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name

    with st.spinner("⚡ Processing your PDF..."):
        loader = PyPDFLoader(tmp_path)
        pages = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = splitter.split_documents(pages)
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        vectorstore = FAISS.from_documents(chunks, embeddings)

    st.success(f"✅ PDF loaded successfully — {len(pages)} pages, {len(chunks)} chunks indexed")

    question = st.text_input("💬 Ask anything about your PDF...")

    if question:
        with st.spinner("🤖 Thinking..."):
            relevant_chunks = vectorstore.similarity_search(question, k=3)
            context = "\n".join([doc.page_content for doc in relevant_chunks])

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "user", "content": f"Answer based on context:\n{context}\n\nQuestion: {question}"}
                ]
            )
            answer = response.choices[0].message.content

        st.markdown(f'<div class="answer-box">🤖 <strong>Answer:</strong><br><br>{answer}</div>', unsafe_allow_html=True)