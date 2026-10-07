import os
import subprocess
from pathlib import Path
import ast
import builtins
import pickle

import networkx as nx
from sentence_transformers import SentenceTransformer


def clone_repo(repo_url, destination="repos"):
    repo_name = repo_url.rstrip("/").split("/")[-1]
    repo_name = repo_name.removesuffix(".git")

    repo_path = os.path.join(destination, repo_name)

    if os.path.exists(repo_path):
        print("repo already exists")
        return repo_path

    subprocess.run(
        ["git", "clone", repo_url, repo_path],
        check=True
    )

    return repo_path


repo_url = input("Enter GitHub repository URL: ")
repo_path = clone_repo(
    repo_url,
    destination=r"C:\Users\DELL"
)

print(repo_path)


ignored_dirs = ["s3", ".dvc"]

ignored_files = [
    ".png",
    ".jpg",
    ".exe",
    ".dll",
    ".zip",
    ".pdf",
    ".dvcignore",
    ".gitignore",
    ".ipynb"
]

source_files = []
config_files = []
doc_files = []

SOURCE_EXTENSIONS = {".py"}

CONFIG_EXTENSIONS = {
    ".yaml",
    ".yml",
    ".toml",
    ".json"
}

DOC_EXTENSIONS = {".md"}

BUILTINS = set(dir(builtins))


for root, dirs, files in os.walk(repo_path):
    dirs[:] = [
        d for d in dirs
        if d not in ignored_dirs
    ]

    for f in files:
        if Path(f).suffix in ignored_files:
            continue

        extension = Path(f).suffix

        if extension in SOURCE_EXTENSIONS:
            source_files.append(
                os.path.join(root, f)
            )

        elif extension in CONFIG_EXTENSIONS:
            config_files.append(
                os.path.join(root, f)
            )

        elif extension in DOC_EXTENSIONS:
            doc_files.append(
                os.path.join(root, f)
            )

print(source_files)
nodes = []


