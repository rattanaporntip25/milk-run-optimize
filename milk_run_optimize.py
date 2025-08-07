import streamlit as st
import numpy as np
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

st.set_page_config(page_title="Milk Run Optimizer", layout="wide")
st.title("Milk Run Optimizer")
st.markdown("🚛 คำนวณเส้นทางขนส่งที่สั้นที่สุดด้วย Google OR-Tools")

# -----------------------------
# ข้อมูลจุด (DIT และเวนเดอร์)
# -----------------------------
locations = {
    "DIT": (13.4214, 101.0101),
    "VND1": (13.5000, 100.9000),
    "VND2": (13.6000, 101.2000),
    "VND3": (13.4500, 100.8000),
}

# -----------------------------
# สร้าง Distance Matrix
# -----------------------------
def compute_distance_matrix(loc_dict):
    keys = list(loc_dict.keys())
    size = len(keys)
    matrix = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            if i != j:
                lat1, lon1 = loc_dict[keys[i]]
                lat2, lon2 = loc_dict[keys[j]]
                matrix[i][j] = np.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)
    return matrix, keys

distance_matrix, location_keys = compute_distance_matrix(locations)

# -----------------------------
# ใช้ OR-Tools หาเส้นทาง
# -----------------------------
manager = pywrapcp.RoutingIndexManager(len(distance_matrix), 1, 0)
routing = pywrapcp.RoutingModel(manager)

def distance_callback(from_idx, to_idx):
    from_node = manager.IndexToNode(from_idx)
    to_node = manager.IndexToNode(to_idx)
    return int(distance_matrix[from_node][to_node] * 100000)  # scale

transit_index = routing.RegisterTransitCallback(distance_callback)
routing.SetArcCostEvaluatorOfAllVehicles(transit_index)

params = pywrapcp.DefaultRoutingSearchParameters()
params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

solution = routing.SolveWithParameters(params)

# -----------------------------
# แสดงผลลัพธ์บน Streamlit
# -----------------------------
if solution:
    route_idx = routing.Start(0)
    optimized_route = []
    while not routing.IsEnd(route_idx):
        node_index = manager.IndexToNode(route_idx)
        optimized_route.append(location_keys[node_index])
        route_idx = solution.Value(routing.NextVar(route_idx))
    optimized_route.append(location_keys[manager.IndexToNode(route_idx)])

    st.success("✔️ เส้นทางที่สั้นที่สุด:")
    st.write(" ➜ ".join(optimized_route))

    # แสดงแผนที่
    route_map = folium.Map(location=locations["DIT"], zoom_start=9)
    coords = [locations[loc] for loc in optimized_route]

    for i, loc in enumerate(optimized_route):
        lat, lng = locations[loc]
        icon_color = "blue" if loc != "DIT" else "green"
        popup = f"{i+1}. {loc}"
        folium.Marker(location=(lat, lng), popup=popup,
                      icon=folium.Icon(color=icon_color)).add_to(route_map)

    folium.PolyLine(coords, color="red", weight=3, opacity=0.8).add_to(route_map)

    st_data = st_folium(route_map, width=800, height=500)
else:
    st.error("ไม่พบเส้นทางที่เหมาะสม 😢")
