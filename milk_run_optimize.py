import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

st.set_page_config(page_title="Milk Run Optimizer", layout="wide")
st.title("Milk Run Optimizer")
st.markdown("ระบบจัดลำดับเส้นทาง Milk Run ด้วย Google OR-Tools")

# โหลดจาก Google Sheets
@st.cache_data
def load_sheet(sheet_gid, name):
    url = f"https://docs.google.com/spreadsheets/d/1IQ2T_v2y9z3KCsZ6ul3qQtGBKgnx3s0OtwRaDIuuUSc/export?format=csv&gid={sheet_gid}"
    try:
        df = pd.read_csv(url)
        st.success(f"✅ โหลด {name} สำเร็จ")
        return df
    except Exception as e:
        st.error(f"❌ โหลด {name} ล้มเหลว: {e}")
        return pd.DataFrame()

vendors = load_sheet(0, "Vendors")
routes = load_sheet(498856514, "Routes")

# แปลงพิกัดเป็น float
vendors["lat"] = vendors["lat"].astype(float)
vendors["lng"] = vendors["lng"].astype(float)

# ✅ เพิ่ม DIT ลงใน vendors
dit_row = pd.DataFrame([{
    "Ab.": "DIT",
    "lat": 13.4214134,
    "lng": 101.0101508
}])
vendors = pd.concat([dit_row, vendors], ignore_index=True)

# --- UI เลือกวันที่/รถ
routes["date"] = pd.to_datetime(routes["date"])
selected_date = st.date_input("เลือกวันที่", value=routes["date"].min())
selected_vehicle = st.selectbox("เลือกรถ", sorted(routes["vehicle_id"].unique()))

# --- กรองข้อมูลตามวันที่/รถ
filtered = routes[
    (routes["date"] == pd.to_datetime(selected_date)) &
    (routes["vehicle_id"] == selected_vehicle)
]

if filtered.empty:
    st.warning("ไม่มีข้อมูลในวัน/รถที่เลือก")
    st.stop()

# ✅ ดึงตัวย่อของ vendors ที่ต้องไปรับวันนี้
vendor_list = ["DIT"] + list(filtered["Ab."].unique()) + ["DIT"]
locations = {abbr: (vendors[vendors["Ab."] == abbr]["lat"].values[0],
                    vendors[vendors["Ab."] == abbr]["lng"].values[0])
             for abbr in vendor_list}

# --- คำนวณระยะห่างแบบ Euclidean
def compute_distance_matrix(loc_dict):
    keys = list(loc_dict.keys())
    size = len(keys)
    matrix = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            lat1, lng1 = loc_dict[keys[i]]
            lat2, lng2 = loc_dict[keys[j]]
            matrix[i][j] = np.sqrt((lat1 - lat2)**2 + (lng1 - lng2)**2)
    return matrix, keys

dist_matrix, keys = compute_distance_matrix(locations)

# --- ใช้ OR-Tools วางเส้นทาง
def solve_tsp(distance_matrix):
    size = len(distance_matrix)
    manager = pywrapcp.RoutingIndexManager(size, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(i, j):
        return int(distance_matrix[i][j] * 100000)

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        return None

    route = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        route.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    route.append(manager.IndexToNode(index))
    return route

route_indices = solve_tsp(dist_matrix)

# --- แสดงผล
if route_indices:
    st.subheader("🔁 ลำดับเส้นทางที่แนะนำ:")
    optimized = [keys[i] for i in route_indices]
    st.markdown(" ➡️ ".join(optimized))

    # --- แผนที่
    start_loc = locations[optimized[0]]
    route_map = folium.Map(location=start_loc, zoom_start=10)

    colors = ["blue", "green", "purple", "orange", "darkred"]

    # ปักหมุดทุกจุด
    for idx, abbr in enumerate(optimized):
        lat, lng = locations[abbr]
        popup = f"{abbr} ({idx+1})"
        color = "red" if abbr == "DIT" else colors[idx % len(colors)]
        folium.Marker(location=(lat, lng), popup=popup,
                      icon=folium.Icon(color=color)).add_to(route_map)

    # วาดเส้น
    latlngs = [locations[abbr] for abbr in optimized]
    folium.PolyLine(latlngs, color="blue", weight=4, opacity=0.7).add_to(route_map)

    st_folium(route_map, width=800, height=500)
else:
    st.error("❌ ไม่สามารถวางเส้นทางได้")
