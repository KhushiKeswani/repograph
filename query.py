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
callers = []
callees = []

for path in paths:

    path_callers = [
        u
        for u, v, d in G.in_edges(path, data=True)
        if d["type"] == "CALLS"
    ]

    path_callees = [
        v
        for u, v, d in G.out_edges(path, data=True)
        if d["type"] == "CALLS"
    ]

    callers.extend(path_callers)
    callees.extend(path_callees)


# Remove duplicates
callers = list(set(callers))
callees = list(set(callees))
path_content = []
for path in paths:
    node_data = G.nodes[path]
    
    content = node_data.get("content")
    
    if content:
        path_content.append(content)
caller_content = []
for caller in callers:
    node_data = G.nodes[caller]
        
    content = node_data.get("content")
        
    if content:
        caller_content.append(content)
callee_content = []
for callee in callees:
    node_data = G.nodes[callee]
        
    content = node_data.get("content")
        
    if content:
        callee_content.append(content)
def format_chunk(node_id, G):
    node_data = G.nodes[node_id]
    content = node_data.get("content")
    if not content:
        return None
    return f"File: {node_data.get('file')}\nFunction: {node_data.get('name')}\n\n{content}"

path_content = [c for p in paths if (c := format_chunk(p, G))]
caller_content = [c for clr in callers if (c := format_chunk(clr, G))]
callee_content = [c for cle in callees if (c := format_chunk(cle, G))]
all_chunks = path_content + caller_content + callee_content
seen = set()
unique_chunks = []
for chunk in all_chunks:
    if chunk not in seen:
        seen.add(chunk)
        unique_chunks.append(chunk)

context = "\n\n---\n\n".join(unique_chunks)

print('context collected successfully')
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