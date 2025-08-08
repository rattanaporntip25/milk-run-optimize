import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

st.set_page_config(page_title="Milk Run Optimizer", layout="wide")
st.title("🫠 Milk Run Route Optimizer")
st.markdown("สร้างเส้นทางที่เหมาะสมจากข้อมูล Google Sheets")

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

routes_df = load_sheet(498856514, "Routes")
vendors_df = load_sheet(0, "Vendors")
distance_df = load_sheet(703414661, "Distance Matrix")

if "date" not in routes_df.columns:
    st.error("❌ ไม่พบคอลัมน์ 'date' ในชีท Routes")
    st.stop()

routes_df["day_name"] = routes_df["date"].astype(str).str.strip().str[:3].str.capitalize()

selected_day = st.selectbox("เลือกวัน", sorted(routes_df["day_name"].unique()))
selected_vehicle = st.selectbox("เลือกรถ", sorted(routes_df["vehicle_id"].unique()))

filtered = routes_df[
    (routes_df["day_name"] == selected_day) &
    (routes_df["vehicle_id"] == selected_vehicle)
].sort_values(["trip_no"])

if filtered.empty:
    st.warning("ไม่พบข้อมูลสำหรับรถและวันดังกล่าว")
    st.stop()

vendor_coords = {row["Ab."]: (row["lat"], row["lng"]) for _, row in vendors_df.iterrows()}
vendor_coords["DIT"] = (13.4214134, 101.0101508)

colors = ["red", "blue", "green", "orange", "purple", "darkred", "cadetblue", "darkblue"]
route_map = folium.Map(location=vendor_coords["DIT"], zoom_start=9)

def solve_tsp(locations, dist_matrix):
    size = len(locations)
    manager = pywrapcp.RoutingIndexManager(size, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_idx, to_idx):
        from_node = manager.IndexToNode(from_idx)
        to_node = manager.IndexToNode(to_idx)
        return int(dist_matrix[from_node][to_node] * 1000)

    transit_callback_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_idx)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

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

total_km_all_trips = 0

for i, (trip_no, group) in enumerate(filtered.groupby("trip_no")):
    st.subheader(f"📍 Trip {trip_no}: เส้นทางที่เหมาะสม")
    trip_locs = group["Ab."].tolist()
    non_dit = [x for x in trip_locs if x != "DIT"]
    locations = ["DIT"] + non_dit

    try:
        dist_matrix = distance_df.set_index(distance_df.columns[0])
        dist_matrix = dist_matrix.loc[locations, locations].astype(float).values
    except:
        st.warning(f"❌ ไม่สามารถโหลดระยะทาง trip {trip_no}")
        continue

    route_indices = solve_tsp(locations, dist_matrix)
    if not route_indices:
        st.warning(f"❌ ไม่สามารถ optimize trip {trip_no}")
        continue

    optimized_route = [locations[i] for i in route_indices]
    
    seq = 1
    for stop in optimized_route:
        if stop == "DIT":
            st.write(f"{stop} (โรงงาน)")
        else:
            st.write(f"{seq}. {stop}")
            seq += 1

    total_km = 0
    for j in range(len(route_indices)-1):
        total_km += dist_matrix[route_indices[j]][route_indices[j+1]]

    total_km_all_trips += total_km
    st.success(f"🛣️ ระยะทาง trip {trip_no}: **{total_km:.2f} กม.**")

    coords = []
    seq = 1
    for abbr in optimized_route:
        coord = vendor_coords.get(abbr)
        if coord:
            coords.append(coord)
            if abbr == "DIT":
                popup = f"Trip {trip_no} | โรงงาน"
                icon_color = "black"
            else:
                popup = f"Trip {trip_no} | {seq}. {abbr}"
                icon_color = colors[i % len(colors)]
                seq += 1
            folium.Marker(location=coord, popup=popup,
                          icon=folium.Icon(color=icon_color)).add_to(route_map)

    if len(coords) >= 2:
        folium.PolyLine(coords, color=colors[i % len(colors)], weight=3, opacity=0.8).add_to(route_map)

st.header("🗺️ แผนที่รวมทุก Trip")
st_folium(route_map, width=900, height=600)

