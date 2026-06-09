import chromadb
import ollama

from pathlib import Path


# Create/load local Chroma database
client = chromadb.PersistentClient(path="chroma_db")

collection = client.get_or_create_collection(
    name="knowledge_base"
)


# Load text knowledge file
text_path = Path("knowledge/knowledge.txt")

print(f"Loading text file from: {text_path.absolute()}")


# Read text file
with open(text_path, "r", encoding="utf-8") as file:
    text = file.read()


# Chunking settings
chunk_size = 500
chunk_overlap = 100

chunks = []

start = 0

while start < len(text):

    end = start + chunk_size

    chunk = text[start:end]

    chunks.append(chunk)

    start += chunk_size - chunk_overlap


print(f"Created {len(chunks)} chunks")


# Generate embeddings and store in ChromaDB
for i, chunk in enumerate(chunks):

    print(f"Embedding chunk {i + 1}/{len(chunks)}")

    embedding_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=chunk
    )

    embedding = embedding_response["embedding"]

    collection.add(
        ids=[str(i)],
        embeddings=[embedding],
        documents=[chunk]
    )


print("Knowledge base indexed successfully.")
