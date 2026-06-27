# Chat with PDF 📄

An AI-powered application that lets you upload any PDF and ask questions about it instantly.

## 🚀 Live Demo
[Click here to try it live](https://gen-ai-projects-caxfmgw7xzfg6jfbwqqlz7.streamlit.app/)

## 🛠️ Tech Stack
- **LangChain** — PDF loading and text splitting
- **FAISS** — Vector similarity search
- **Google Gemini** — Text embeddings
- **Groq + LLaMA 3** — Fast AI responses
- **Streamlit** — Web interface

## ⚙️ How it works
1. Upload any PDF file
2. App chunks the PDF and creates embeddings
3. Your question is matched against relevant chunks
4. LLaMA 3 generates an accurate answer

## 🏃 Run Locally
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## 🔑 Environment Variables
Create a `.env` file with:
```
GOOGLE_API_KEY=your_key
GROQ_API_KEY=your_key
```
