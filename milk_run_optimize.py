import streamlit as st
import pandas as pd
import numpy as np
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="Milk Run Optimizer", layout="wide")
st.title("Milk Run Route Optimizer")
st.markdown("สร้างเส้นทางที่เหมาะสมจากข้อมูล Google Sheets")

# -------------------------------
# ฟังก์ชันโหลด Google Sheet
# -------------------------------
@st.cache_data
def load_sheet(sheet_gid, name):
    url = f"https://docs.google.com/spreadsheets/d/1IQ2T_v2y9z3KCsZ6ul3qQtGBKgnx3s0OtwRaDIuuUSc/export?format=csv&gid={sheet_gid}"
    try:
        df = pd.read_csv(url)
        st.success(f"✅ โหลดข้อมูล {name} สำเร็จ")
        return df
    except Exception as e:
        st.error(f"❌ โหลดข้อมูล {name} ล้มเหว: {e}")
        return pd.DataFrame()

# โหลดข้อมูล
routes_df = load_sheet(498856514, "Routes")
vendors_df = load_sheet(0, "Vendors")
distance_matrix_df = load_sheet(703414661, "Distance Matrix")

# -------------------------------
# เตรียมข้อมูลพิกัดของเวนเดอร์ + DIT
# -------------------------------
vendor_coords = {
    row["Ab."]: (row["lat"], row["lng"])
    for _, row in vendors_df.iterrows()
}
vendor_coords["DIT"] = (13.4214134, 101.0101508)

# -------------------------------
# UI เลือกวัน/รถ
# -------------------------------
routes_df["date"] = pd.to_datetime(routes_df["date"])
selected_date = st.date_input("เลือกวันที่", value=routes_df["date"].min())
selected_vehicle = st.selectbox("เลือกรถ", sorted(routes_df["vehicle_id"].unique()))

# กรองข้อมูล
filtered = routes_df[
    (routes_df["date"] == pd.to_datetime(selected_date)) &
    (routes_df["vehicle_id"] == selected_vehicle)
].sort_values(["trip_no", "arrival_time"])

if filtered.empty:
    st.warning("ไม่มีข้อมูลรอบรถในวันนี้")
    st.stop()

# -------------------------------
# เตรียม Distance Matrix (เลือกเฉพาะที่เกี่ยวข้อง)
# -------------------------------
used_abbr = filtered["Ab."].unique().tolist()
if "DIT" not in used_abbr:
    used_abbr.insert(0, "DIT")
else:
    used_abbr.remove("DIT")
    used_abbr.insert(0, "DIT")

matrix = distance_matrix_df.set_index(distance_matrix_df.columns[0])
matrix = matrix.loc[used_abbr, used_abbr]

# แปลงค่าทศนิยม -> จำนวนเต็ม (หน่วย 0.1 กม.)
distance_matrix = (matrix.to_numpy() * 10).round().astype(int).tolist()

# -------------------------------
# Google OR-Tools Optimizer
# -------------------------------
def solve_tsp(matrix):
    size = len(matrix)
    manager = pywrapcp.RoutingIndexManager(size, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_idx, to_idx):
        return matrix[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    solution = routing.SolveWithParameters(search_params)
    if not solution:
        return []

    index = routing.Start(0)
    route = []
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        route.append(node)
        index = solution.Value(routing.NextVar(index))
    route.append(manager.IndexToNode(index))
    return route

route_indices = solve_tsp(distance_matrix)
optimized_order = [used_abbr[i] for i in route_indices]

# -------------------------------
# แสดงผลลำดับ + ระยะทางรวม
# -------------------------------
st.subheader("🤭 ลำดับเส้นทางที่เหมาะสม")
for i, abbr in enumerate(optimized_order):
    st.write(f"{i+1}. {abbr}")

# ระยะทางรวม
if len(route_indices) >= 2:
    total_distance_units = 0
    for i in range(len(route_indices) - 1):
        from_idx = route_indices[i]
        to_idx = route_indices[i + 1]
        total_distance_units += distance_matrix[from_idx][to_idx]
    total_distance_km = total_distance_units / 10
    st.success(f"📏 ระยะทางรวม: {total_distance_km:.2f} กม.")

# -------------------------------
# แผนที่ Folium
# -------------------------------
st.subheader("📽️ แผนที่ Optimized")

start_point = vendor_coords.get("DIT", (13.7, 100.5))
route_map = folium.Map(location=start_point, zoom_start=10)

colors = ["blue", "green", "orange", "purple", "darkred", "cadetblue"]

coords = []
for i, abbr in enumerate(optimized_order):
    lat, lng = vendor_coords.get(abbr, (None, None))
    if lat and lng:
        coords.append((lat, lng))
        popup = f"{abbr}"
        icon_color = "red" if abbr == "DIT" else colors[i % len(colors)]
        folium.Marker(
            location=(lat, lng),
            popup=popup,
            icon=folium.Icon(color=icon_color)
        ).add_to(route_map)

if len(coords) >= 2:
    folium.PolyLine(coords, color="blue", weight=3, opacity=0.8).add_to(route_map)

st_folium(route_map, width=800, height=500)
