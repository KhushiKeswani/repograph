
import os
import subprocess
from pathlib import Path
import ast
import builtins
def clone_repo(repo_url, destination='repos'):
    repo_name = repo_url.rstrip("/").split("/")[-1]
    repo_name = repo_name.removesuffix(".git")

    repo_path = os.path.join(destination, repo_name)
    if os.path.exists(repo_path):
        print('repo already exists')
        return repo_path

    subprocess.run(
        ["git", "clone", repo_url, repo_path],
        check=True
    )

    return repo_path


repo_url = input("Enter GitHub repository URL: ")
repo_path = clone_repo(repo_url, destination=r'C:\Users\DELL')

print(repo_path)


ignored_dirs = ['s3', '.dvc']

ignored_files = [
    '.png',
    '.jpg',
    '.exe',
    '.dll',
    '.zip',
    '.pdf',
    '.dvcignore',
    '.gitignore',
    '.ipynb'
]

source_files = []
config_files = []
doc_files = []

SOURCE_EXTENSIONS = {
    ".py"
}

CONFIG_EXTENSIONS = {
    ".yaml",
    ".yml",
    ".toml",
    ".json"
}

DOC_EXTENSIONS = {
    ".md"
}

BUILTINS = set(dir(builtins))
for root, dirs, files in os.walk(repo_path):

    dirs[:] = [
        d for d in dirs
        if d not in ignored_dirs
    ]

    for f in files:

        if Path(f).suffix not in ignored_files:

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


print(config_files)
print(source_files)
print(doc_files)


# ============================================================
# AST ENTITY EXTRACTION
# ============================================================

nodes = []


for file in source_files:
    relpath = os.path.relpath(file,repo_path)
    with open(file, encoding="utf-8") as f:
        code = f.read()

    tree = ast.parse(code)

    # --------------------------------------------------------
    # FILE NODE
    # --------------------------------------------------------
    
    nodes.append({
        "id": relpath,
        "name": Path(file).name,
        "type": "file",
        "file": relpath
    })

    # --------------------------------------------------------
    # OTHER ENTITIES
    # --------------------------------------------------------

    for node in ast.walk(tree):

        if isinstance(node, ast.FunctionDef):
            source_code = ast.get_source_segment(code, node)
            nodes.append({
                "id": f"{relpath}::{node.name}",
                "name": node.name,
                "type": "function",
                "file": relpath,
                "content": source_code
            })

        elif isinstance(node, ast.ClassDef):
            source_code = ast.get_source_segment(code, node)
            nodes.append({
                "id": f"{relpath}::{node.name}",
                "name": node.name,
                "type": "class",
                "file": relpath,
                "content" : source_code
            })

        elif isinstance(node, ast.Import):

            for alias in node.names:

                nodes.append({
                    "id": f"{relpath}::import::{alias.name}",
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
                    "id": f"{relpath}::import::{base_module}.{alias.name}",
                    "name": f"{base_module}.{alias.name}",
                    "type": "import",
                    "file": relpath
                })


# ============================================================
# DISPLAY NODES
# ============================================================

print("\n================ NODES ================\n")

for node in nodes:

    print(
        f"{node['type'].upper():10} "
        f"{node['name']} "
        f"-> {node['file']}"
    )
    if node.get("content"):
        print(node["content"])
# ============================================================
# BUILD CONTAINS EDGES
# ============================================================

edges = []

for node in nodes:

    # File contains functions/classes/imports
    if node["type"] == "file":
        continue

    edges.append({
        "source": node["file"],
        "type": "CONTAINS",
        "target": node["id"]
    })


# ============================================================
# FUNCTION LOOKUP
# ============================================================

function_lookup = {}

for node in nodes:

    if node["type"] == "function":

        function_lookup[
            (node["file"], node["name"])
        ] = node["id"]


# ============================================================
# IMPORT LOOKUP
# ============================================================

import_lookup = {}

for node in nodes:

    if node["type"] == "import":

        imported_name = node["name"].split(".")[-1]

        import_lookup[
            (node["file"], imported_name)
        ] = node["name"]


# ============================================================
# FIND FUNCTION CALLS
# ============================================================