for file in source_files:
    relpath = os.path.relpath(file, repo_path)

    with open(file, encoding="utf-8") as f:
        code = f.read()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        continue
        
    nodes.append({
        "id": relpath,
        "name": Path(file).name,
        "type": "file",
        "file": relpath
    })

    for node in tree.body:

        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            source_code = ast.get_source_segment(
                code,
                node
            )

            nodes.append({
                "id": f"{relpath}::{node.name}",
                "name": node.name,
                "type": "function",
                "file": relpath,
                "content": source_code
            })

        elif isinstance(node, ast.ClassDef):

            class_id = f"{relpath}::{node.name}"

            nodes.append({
                "id": class_id,
                "name": node.name,
                "type": "class",
                "file": relpath,
                "content": ast.get_source_segment(
                    code,
                    node
                )
            })

            for child in node.body:

                if isinstance(
                    child,
                    (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    source_code = ast.get_source_segment(
                        code,
                        child
                    )

                    nodes.append({
                        "id": (
                            f"{relpath}::"
                            f"{node.name}::"
                            f"{child.name}"
                        ),
                        "name": child.name,
                        "type": "method",
                        "file": relpath,
                        "class": node.name,
                        "content": source_code
                    })

        elif isinstance(node, ast.Import):

            for alias in node.names:
                nodes.append({
                    "id": (
                        f"{relpath}::import::"
                        f"{alias.name}"
                    ),
                    "name": alias.name,
                    "type": "import",
                    "file": relpath
                })

        elif isinstance(node, ast.ImportFrom):

            base_module = (
                node.module
                if node.module
                else "." * node.level
            )

            for alias in node.names:
                nodes.append({
                    "id": (
                        f"{relpath}::import::"
                        f"{base_module}.{alias.name}"
                    ),
                    "name": (
                        f"{base_module}.{alias.name}"
                    ),
                    "type": "import",
                    "file": relpath
                })


edges = []


for node in nodes:

    if node["type"] == "file":
        continue

    if node["type"] == "method":

        class_id = (
            f'{node["file"]}::'
            f'{node["class"]}'
        )

        edges.append({
            "source": class_id,
            "type": "CONTAINS",
            "target": node["id"]
        })

    else:

        edges.append({
            "source": node["file"],
            "type": "CONTAINS",
            "target": node["id"]
        })


function_lookup = {}
method_lookup = {}


for node in nodes:

    if node["type"] == "function":

        function_lookup[
            (node["file"], node["name"])
        ] = node["id"]

    elif node["type"] == "method":

        method_lookup[
            (
                node["file"],
                node["class"],
                node["name"]
            )
        ] = node["id"]

class_lookup = {}

for node in nodes:
    if node["type"] == "class":
        class_lookup[
            (node["file"], node["name"])
        ] = node["id"]
import_lookup = {}


for node in nodes:

    if node["type"] == "import":

        imported_name = (
            node["name"].split(".")[-1]
        )

        import_lookup[
            (node["file"], imported_name)
        ] = node["name"]


for file in source_files:

    with open(file, encoding="utf-8") as f:
        code = f.read()

    try:
            tree = ast.parse(code)
    except SyntaxError:
            continue

    relpath = os.path.relpath(
        file,
        repo_path
    )

    for node in tree.body:

        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):

            caller = f"{relpath}::{node.name}"
            object_types = {}

            for inner in ast.walk(node):

                if isinstance(inner, ast.Assign):

                    if (
                        isinstance(inner.value, ast.Call)
                        and
                        isinstance(
                            inner.value.func,
                            ast.Name
                        )
                    ):

                        class_name = inner.value.func.id

                        class_id = class_lookup.get(
                            (relpath, class_name)
                        )

                        if class_id:

                            for target in inner.targets:

                                if isinstance(
                                    target,
                                    ast.Name
                                ):
                                    object_types[
                                        target.id
                                    ] = class_id

                if not isinstance(
                    inner,
                    ast.Call
                ):
                    continue

                # function_name()
                if isinstance(
                    inner.func,
                    ast.Name
                ):

                    callee = inner.func.id

                    target = function_lookup.get(
                        (relpath, callee)
                    )

                    if target:

                        edges.append({
                            "source": caller,
                            "type": "CALLS",
                            "target": target
                        })

                        continue

                    if callee in BUILTINS:
                        continue

                    if (relpath, callee) in import_lookup:

                        imported_symbol = import_lookup[
                            (relpath, callee)
                        ]

                        parts = imported_symbol.rsplit(
                            ".",
                            1
                        )

                        if len(parts) != 2:
                            continue

                        module = parts[0]
                        function_name = parts[1]

                        module_path = (
                            module.replace(
                                ".",
                                os.sep
                            )
                            + ".py"
                        )

                        target = None

                        for graph_node in nodes:

                            if (
                                graph_node["type"] == "function"
                                and
                                graph_node["name"] == function_name
                                and
                                graph_node["file"].endswith(
                                    module_path
                                )
                            ):

                                target = graph_node["id"]
                                break

                        if target:

                            edges.append({
                                "source": caller,
                                "type": "CALLS",
                                "target": target
                            })

                # object.method()
                elif isinstance(
                    inner.func,
                    ast.Attribute
                ):

                    attribute = inner.func
                    receiver = attribute.value

                    if not isinstance(
                        receiver,
                        ast.Name
                    ):
                        continue

                    object_name = receiver.id
                    method_name = attribute.attr

                    # self.method()
                    if object_name == "self":
                        continue


                    # tts.speak()
                    class_id = object_types.get(
                        object_name
                    )

                    if not class_id:
                        continue

                    class_file, class_name = class_id.rsplit(
                        "::",
                        1
                    )

                    target = method_lookup.get(
                        (
                            class_file,
                            class_name,
                            method_name
                        )
                    )

                    if target:

                        edges.append({
                            "source": caller,
                            "type": "CALLS",
                            "target": target
                        })


        elif isinstance(node, ast.ClassDef):

            current_class = node.name

            for method_node in node.body:

                if not isinstance(
                    method_node,
                    (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    continue

                caller = (
                    f"{relpath}::"
                    f"{current_class}::"
                    f"{method_node.name}"
                )

                object_types = {}

                for inner in ast.walk(method_node):

                    # Detect:
                    # tts = Tts()
                    if isinstance(inner, ast.Assign):

                        if (
                            isinstance(inner.value, ast.Call)
                            and
                            isinstance(
                                inner.value.func,
                                ast.Name
                            )
                        ):

                            class_name = (
                                inner.value.func.id
                            )

                            class_id = class_lookup.get(
                                (
                                    relpath,
                                    class_name
                                )
                            )

                            if class_id:

                                for target in inner.targets:

                                    if isinstance(
                                        target,
                                        ast.Name
                                    ):

                                        object_types[
                                            target.id
                                        ] = class_id


                    if not isinstance(
                        inner,
                        ast.Call
                    ):
                        continue


                    # function_name()
                    if isinstance(
                        inner.func,
                        ast.Name
                    ):

                        callee = inner.func.id

                        # method_name() inside same class
                        target = method_lookup.get(
                            (
                                relpath,
                                current_class,
                                callee
                            )
                        )

                        if target:

                            edges.append({
                                "source": caller,
                                "type": "CALLS",
                                "target": target
                            })

                            continue


                        # top_level_function()
                        target = function_lookup.get(
                            (
                                relpath,
                                callee
                            )
                        )

                        if target:

                            edges.append({
                                "source": caller,
                                "type": "CALLS",
                                "target": target
                            })

                            continue


                        if callee in BUILTINS:
                            continue


                    # self.method()
                    # OR
                    # tts.speak()
                    elif isinstance(
                        inner.func,
                        ast.Attribute
                    ):

                        attribute = inner.func
                        receiver = attribute.value
                        method_name = attribute.attr


                        if not isinstance(
                            receiver,
                            ast.Name
                        ):
                            continue


                        object_name = receiver.id


                        # self.method()
                        if object_name == "self":

                            target = method_lookup.get(
                                (
                                    relpath,
                                    current_class,
                                    method_name
                                )
                            )

                            if target:

                                edges.append({
                                    "source": caller,
                                    "type": "CALLS",
                                    "target": target
                                })

                            continue


                        # tts.speak()
                        class_id = object_types.get(
                            object_name
                        )

                        if not class_id:
                            continue


                        class_file, class_name = (
                            class_id.rsplit(
                                "::",
                                1
                            )
                        )

                        target = method_lookup.get(
                            (
                                class_file,
                                class_name,
                                method_name
                            )
                        )

                        if target:

                            edges.append({
                                "source": caller,
                                "type": "CALLS",
                                "target": target
                            })
for file in source_files:
    with open(file, encoding="utf-8") as f:
        code = f.read()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        continue
    source = os.path.relpath(
        file,
        repo_path
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_id = (
                    f"{source}::import::{alias.name}"
                )

                edges.append({
                    "source": source,
                    "type": "IMPORTS",
                    "target": import_id
                })

        elif isinstance(node, ast.ImportFrom):
            base_module = (
                node.module
                if node.module
                else "." * node.level
            )
            for alias in node.names:
                import_name = (
                    f"{base_module}.{alias.name}"
                )
                import_id = (
                    f"{source}::import::{import_name}"
                )

                edges.append({
                    "source": source,
                    "type": "IMPORTS",
                    "target": import_id
                })


print("\n========== EDGES ==========")

for edge in edges:

    print(
        edge["source"],
        "--",
        edge["type"],
        "-->",
        edge["target"]
    )

node_ids = {node["id"] for node in nodes}

for edge in edges:
    if edge["target"] not in node_ids:
        print("MISSING NODE:", edge["target"], edge["type"])
G = nx.MultiDiGraph()


for node in nodes:

    G.add_node(
        node["id"],
        name=node["name"],
        type=node["type"],
        file=node["file"],
        content=node.get("content")
    )


for edge in edges:

    G.add_edge(
        edge["source"],
        edge["target"],
        type=edge["type"]
    )


print("Nodes:", G.number_of_nodes())
print("Edges:", G.number_of_edges())


embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)
embeddings = {}
for node in nodes:
    if node["type"] in {"function","class","method"}:
        if node.get("content"):
            embeddings[node["id"]] = embedding_model.encode(node["content"],batch_size = 4,show_progress_bar=True)
with open("graph.pkl","wb") as f:
    pickle.dump(G,f)
with open("embeddings.pkl","wb") as f:
    pickle.dump(embeddings,f)
print(f"Files: {len(source_files)}")
print(f"Nodes: {G.number_of_nodes()}")
print(f"Edges: {G.number_of_edges()}")
for n, d in G.nodes(data=True):
    if "type" not in d:
        print(n, d)