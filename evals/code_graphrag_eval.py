import json
import pickle

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# -----------------------------
# Load
# -----------------------------

with open("evals/queries.json", "r") as f:
    queries = json.load(f)

with open("graph.pkl", "rb") as f:
    G = pickle.load(f)

with open("embeddings.pkl", "rb") as f:
    embeddings = pickle.load(f)

embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


# -----------------------------
# Semantic retrieval
# -----------------------------

def semantic_retrieve(question, k=5):

    query_embedding = embedding_model.encode(
        question
    )

    scores = []

    for node_id, vector in embeddings.items():

        score = cosine_similarity(
            [query_embedding],
            [vector]
        )[0][0]

        scores.append(
            (node_id, score)
        )

    scores.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return scores[:k]


# -----------------------------
# Graph expansion
# -----------------------------

def expand_graph(seeds, max_hops=2):

    visited = set(seeds)

    queue = [
        (node, 0)
        for node in seeds
    ]

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

            has_calls = any(
                data.get("type") == "CALLS"
                for data in edges.values()
            )

            if not has_calls:
                continue

            if neighbor not in visited:

                visited.add(neighbor)

                queue.append(
                    (neighbor, depth + 1)
                )

    return visited


# -----------------------------
# Relevant Context Recall
# -----------------------------

def context_recall(
    retrieved_nodes,
    relevant_nodes
):

    relevant_nodes = set(relevant_nodes)

    if not relevant_nodes:
        return 0

    found = (
        set(retrieved_nodes)
        & relevant_nodes
    )

    return len(found) / len(
        relevant_nodes
    )


# -----------------------------
# Cross-file Recall
# -----------------------------

def cross_file_recall(
    retrieved_nodes,
    relevant_nodes
):

    relevant_nodes = set(relevant_nodes)

    # Files containing relevant nodes
    relevant_files = {
        G.nodes[node].get("file")
        for node in relevant_nodes
        if node in G.nodes
    }

    # Files represented by retrieved nodes
    retrieved_files = {
        G.nodes[node].get("file")
        for node in retrieved_nodes
        if node in G.nodes
    }

    if not relevant_files:
        return 0

    return len(
        relevant_files & retrieved_files
    ) / len(relevant_files)


# -----------------------------
# Accumulators
# -----------------------------

semantic_context_scores = []
graph_context_scores = []

semantic_cross_file_scores = []
graph_cross_file_scores = []


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

    semantic_results = semantic_retrieve(
        question,
        k=5
    )

    semantic_nodes = [
        node_id
        for node_id, score
        in semantic_results
    ]

    # -------------------------
    # GraphRAG
    # -------------------------

    seeds = semantic_nodes[:3]

    graph_nodes = expand_graph(
        seeds,
        max_hops=2
    )

    # Keep semantic seeds + graph context
    graph_retrieved_nodes = (
        set(semantic_nodes)
        | graph_nodes
    )

    # -------------------------
    # Relevant context recall
    # -------------------------

    semantic_context_scores.append(
        context_recall(
            semantic_nodes,
            relevant_nodes
        )
    )

    graph_context_scores.append(
        context_recall(
            graph_retrieved_nodes,
            relevant_nodes
        )
    )

    # -------------------------
    # Cross-file recall
    # -------------------------

    semantic_cross_file_scores.append(
        cross_file_recall(
            semantic_nodes,
            relevant_nodes
        )
    )

    graph_cross_file_scores.append(
        cross_file_recall(
            graph_retrieved_nodes,
            relevant_nodes
        )
    )


# -----------------------------
# Results
# -----------------------------

def average(values):
    return sum(values) / len(values)


print("\n==============================")
print("Codebase RAG vs GraphRAG")
print("==============================")


print("\nRelevant Context Recall")

print(
    f"Semantic RAG: "
    f"{average(semantic_context_scores):.3f}"
)

print(
    f"GraphRAG:     "
    f"{average(graph_context_scores):.3f}"
)


print("\nCross-file Recall")

print(
    f"Semantic RAG: "
    f"{average(semantic_cross_file_scores):.3f}"
)

print(
    f"GraphRAG:     "
    f"{average(graph_cross_file_scores):.3f}"
)