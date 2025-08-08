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

colors = ["red", "blue", "green", "orange", "purple", "darkred", "cadetblue", "darkgreen"]
route_map = folium.Map(location=vendor_coords.get("DIT", (13.7, 100.5)), zoom_start=9)

trip_list = filtered["trip_no"].unique()
for trip_idx, trip_no in enumerate(trip_list):
    trip_df = filtered[filtered["trip_no"] == trip_no]
    stops = trip_df["Ab."].tolist()
    if "DIT" not in stops:
        stops.insert(0, "DIT")

    dist_matrix = distance_df.set_index(distance_df.columns[0])
    dist_matrix = dist_matrix.loc[stops, stops].astype(float).values

    def solve_tsp(dist_matrix):
        size = len(dist_matrix)
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

    route_indices = solve_tsp(dist_matrix)
    if not route_indices:
        st.error(f"❌ ไม่สามารถคำนวณเส้นทางสำหรับ Trip {trip_no} ได้")
        continue

    optimized_route = [stops[i] for i in route_indices]
    st.subheader(f"📍 Trip {trip_no}: เส้นทางที่เหมาะสม")
    for i, stop in enumerate(optimized_route):
        st.write(f"{i+1}. {stop}")

    total_km = sum(dist_matrix[route_indices[i]][route_indices[i+1]] for i in range(len(route_indices)-1))
    st.success(f"🚐 Trip {trip_no} ระยะทางรวม: **{total_km:.2f} กม.**")

    coords = []
    for i, abbr in enumerate(optimized_route):
        coord = vendor_coords.get(abbr)
        if coord:
            coords.append(coord)
            popup = f"Trip {trip_no}: {i+1}. {abbr}"
            icon_color = "black" if abbr == "DIT" else colors[trip_idx % len(colors)]
            folium.Marker(location=coord, popup=popup,
                          icon=folium.Icon(color=icon_color)).add_to(route_map)

    if len(coords) >= 2:
        folium.PolyLine(coords, color=colors[trip_idx % len(colors)],
                        weight=3, opacity=0.8).add_to(route_map)

st.subheader("🗌️ แผนที่รวมทุก Trip")
st_folium(route_map, width=800, height=500)
