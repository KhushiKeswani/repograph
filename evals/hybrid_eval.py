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
# Metrics
# -----------------------------

def recall_at_k(results, relevant_nodes, k):

    top_k = {
        node_id
        for node_id, _ in results[:k]
    }

    return int(
        bool(top_k & relevant_nodes)
    )


def precision_at_k(results, relevant_nodes, k):

    top_k = [
        node_id
        for node_id, _ in results[:k]
    ]

    relevant_count = sum(
        node_id in relevant_nodes
        for node_id in top_k
    )

    return relevant_count / k


def reciprocal_rank(results, relevant_nodes):

    for rank, (node_id, _) in enumerate(
        results,
        start=1
    ):

        if node_id in relevant_nodes:
            return 1 / rank

    return 0


# -----------------------------
# Result storage
# -----------------------------

recall = {
    1: [],
    3: [],
    5: [],
    10: []
}

precision = {
    1: [],
    3: [],
    5: [],
    10: []
}

mrr = []


# -----------------------------
# Evaluation
# -----------------------------

for item in queries:

    question = item["query"]

    relevant_nodes = set(
        item["relevant_nodes"]
    )

    # -------------------------
    # Semantic retrieval
    # -------------------------

    similarities = retrieve(question)

    similarity_dict = dict(similarities)

    semantic_seeds = [
        node_id
        for node_id, score in similarities[:3]
    ]


    # -------------------------
    # Graph retrieval
    # -------------------------

    graph_nodes = set()

    for seed in semantic_seeds:

        graph_nodes.update(
            get_2hop_nodes(
                G,
                seed,
                max_hops=2
            )
        )


    # -------------------------
    # Hybrid candidate pool
    # -------------------------

    hybrid_nodes = set(
        semantic_seeds
    )

    hybrid_nodes.update(
        graph_nodes
    )


    # -------------------------
    # Rank hybrid candidates
    # by semantic similarity
    # -------------------------

    hybrid_results = [
        (
            node_id,
            similarity_dict[node_id]
        )
        for node_id in hybrid_nodes
        if node_id in similarity_dict
    ]

    hybrid_results.sort(
        key=lambda x: x[1],
        reverse=True
    )


    # -------------------------
    # Metrics
    # -------------------------

    for k in [1, 3, 5, 10]:

        recall[k].append(
            recall_at_k(
                hybrid_results,
                relevant_nodes,
                k
            )
        )

        precision[k].append(
            precision_at_k(
                hybrid_results,
                relevant_nodes,
                k
            )
        )

    mrr.append(
        reciprocal_rank(
            hybrid_results,
            relevant_nodes
        )
    )


# -----------------------------
# Final results
# -----------------------------

print("\n==============================")
print("Hybrid RepoGraph Evaluation")
print("==============================")


print("\nRecall")

for k in [1, 3, 5, 10]:

    score = (
        sum(recall[k])
        / len(recall[k])
    )

    print(
        f"Recall@{k}: {score:.3f}"
    )


print("\nPrecision")

for k in [1, 3, 5, 10]:

    score = (
        sum(precision[k])
        / len(precision[k])
    )

    print(
        f"Precision@{k}: {score:.3f}"
    )


print(
    f"\nMRR: "
    f"{sum(mrr) / len(mrr):.3f}"
)