st.success(f"📏 ระยะทางรวมทั้งหมด: **{total_km_all_trips:.2f} กม.**")
# milk_run_savings.py

import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# -------------------------
# Page Setup
# -------------------------
st.set_page_config(page_title="Milk Run Optimizer", layout="wide")
st.title("🧠 Milk Run Savings-based Optimizer")
st.markdown("ใช้ข้อมูลจาก Google Sheets เพื่อคำนวณเส้นทางที่เหมาะสมที่สุด")

# -------------------------
# Load Data from Google Sheets
# -------------------------
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

vendors_df = load_sheet(0, "Vendors")
routes_df = load_sheet(498856514, "Routes")
vehicles_df = load_sheet(1327265658, "Vehicles")
distance_df = load_sheet(703414661, "Distance Matrix")

# -------------------------
# Setup and Prepare Data
# -------------------------
vendors_df["Ab."] = vendors_df["Ab."].str.strip()
distance_df = distance_df.set_index(distance_df.columns[0])

# Fix: Add DIT (Daikin HQ)
vendors_df = pd.concat([
    pd.DataFrame.from_records([{
        "Ab.": "DIT",
        "lat": 13.4214134,
        "lng": 101.0101508,
        "Name": "DAIKIN INDUSTRIES (THAILAND) LTD."
    }]),
    vendors_df
], ignore_index=True)

# วันในภาษาอังกฤษ 3 ตัวอักษร
routes_df["day_name"] = routes_df["date"].astype(str).str[:3].str.capitalize()

selected_day = st.selectbox("เลือกวัน", sorted(routes_df["day_name"].unique()))

# -------------------------
# Optimization Function
# -------------------------
def solve_savings(locations, distance_matrix):
    size = len(locations)
    manager = pywrapcp.RoutingIndexManager(size, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_idx, to_idx):
        from_node = manager.IndexToNode(from_idx)
        to_node = manager.IndexToNode(to_idx)
        return int(distance_matrix[from_node][to_node] * 1000)

    transit_callback_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_idx)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.SAVINGS)

    solution = routing.SolveWithParameters(search_parameters)

    if solution:
        index = routing.Start(0)
        route = []
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))
        return route
    return None

# -------------------------
# Main Run (Per Vehicle)
# -------------------------

vendor_coords = {row["Ab."]: (row["lat"], row["lng"]) for _, row in vendors_df.iterrows()}

for vehicle_id in sorted(routes_df[routes_df["day_name"] == selected_day]["vehicle_id"].unique()):
    st.subheader(f"🚚 รถ: {vehicle_id}")
    vehicle_routes = routes_df[(routes_df["vehicle_id"] == vehicle_id) & (routes_df["day_name"] == selected_day)]

    for trip_no, group in vehicle_routes.groupby("trip_no"):
        st.markdown(f"**Trip {trip_no}**")
        vendor_list = group["Ab."].tolist()

        if "DIT" not in vendor_list:
            vendor_list.insert(0, "DIT")

        dist_mat = distance_df.loc[vendor_list, vendor_list].astype(float).values
        route_idx = solve_savings(vendor_list, dist_mat)

        if not route_idx:
            st.warning(f"ไม่สามารถ optimize เส้นทาง Trip {trip_no}")
            continue

        optimized = [vendor_list[i] for i in route_idx]

        for i, abbr in enumerate(optimized):
            st.write(f"{i+1}. {abbr}")

        # Total Distance
        total_km = 0
        for i in range(len(route_idx)-1):
            total_km += dist_mat[route_idx[i]][route_idx[i+1]]

        st.success(f"🚩 ระยะทางรวม: {total_km:.2f} กม.")

        # Map
        map_color = "blue"
        fmap = folium.Map(location=vendor_coords["DIT"], zoom_start=9)
        coords = []
        for i, abbr in enumerate(optimized):
            coord = vendor_coords.get(abbr)
            coords.append(coord)
            popup = f"{i+1}. {abbr}"
            icon_color = "black" if abbr == "DIT" else "green"
            folium.Marker(location=coord, popup=popup, icon=folium.Icon(color=icon_color)).add_to(fmap)

        folium.PolyLine(coords, color=map_color, weight=3, opacity=0.7).add_to(fmap)
        st_folium(fmap, width=850, height=500)
