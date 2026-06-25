import chromadb
import ollama
from search import search_web

# Load Chroma database
client = chromadb.PersistentClient(
    path="chroma_db"
)

collection = client.get_collection(
    name="knowledge_base"
)

SIMILARITY_THRESHOLD = 300

chat_history = []
def ask_question(
    query,
    language="en"
):

    # Create embedding for user query
    query_embedding_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )

    query_embedding = query_embedding_response[
        "embedding"
    ]

    # Search vector database
    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=3
    )

    docs = results["documents"][0]

    distances = results.get(
        "distances",
        [[999]]
    )[0]

    best_distance = min(distances)

    print("=" * 50)
    print("Query:", query)
    print("Language:", language)
    print("Best Distance:", best_distance)
    print("Distances:", distances)
    print("=" * 50)

    use_kb = (
        len(docs) > 0
        and best_distance < SIMILARITY_THRESHOLD
    )

    if language == "hi":

        language_instruction = """
उत्तर केवल हिन्दी में दें।
सभी उत्तर प्राकृतिक हिन्दी में दें।
अंग्रेज़ी का उपयोग केवल आवश्यकता होने पर करें.
"""

    else:

        language_instruction = """
Answer only in English.
"""

    if use_kb:

        context = "\n".join(docs)

        prompt = f"""
You are a helpful AI assistant.

{language_instruction}

Answer ONLY using the provided context.

Context:
{context}

Question:
{query}
"""

        print(
            f"[RAG] Using Knowledge Base "
            f"(distance={best_distance:.3f})"
        )

    else:

        web_answer = search_web(query)

        context = (
            web_answer
            if web_answer
            else "No information found."
        )

        prompt = f"""
You are a helpful AI assistant.

{language_instruction}

Use the following web information
to answer the question.

Web Information:
{context}

Question:
{query}
"""

        print(
            f"[RAG] Using SearXNG "
            f"(distance={best_distance:.3f})"
        )

    global chat_history

    messages = []
    for msg in chat_history:
        messages.append(msg)

    messages.append({
        "role": "user",
        "content": prompt
    })

    response = ollama.chat(
        model="llama3",
        messages=messages
    )

    content = response["message"]["content"]

    chat_history.append({"role": "user", "content": query})
    chat_history.append({"role": "assistant", "content": content})

    # Keep the last 10 messages (10 user + 10 assistant = 20 total)
    if len(chat_history) > 20:
        chat_history = chat_history[-20:]

    return content

def query_knowledge_base(query: str) -> str:
    """Queries the local knowledge base for information. If no relevant info is found locally, it falls back to a web search."""
    query_embedding_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )
    query_embedding = query_embedding_response["embedding"]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )

    docs = results["documents"][0]
    distances = results.get("distances", [[999]])[0]
    best_distance = min(distances)

    print("=" * 50)
    print("[Live] Query:", query)
    print("[Live] Best Distance:", best_distance)
    print("[Live] Distances:", distances)
    print("=" * 50)

    use_kb = len(docs) > 0 and best_distance < SIMILARITY_THRESHOLD
    if use_kb:
        print(f"[RAG Live] Using Knowledge Base (distance={best_distance:.3f})")
        print(f"[RAG Live] Chunks loaded: {len(docs)}")
        for i, doc in enumerate(docs):
            print(f"[RAG Live] Chunk {i+1} Information: {doc}")
        return "\n".join(docs)
    else:
        print(f"[RAG Live] Falling back to SearXNG Web Search (distance={best_distance:.3f})")
        web_answer = search_web(query)
        if web_answer:
            return web_answer
        return "No relevant information found in the knowledge base or web search."