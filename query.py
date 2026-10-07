import pickle
from sklearn.metrics.pairwise import cosine_similarity
import os
from dotenv import load_dotenv
import requests

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
with open("graph.pkl", "rb") as f:
    G = pickle.load(f)
with open("embeddings.pkl","rb") as f:
    embeddings = pickle.load(f)
from sentence_transformers import SentenceTransformer
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
def get_2hop_nodes(G, start_node, max_hops=2):
    visited = {start_node}
    queue = [(start_node, 0)]

    while queue:
        node, depth = queue.pop(0)

        if depth == max_hops:
            continue

        for neighbor in G.successors(node):
            # Only follow CALLS edges
            edges = G.get_edge_data(node, neighbor, default={})

            has_calls_edge = any(
                edge_data.get("type") == "CALLS"
                for edge_data in edges.values()
            )

            if not has_calls_edge:
                continue

            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

    return visited
user_question = input("ask a question: ")
embedded_question = embedding_model.encode(user_question)
similarities = []
for node_id, vector in embeddings.items():

    score = cosine_similarity(
        [embedded_question],
        [vector]
    )[0][0]

    similarities.append(
        (node_id, score)
    )
similarities.sort(
    key=lambda x: x[1],
    reverse=True
)
top_results = similarities[:3]
paths = [item[0] for item in top_results]
expanded_nodes = set()

for path in paths:
    expanded_nodes.update(
        get_2hop_nodes(G, path, max_hops=2)
    )

expanded_nodes.discard(None)

def format_chunk(node_id, G):
    node_data = G.nodes[node_id]
    content = node_data.get("content")
    if not content:
        return None
    return f"File: {node_data.get('file')}\nFunction: {node_data.get('name')}\n\n{content}"
all_chunks = []

for node_id in expanded_nodes:
    chunk = format_chunk(node_id, G)

    if chunk:
        all_chunks.append(chunk)

context = "\n\n---\n\n".join(all_chunks)

print('content collected successfully')
prompt = f"""
You are a code assistant.

Answer the user's question using the provided code context.
If the answer cannot be found in the provided code context, say that you cannot determine it from the code
CODE CONTEXT:
{context}

USER QUESTION:
{user_question}
"""
url = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": "nvidia/nemotron-3.5-lightning:free",
    "messages": [
        {
            "role": "user",
            "content": prompt
        }
    ]
}

response = requests.post(
    url,
    headers=headers,
    json=payload
)

data = response.json()

print(data["choices"][0]["message"]["content"])
print("Semantic seeds:", paths)
print("Expanded nodes:", expanded_nodes)