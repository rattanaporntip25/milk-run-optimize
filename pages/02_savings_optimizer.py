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
