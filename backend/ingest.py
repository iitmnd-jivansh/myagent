import chromadb
import ollama

from pathlib import Path


# Create/load local Chroma database
client = chromadb.PersistentClient(path="chroma_db")

collection = client.get_or_create_collection(
    name="knowledge_base"
)

print("=" * 60)
print("[INGEST] Knowledge Base Ingestion Tool")
print("[INGEST]   ChromaDB path: chroma_db")
print("[INGEST]   Collection: knowledge_base")
print("=" * 60)


# Load text knowledge file
text_path = Path("knowledge/knowledge.txt")

print(f"[INGEST] Loading text file from: {text_path.absolute()}")

if not text_path.exists():
    print(f"[INGEST] ❌ ERROR: File not found at {text_path.absolute()}")
    print("[INGEST]   Please ensure knowledge/knowledge.txt exists")
    exit(1)

file_size = text_path.stat().st_size
print(f"[INGEST]   File size: {file_size} bytes ({file_size/1024:.1f} KB)")


# Read text file
with open(text_path, "r", encoding="utf-8") as file:
    text = file.read()

print(f"[INGEST]   Total characters read: {len(text):,}")
print(f"[INGEST]   Estimated words: {len(text.split()):,}")


# Chunking settings
chunk_size = 500
chunk_overlap = 100

print(f"[INGEST] Chunking configuration:")
print(f"[INGEST]   Chunk size: {chunk_size} chars")
print(f"[INGEST]   Chunk overlap: {chunk_overlap} chars")
print(f"[INGEST]   Effective stride: {chunk_size - chunk_overlap} chars")

chunks = []

start = 0

while start < len(text):
    end = start + chunk_size
    chunk = text[start:end]
    chunks.append(chunk)
    start += chunk_size - chunk_overlap

print(f"[INGEST] Created {len(chunks)} chunks from source text")
print(f"[INGEST]   Average chunk length: {sum(len(c) for c in chunks) / len(chunks):.0f} chars")


# Generate embeddings and store in ChromaDB
print(f"[INGEST] Starting embedding generation and storage...")
print(f"[INGEST]   Embedding model: nomic-embed-text (Ollama)")
print(f"[INGEST]   Total chunks to process: {len(chunks)}")

for i, chunk in enumerate(chunks):
    print(f"[INGEST]   Processing chunk {i + 1}/{len(chunks)}...", end="")

    embedding_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=chunk
    )

    embedding = embedding_response["embedding"]
    print(f" embedding dimension={len(embedding)}")

    collection.add(
        ids=[str(i)],
        embeddings=[embedding],
        documents=[chunk]
    )

print(f"[INGEST] ✅ All {len(chunks)} chunks embedded and stored in ChromaDB")
print(f"[INGEST]   Collection 'knowledge_base' now contains {collection.count()} documents")
print("=" * 60)
print("[INGEST] Knowledge base indexed successfully.")
print("=" * 60)