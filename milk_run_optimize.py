import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

st.set_page_config(page_title="Milk Run Optimizer", layout="wide")
st.title("🧠 Milk Run Route Optimizer")
st.markdown("สร้างเส้นทางที่เหมาะสมจากข้อมูล Google Sheets")

# ฟังก์ชันโหลดข้อมูลจาก Google Sheets
@st.cache_data
def load_sheet(sheet_gid, name):
    url = f"https://docs.google.com/spreadsheets/d/1IQ2T_v2y9z3KCsZ6ul3qQtGBKgnx3s0OtwRaDIuuUSc/export?format=csv&gid={sheet_gid}"
    try:
        df = pd.read_csv(url)
        st.success(f"✅ โหลดข้อมูล {name} สำเร็จ")
        return df
    except Exception as e:
        st.error(f"❌ โหลดข้อมูล {name} ล้มเหลว: {e}")
        return pd.DataFrame()

# โหลดข้อมูล
routes_df = load_sheet(498856514, "Routes")
vendors_df = load_sheet(0, "Vendors")
distance_df = load_sheet(703414661, "Distance Matrix")

# ตรวจสอบคอลัมน์ date
if "date" not in routes_df.columns:
    st.error("❌ ไม่พบคอลัมน์ 'date' ในชีท Routes")
    st.stop()

# แปลงค่าวัน เช่น Mon, Tue,...
routes_df["day_name"] = routes_df["date"].astype(str).str.strip().str[:3]

# UI เลือกวันและรถ
selected_day = st.selectbox("เลือกวัน", sorted(routes_df["day_name"].unique()))
selected_vehicle = st.selectbox("เลือกรถ", sorted(routes_df["vehicle_id"].unique()))

# กรองตามวันที่และรถ
filtered = routes_df[
    (routes_df["day_name"] == selected_day) &
    (routes_df["vehicle_id"] == selected_vehicle)
].sort_values(["trip_no", "arrival_time"])

if filtered.empty:
    st.warning("ไม่พบข้อมูลสำหรับรถและวันดังกล่าว")
    st.stop()

# สร้างลิสต์ของจุดที่ต้องไป (รวม DIT)
locations = filtered["Ab."].tolist()
if "DIT" not in locations:
    locations.insert(0, "DIT")  # เริ่มต้นที่ DIT

# สร้าง Distance Matrix จากชีท
distance_matrix = distance_df.set_index(distance_df.columns[0])
distance_matrix = distance_matrix.loc[locations, locations].values
distance_matrix = np.round(distance_matrix, 2)

# ใช้ Google OR-Tools เพื่อ Optimize
def solve_tsp(dist_matrix):
    size = len(dist_matrix)
    manager = pywrapcp.RoutingIndexManager(size, 1, 0)  # เริ่มจาก index 0 (DIT)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_idx, to_idx):
        from_node = manager.IndexToNode(from_idx)
        to_node = manager.IndexToNode(to_idx)
        return int(dist_matrix[from_node][to_node] * 1000)  # แปลงเป็นเมตร

    transit_callback_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_idx)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC

    solution = routing.SolveWithParameters(search_parameters)
    if solution:
        index = routing.Start(0)
        route = []
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))
        return route
    else:
        return None

# คำนวณเส้นทาง
route_indices = solve_tsp(distance_matrix)
if not route_indices:
    st.error("❌ ไม่สามารถคำนวณเส้นทางได้")
    st.stop()

# สร้างชื่อจุดจาก index
optimized_route = [locations[i] for i in route_indices]

# แสดงผลลัพธ์
st.subheader("📍 เส้นทางที่เหมาะสม")
for i, stop in enumerate(optimized_route):
    st.write(f"{i+1}. {stop}")

# คำนวณระยะทางรวม
total_km = 0
for i in range(len(route_indices)-1):
    from_idx = route_indices[i]
    to_idx = route_indices[i+1]
    total_km += distance_matrix[from_idx][to_idx]

st.success(f"🛣️ ระยะทางรวมทั้งหมด: **{total_km:.2f} กม.**")

# พิกัดสำหรับแผนที่
vendor_coords = {row["Ab."]: (row["lat"], row["lng"]) for _, row in vendors_df.iterrows()}
vendor_coords["DIT"] = (13.4214134, 101.0101508)

# แสดงแผนที่ Folium
st.subheader("🗺️ แผนที่เส้นทาง")

first_point = optimized_route[0]
route_map = folium.Map(location=vendor_coords.get(first_point, (13.7, 100.5)), zoom_start=9)
colors = ["red", "blue", "green", "orange", "purple", "darkred"]

coords = []
for i, abbr in enumerate(optimized_route):
    coord = vendor_coords.get(abbr, None)
    if coord:
        coords.append(coord)
        popup = f"{i+1}. {abbr}"
        icon_color = "black" if abbr == "DIT" else "blue"
        folium.Marker(location=coord, popup=popup,
                      icon=folium.Icon(color=icon_color)).add_to(route_map)

if len(coords) >= 2:
    folium.PolyLine(coords, color="blue", weight=3, opacity=0.7).add_to(route_map)

st_folium(route_map, width=800, height=500)
