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

SIMILARITY_THRESHOLD = 320

chat_history = []

def ask_question(query, language="en"):
    print("=" * 60)
    print(f"[RAG] ask_question() called")
    print(f"[RAG]   Query: '{query}'")
    print(f"[RAG]   Language: '{language}'")
    print("=" * 60)

    # Step 1: Create embedding for user query
    print(f"[RAG]   Step 1/6: Generating query embedding with nomic-embed-text...")
    query_embedding_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )

    query_embedding = query_embedding_response["embedding"]
    print(f"[RAG]   ✅ Embedding generated (dimension: {len(query_embedding)})")

    # Step 2: Search vector database
    print(f"[RAG]   Step 2/6: Querying ChromaDB vector store...")
    print(f"[RAG]   Collection: 'knowledge_base' | n_results: 3")

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )

    docs = results["documents"][0]
    distances = results.get("distances", [[999]])[0]
    best_distance = min(distances)

    print(f"[RAG]   ChromaDB returned {len(docs)} document(s)")
    print(f"[RAG]   Best distance: {best_distance:.3f}")
    print(f"[RAG]   All distances: {[f'{d:.3f}' for d in distances]}")
    print(f"[RAG]   Similarity threshold: {SIMILARITY_THRESHOLD}")
    print("─" * 50)
    print("Query:", query)
    print("Language:", language)
    print("Best Distance:", best_distance)
    print("Distances:", distances)
    print("=" * 50)

    # Step 3: Decide whether to use KB or web
    use_kb = len(docs) > 0 and best_distance < SIMILARITY_THRESHOLD

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

        print(f"[RAG]   Step 3/6: Using Knowledge Base (distance={best_distance:.3f} < {SIMILARITY_THRESHOLD})")
        print(f"[RAG]   KB Context ({len(context)} chars):")
        for i, doc in enumerate(docs):
            print(f"[RAG]     Chunk {i+1}: {doc[:150]}...")

        prompt = f"""
You are a helpful AI assistant.

{language_instruction}

Answer ONLY using the provided context.

Context:
{context}

Question:
{query}
"""
    else:
        print(f"[RAG]   Step 3/6: KB similarity too low (distance={best_distance:.3f} >= {SIMILARITY_THRESHOLD})")
        print(f"[RAG]   Falling back to web search via SearXNG...")

        web_answer = search_web(query)

        context = web_answer if web_answer else "No information found."

        if web_answer:
            print(f"[RAG]   ✅ Web search successful ({len(web_answer)} chars of information)")
        else:
            print(f"[RAG]   ⚠️ Web search returned no results")

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

    # Step 4: Build conversation history
    print(f"[RAG]   Step 4/6: Building conversation context...")
    global chat_history
    print(f"[RAG]   Chat history entries: {len(chat_history)} (max 20)")

    messages = []
    for msg in chat_history:
        messages.append(msg)

    messages.append({
        "role": "user",
        "content": prompt
    })
    print(f"[RAG]   Total messages sent to LLM: {len(messages)}")

    # Step 5: Call Ollama LLM
    model_name = "alibayram/smollm3"
    print(f"[RAG]   Step 5/6: Calling Ollama model '{model_name}'...")
    print(f"[RAG]   Prompt length: {len(prompt)} chars")
    print(f"[RAG]   Waiting for LLM response...")

    response = ollama.chat(
        model=model_name,
        messages=messages,
        think=False
    )

    content = response["message"]["content"]
    print(f"[RAG]   ✅ LLM responded ({len(content)} chars)")
    print(f"[RAG]   Response preview: \"{content[:200]}...\"")
    print(f"[RAG]   Full response ({len(content.split())} words):")
    print(f"[RAG]   {content}")

    # Step 6: Update chat history
    print(f"[RAG]   Step 6/6: Updating chat history...")
    chat_history.append({"role": "user", "content": query})
    chat_history.append({"role": "assistant", "content": content})

    if len(chat_history) > 20:
        trimmed = len(chat_history) - 20
        chat_history = chat_history[-20:]
        print(f"[RAG]   Trimmed {trimmed} old messages to keep history at 20 entries")

    print(f"[RAG] ✅ ask_question() completed successfully")
    print("=" * 60)

    return content


def query_knowledge_base(query: str) -> str:
    """Queries the local knowledge base for information. If no relevant info is found locally, it falls back to a web search."""
    print("=" * 60)
    print(f"[KB] query_knowledge_base() called")
    print(f"[KB]   Query: '{query}'")
    print("=" * 60)

    print(f"[KB]   Step 1: Generating query embedding with nomic-embed-text...")
    query_embedding_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=query
    )
    query_embedding = query_embedding_response["embedding"]
    print(f"[KB]   ✅ Embedding generated (dimension: {len(query_embedding)})")

    print(f"[KB]   Step 2: Querying ChromaDB vector store...")
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )

    docs = results["documents"][0]
    distances = results.get("distances", [[999]])[0]
    best_distance = min(distances)

    print(f"[KB]   ChromaDB returned {len(docs)} document(s)")
    print(f"[KB]   Best distance: {best_distance:.3f}")
    print(f"[KB]   All distances: {[f'{d:.3f}' for d in distances]}")
    print(f"[KB]   Similarity threshold: {SIMILARITY_THRESHOLD}")
    print("─" * 50)
    print("[Live] Query:", query)
    print("[Live] Best Distance:", best_distance)
    print("[Live] Distances:", distances)
    print("=" * 50)

    use_kb = len(docs) > 0 and best_distance < SIMILARITY_THRESHOLD

    if use_kb:
        print(f"[KB]   ✅ Using Knowledge Base (distance={best_distance:.3f} < {SIMILARITY_THRESHOLD})")
        print(f"[KB]   Chunks loaded: {len(docs)}")
        for i, doc in enumerate(docs):
            print(f"[KB]   Chunk {i+1} Information: {doc[:200]}...")
        print(f"[KB] ✅ Returning {len(docs)} document(s)")
        print("=" * 60)
        return "\n".join(docs)
    else:
        print(f"[KB]   KB similarity too low (distance={best_distance:.3f} >= {SIMILARITY_THRESHOLD})")
        print(f"[KB]   Falling back to SearXNG Web Search...")
        web_answer = search_web(query)
        if web_answer:
            print(f"[KB]   ✅ Web search returned {len(web_answer)} chars of information")
            print(f"[KB]   Response: {web_answer[:200]}...")
            print("=" * 60)
            return web_answer
        print(f"[KB]   ⚠️ No results from KB or web search for query: '{query}'")
        print("=" * 60)
        return "No relevant information found in the knowledge base or web search."