for file in source_files:

    with open(file, encoding="utf-8") as f:
        code = f.read()

    tree = ast.parse(code)

    relpath = os.path.relpath(file, repo_path)

    for node in ast.walk(tree):

        # ----------------------------------------------------
        # Find a function definition
        # ----------------------------------------------------

        if isinstance(node, ast.FunctionDef):

            caller = f"{relpath}::{node.name}"

            # Look inside this function
            for inner in ast.walk(node):

                # ------------------------------------------------
                # Find function calls
                # ------------------------------------------------

                if isinstance(inner, ast.Call):

                    # We currently handle:
                    # load_data()
                    if isinstance(inner.func, ast.Name):

                        callee = inner.func.id

                        # ==================================================
                        # 1. CHECK LOCAL FUNCTION
                        # ==================================================

                        local_target = function_lookup.get(
                            (relpath, callee)
                        )

                        if local_target:

                            edges.append({
                                "source": caller,
                                "type": "CALLS",
                                "target": local_target
                            })
                        elif callee in BUILTINS:

                            # Ignore things like:
                            # open(), float(), len(), print(), etc.

                            continue
                        # ==================================================
                        # 2. CHECK IMPORTED FUNCTION
                        # ==================================================

                        elif (relpath, callee) in import_lookup:

                            imported_symbol = import_lookup[
                                (relpath, callee)
                            ]

                            # Example:
                            #
                            # sklearn.metrics.mean_squared_error
                            #
                            # module =
                            # sklearn.metrics
                            #
                            # function_name =
                            # mean_squared_error

                            parts = imported_symbol.rsplit(".", 1)

                            module = parts[0]
                            function_name = parts[1]

                            module_path = (
                                module.replace(".", os.sep)
                                + ".py"
                            )

                            target = None

                            # Search for the actual function
                            # in our extracted nodes
                            for graph_node in nodes:

                                if (
                                    graph_node["type"] == "function"
                                    and graph_node["name"] == function_name
                                    and graph_node["file"].endswith(
                                        module_path
                                    )
                                ):

                                    target = graph_node["id"]
                                    break

                            # ------------------------------------------------
                            # Imported function successfully resolved
                            # ------------------------------------------------

                            if target:

                                edges.append({
                                    "source": caller,
                                    "type": "CALLS",
                                    "target": target
                                })

                            # ------------------------------------------------
                            # Imported name found but actual function
                            # could not be found
                            # ------------------------------------------------

                            else:

                                unresolved_id = (
                                    f"external::{callee}"
                                )

                                # Create external node only once
                                if not any(
                                    n["id"] == unresolved_id
                                    for n in nodes
                                ):

                                    nodes.append({
                                        "id": unresolved_id,
                                        "name": callee,
                                        "type": "external",
                                        "file": "external"
                                    })

                                edges.append({
                                    "source": caller,
                                    "type": "CALLS_UNRESOLVED",
                                    "target": unresolved_id
                                })

                        # ==================================================
                        # 3. NOT LOCAL AND NOT IMPORTED
                        # ==================================================

                        else:

                            unresolved_id = (
                                f"external::{callee}"
                            )

                            # Create external node only once
                            if not any(
                                n["id"] == unresolved_id
                                for n in nodes
                            ):

                                nodes.append({
                                    "id": unresolved_id,
                                    "name": callee,
                                    "type": "external",
                                    "file": "external"
                                })

                            edges.append({
                                "source": caller,
                                "type": "CALLS_UNRESOLVED",
                                "target": unresolved_id
                            })
       
for file in source_files:

    with open(file, encoding="utf-8") as f:
        code = f.read()

    tree = ast.parse(code)

    source = os.path.relpath(file, repo_path)

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:

                import_id = f"{source}::import::{alias.name}"

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

                import_name = f"{base_module}.{alias.name}"

                import_id = f"{source}::import::{import_name}"

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
import networkx as nx
from pyvis.network import Network

# ============================================================
# BUILD THE FULL GRAPH (backend — used for retrieval later too)
# ============================================================

# ============================================================
# BUILD NETWORKX GRAPH
# ============================================================

G = nx.MultiDiGraph()

# Add nodes
for node in nodes:
    G.add_node(
        node["id"],
        name=node["name"],
        type=node["type"],
        file=node["file"]
    )

# Add edges
for edge in edges:
    G.add_edge(
        edge["source"],
        edge["target"],
        type=edge["type"]
    )

print("\n================ GRAPH ================\n")

print("Nodes:", G.number_of_nodes())
print("Edges:", G.number_of_edges())


# ============================================================
# FUNCTION: GET GRAPH FOR ONE FILE
# ============================================================

