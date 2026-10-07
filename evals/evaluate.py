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

        similarities.append((node_id, score))

    similarities.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return similarities


# -----------------------------
# Metrics
# -----------------------------

def recall_at_k(results, relevant_nodes, k):
    top_k = {node_id for node_id, _ in results[:k]}

    return int(bool(top_k & relevant_nodes))


def reciprocal_rank(results, relevant_nodes):
    for rank, (node_id, _) in enumerate(results, start=1):
        if node_id in relevant_nodes:
            return 1 / rank

    return 0


# -----------------------------
# Evaluation
# -----------------------------

recall_1 = []
recall_3 = []
recall_5 = []
recall_10 = []
mrr_scores = []


for item in queries:

    question = item["query"]
    relevant_nodes = set(item["relevant_nodes"])

    # Full semantic ranking
    similarities = retrieve(question)

    # Same top-3 seeds as your actual query.py
    semantic_seeds = [
        node_id
        for node_id, score in similarities[:3]
    ]

    # -------------------------
    # Graph expansion
    # -------------------------

    expanded_nodes = set()

    for seed in semantic_seeds:
        expanded_nodes.update(
            get_2hop_nodes(
                G,
                seed,
                max_hops=2
            )
        )

    # -------------------------
    # Rank expanded nodes
    # using semantic score
    # -------------------------

    similarity_dict = dict(similarities)

    graph_results = [
        (node_id, similarity_dict[node_id])
        for node_id in expanded_nodes
        if node_id in similarity_dict
    ]

    graph_results.sort(
        key=lambda x: x[1],
        reverse=True
    )

    # -------------------------
    # Metrics
    # -------------------------

    recall_1.append(
        recall_at_k(
            graph_results,
            relevant_nodes,
            1
        )
    )

    recall_3.append(
        recall_at_k(
            graph_results,
            relevant_nodes,
            3
        )
    )

    recall_5.append(
        recall_at_k(
            graph_results,
            relevant_nodes,
            5
        )
    )

    recall_10.append(
        recall_at_k(
            graph_results,
            relevant_nodes,
            10
        )
    )

    mrr_scores.append(
        reciprocal_rank(
            graph_results,
            relevant_nodes
        )
    )


# -----------------------------
# Final results
# -----------------------------

print("\n==============================")
print("GraphRAG Evaluation")
print("==============================")

print(
    f"Recall@1:  "
    f"{sum(recall_1) / len(recall_1):.3f}"
)

print(
    f"Recall@3:  "
    f"{sum(recall_3) / len(recall_3):.3f}"
)

print(
    f"Recall@5:  "
    f"{sum(recall_5) / len(recall_5):.3f}"
)

print(
    f"Recall@10: "
    f"{sum(recall_10) / len(recall_10):.3f}"
)

print(
    f"MRR:       "
    f"{sum(mrr_scores) / len(mrr_scores):.3f}"
)