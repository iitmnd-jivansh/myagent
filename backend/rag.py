import chromadb
import ollama


# Load Chroma database
client = chromadb.PersistentClient(path="chroma_db")

collection = client.get_collection(
    name="knowledge_base"
)


def ask_question(query):

    # Create embedding for user query
    query_embedding_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )

    query_embedding = query_embedding_response["embedding"]

    # Search vector database
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )

    # Combine retrieved context
    context = "\n".join(results["documents"][0])

    # Build prompt
    prompt = f"""
You are a helpful AI assistant.

Answer ONLY using the provided context.

Context:
{context}

Question:
{query}
"""

    # Generate response
    response = ollama.chat(
        model="llama3",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]
