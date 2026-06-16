import chromadb
import ollama
from search import search_web

# Load Chroma database
client = chromadb.PersistentClient(path="chroma_db")

collection = client.get_collection(
    name="knowledge_base"
)

SIMILARITY_THRESHOLD = 0.45


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

    docs = results["documents"][0]

    distances = results.get(
        "distances",
        [[999]]
    )[0]

    use_kb = (
        len(docs) > 0
        and len(distances) > 0
        and min(distances) < SIMILARITY_THRESHOLD
    )

    if use_kb:

        context = "\n".join(docs)

        prompt = f"""
You are a helpful AI assistant.

Answer ONLY using the provided context.

Context:
{context}

Question:
{query}
"""

        print("[RAG] Using Knowledge Base")

    else:

        web_answer = search_web(query)

        context = (
            web_answer
            if web_answer
            else "No information found."
        )

        prompt = f"""
You are a helpful AI assistant.

Use the following web information
to answer the question.

Web Information:
{context}

Question:
{query}
"""

        print("[RAG] Using SearXNG")

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
