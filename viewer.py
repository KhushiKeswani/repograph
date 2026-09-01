import networkx as nx
from pyvis.network import Network
import pickle
with open("graph.pkl", "rb") as f:
    G = pickle.load(f)
print("Loaded graph OK")
print("Nodes:", G.number_of_nodes())
print("Edges:", G.number_of_edges())
# FUNCTION: GET GRAPH FOR ONE FILE
def get_file_graph(G, selected_file):

    H = nx.MultiDiGraph()
    # Add the selected FILE node
    for node, data in G.nodes(data=True):

        if (
            data["type"] == "file"
            and data["file"] == selected_file
        ):

            H.add_node(
                node,
                **data
            )
    # Add FUNCTIONS and CLASSES belonging to this file
    for node, data in G.nodes(data=True):

        if (
            data["file"] == selected_file
            and data["type"] in {"function", "class","external"}
        ):

            H.add_node(
                node,
                **data
            )
    # 3. ADD EDGES FROM SELECTED FILE
    for source, target, data in G.edges(data=True):

        edge_type = data.get("type")

        # We only care about these relationships
        if edge_type not in {
            "CONTAINS",
            "CALLS",
            "CALLS_UNRESOLVED"
        }:
            continue
        # Is the SOURCE inside our selected file?
        if source not in H.nodes:
            continue
        # Normal target
        if target in G.nodes:
            target_data = G.nodes[target]
            # If target is already in H, simply add edge
            if target in H.nodes:

                H.add_edge(
                    source,
                    target,
                    **data
                )
            # External / unresolved target
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

# SHOW AVAILABLE FILES
print("\nAVAILABLE FILES\n ")

file_nodes = [
    (node, data)
    for node, data in G.nodes(data=True)
    if data.get("type") == "file"
]

for i, (node, data) in enumerate(file_nodes):

    print(
        f"{i + 1}. {data['file']}"
    )
# SELECT FILE
choice = int(
    input("\nSelect a file number: ")
)

selected_file = file_nodes[choice - 1][1]["file"]

print(
    "\nSelected file:",
    selected_file
)

# BUILD VISUALIZATION GRAPH
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
# CREATE PYVIS NETWORK
net = Network(
    height="800px",
    width="100%",
    bgcolor="#1e1e1e",
    font_color="white",
    directed=True,
    notebook=False
)

# VISUAL SETTINGS
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
# ADD NODES TO PYVIS
for node, data in H.nodes(data=True):

    node_type = data.get(
        "type",
        "function"
    )
    label = data["name"]
    # Add node
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
# ADD EDGES TO PYVIS
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
# HIERARCHICAL LAYOUT
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
# WRITE HTML
net.write_html(
    "codebase_graph.html",
    open_browser=True
)

print(
    "\nGraph written to codebase_graph.html"
)