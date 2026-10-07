import json
import pickle

from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer


# -----------------------------
# Load data
# -----------------------------

with open("evals/queries.json", "r") as f:
    queries = json.load(f)

with open("graph.pkl", "rb") as f:
    G = pickle.load(f)

with open("embeddings.pkl", "rb") as f:
    embeddings = pickle.load(f)

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


# -----------------------------
# 2-hop CALLS expansion
# -----------------------------

def get_2hop_nodes(G, start_node, max_hops=2):
    visited = {start_node}
    queue = [(start_node, 0)]

    while queue:
        node, depth = queue.pop(0)

        if depth == max_hops:
            continue

        for neighbor in G.successors(node):

            edges = G.get_edge_data(
                node,
                neighbor,
                default={}
            )

            has_calls_edge = any(
                edge_data.get("type") == "CALLS"
                for edge_data in edges.values()
            )

            if not has_calls_edge:
                continue

            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(
                    (neighbor, depth + 1)
                )

    return visited


# -----------------------------
# Semantic retrieval
# -----------------------------

def retrieve(query):
    query_embedding = embedding_model.encode(query)

    similarities = []

    for node_id, vector in embeddings.items():

        score = cosine_similarity(
            [query_embedding],
            [vector]
        )[0][0]

        similarities.append(
            (node_id, score)
        )

    similarities.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return similarities


# -----------------------------
# Precision
# -----------------------------

def precision_at_k(results, relevant_nodes, k):

    top_k = [
        node_id
        for node_id, score in results[:k]
    ]

    relevant_count = sum(
        node_id in relevant_nodes
        for node_id in top_k
    )

    return relevant_count / k


# -----------------------------
# Store results
# -----------------------------

semantic_precision = {
    1: [],
    3: [],
    5: [],
    10: []
}

graph_precision = {
    1: [],
    3: [],
    5: [],
    10: []
}


# -----------------------------
# Evaluation
# -----------------------------

for item in queries:

    question = item["query"]

    relevant_nodes = set(
        item["relevant_nodes"]
    )

    # -------------------------
    # Semantic RAG
    # -------------------------

    similarities = retrieve(question)

    semantic_results = similarities


    # -------------------------
    # GraphRAG
    # -------------------------

    semantic_seeds = [
        node_id
        for node_id, score in similarities[:3]
    ]

    expanded_nodes = set()

    for seed in semantic_seeds:

        expanded_nodes.update(
            get_2hop_nodes(
                G,
                seed,
                max_hops=2
            )
        )

    similarity_dict = dict(similarities)

    graph_results = [
        (
            node_id,
            similarity_dict[node_id]
        )
        for node_id in expanded_nodes
        if node_id in similarity_dict
    ]

    graph_results.sort(
        key=lambda x: x[1],
        reverse=True
    )


    # -------------------------
    # Precision @ K
    # -------------------------

    for k in [1, 3, 5, 10]:

        semantic_precision[k].append(
            precision_at_k(
                semantic_results,
                relevant_nodes,
                k
            )
        )

        graph_precision[k].append(
            precision_at_k(
                graph_results,
                relevant_nodes,
                k
            )
        )


# -----------------------------
# Final results
# -----------------------------

print("\n==============================")
print("Precision Evaluation")
print("==============================")

print("\nSemantic RAG")

for k in [1, 3, 5, 10]:

    score = (
        sum(semantic_precision[k])
        / len(semantic_precision[k])
    )

    print(
        f"Precision@{k}: {score:.3f}"
    )


print("\nGraphRAG")

for k in [1, 3, 5, 10]:

    score = (
        sum(graph_precision[k])
        / len(graph_precision[k])
    )

    print(
        f"Precision@{k}: {score:.3f}"
    )