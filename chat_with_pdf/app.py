import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from groq import Groq
os.environ["GOOGLE_API_KEY"] = ""
GROQ_API_KEY=""


client = Groq(api_key=GROQ_API_KEY)

loader = PyPDFLoader("2_month_placement.pdf")
pages = loader.load()

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(pages)

embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
vectorstore = FAISS.from_documents(chunks, embeddings)

question = "What should I do in Week 1?"
relevant_chunks = vectorstore.similarity_search(question, k=3)
context = "\n".join([doc.page_content for doc in relevant_chunks])

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "user", "content": f"Answer based on context:\n{context}\n\nQuestion: {question}"}
    ]
)

print(f"Question: {question}")
print(f"Answer: {response.choices[0].message.content}")