def get_file_graph(G, selected_file):

    H = nx.MultiDiGraph()

    # --------------------------------------------------------
    # Add the selected FILE node
    # --------------------------------------------------------

    for node, data in G.nodes(data=True):

        if (
            data["type"] == "file"
            and data["file"] == selected_file
        ):

            H.add_node(
                node,
                **data
            )

    # --------------------------------------------------------
    # Add FUNCTIONS and CLASSES belonging to this file
    # --------------------------------------------------------

    for node, data in G.nodes(data=True):

        if (
            data["file"] == selected_file
            and data["type"] in {"function", "class","external"}
        ):

            H.add_node(
                node,
                **data
            )

    # ========================================================
    # 3. ADD EDGES FROM SELECTED FILE
    # ========================================================

    for source, target, data in G.edges(data=True):

        edge_type = data.get("type")

        # We only care about these relationships
        if edge_type not in {
            "CONTAINS",
            "CALLS",
            "CALLS_UNRESOLVED"
        }:
            continue

        # ----------------------------------------------------
        # Is the SOURCE inside our selected file?
        # ----------------------------------------------------

        if source not in H.nodes:
            continue

        # ----------------------------------------------------
        # Normal target
        # ----------------------------------------------------

        if target in G.nodes:

            target_data = G.nodes[target]

            # If target is already in H, simply add edge
            if target in H.nodes:

                H.add_edge(
                    source,
                    target,
                    **data
                )

            # ------------------------------------------------
            # External / unresolved target
            # ------------------------------------------------

            elif target_data.get("type") == "external":

                H.add_node(
                    target,
                    **target_data
                )

                H.add_edge(
                    source,
                    target,
                    **data
                )

    return H

# ============================================================
# SHOW AVAILABLE FILES
# ============================================================

print("\n================ AVAILABLE FILES ================\n")

file_nodes = [
    (node, data)
    for node, data in G.nodes(data=True)
    if data.get("type") == "file"
]

for i, (node, data) in enumerate(file_nodes):

    print(
        f"{i + 1}. {data['file']}"
    )


# ============================================================
# SELECT FILE
# ============================================================

choice = int(
    input("\nSelect a file number: ")
)

selected_file = file_nodes[choice - 1][1]["file"]

print(
    "\nSelected file:",
    selected_file
)


# ============================================================
# BUILD VISUALIZATION GRAPH
# ============================================================

H = get_file_graph(
    G,
    selected_file
)

print(
    "Visualized nodes:",
    H.number_of_nodes()
)

print(
    "Visualized edges:",
    H.number_of_edges()
)


# ============================================================
# CREATE PYVIS NETWORK
# ============================================================

net = Network(
    height="800px",
    width="100%",
    bgcolor="#1e1e1e",
    font_color="white",
    directed=True,
    notebook=False
)


# ============================================================
# VISUAL SETTINGS
# ============================================================

color_map = {
    "file": "#4a90d9",
    "function": "#7ed321",
    "class": "#f5a623"
}

shape_map = {
    "file": "box",
    "function": "dot",
    "class": "dot"
}

size_map = {
    "file": 30,
    "function": 15,
    "class": 20
}


# ============================================================
# ADD NODES TO PYVIS
# ============================================================

for node, data in H.nodes(data=True):

    node_type = data.get(
        "type",
        "function"
    )

    # --------------------------------------------------------
    # Label
    # --------------------------------------------------------
    label = data["name"]

    # --------------------------------------------------------
    # Add node
    # --------------------------------------------------------

    net.add_node(
        node,
        label=label,

        color=color_map.get(
            node_type,
            "#999999"
        ),

        shape=shape_map.get(
            node_type,
            "dot"
        ),

        size=size_map.get(
            node_type,
            15
        ),

        title=(
            f"{node_type}: "
            f"{data['name']} "
            f"— {data['file']}"
        )
    )


# ============================================================
# ADD EDGES TO PYVIS
# ============================================================

for source, target, data in H.edges(data=True):

    edge_type = data["type"]

    # CALLS = red
    # CONTAINS = gray

    if edge_type == "CALLS":

        edge_color = "#c0392b"

    else:

        edge_color = "#666666"

    net.add_edge(
        source,
        target,

        color=edge_color,

        title=edge_type,

        arrows="to"
    )


# ============================================================
# HIERARCHICAL LAYOUT
# ============================================================

net.set_options("""
{
    "interaction": {
        "hover": true,
        "selectConnectedEdges": true,
        "hoverConnectedEdges": true,
        "navigationButtons": true,
        "zoomView": true,
        "dragView": true
    },

    "physics": {
        "enabled": true,
        "hierarchicalRepulsion": {
            "nodeDistance": 150,
            "centralGravity": 0.0,
            "springLength": 150,
            "springConstant": 0.01,
            "damping": 0.09
        },

        "solver": "hierarchicalRepulsion"
    },

    "layout": {
        "hierarchical": {
            "enabled": true,
            "direction": "UD",
            "sortMethod": "directed",
            "nodeSpacing": 150,
            "levelSeparation": 180
        }
    },

    "nodes": {
        "font": {
            "size": 18
        }
    },

    "edges": {
        "smooth": {
            "enabled": true,
            "type": "cubicBezier",
            "forceDirection": "vertical",
            "roundness": 0.4
        },

        "arrows": {
            "to": {
                "enabled": true,
                "scaleFactor": 0.7
            }
        }
    }
}
""")


# ============================================================
# WRITE HTML
# ============================================================

net.write_html(
    "codebase_graph.html",
    open_browser=True
)

print(
    "\nGraph written to codebase_graph.html"
)