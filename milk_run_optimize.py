
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import numpy as np

# ข้อมูลเวนเดอร์ (รวม DIT)
locations = {
    "DIT": (13.4214, 101.0101),
    "VND1": (13.5000, 100.9000),
    "VND2": (13.6000, 101.2000),
    "VND3": (13.4500, 100.8000),
}

# คำนวณระยะทางระหว่างทุกคู่
def compute_euclidean_distance_matrix(loc_dict):
    keys = list(loc_dict.keys())
    size = len(keys)
    matrix = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            xi, yi = loc_dict[keys[i]]
            xj, yj = loc_dict[keys[j]]
            matrix[i][j] = np.sqrt((xi - xj) ** 2 + (yi - yj) ** 2)
    return matrix, keys

distance_matrix, location_order = compute_euclidean_distance_matrix(locations)
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# คำนวณระยะทาง
distance_matrix = compute_euclidean_distance_matrix(locations)

# สร้าง routing model
manager = pywrapcp.RoutingIndexManager(len(distance_matrix), 1, 0)  # 1 vehicle, starts at index 0 (DIT)
routing = pywrapcp.RoutingModel(manager)

# สร้างฟังก์ชันระยะทาง
def distance_callback(from_index, to_index):
    from_node = manager.IndexToNode(from_index)
    to_node = manager.IndexToNode(to_index)
    return int(distance_matrix[from_node][to_node])

transit_callback_index = routing.RegisterTransitCallback(distance_callback)
routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

# สร้าง parameter
search_parameters = pywrapcp.DefaultRoutingSearchParameters()
search_parameters.first_solution_strategy = (
    routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

# แก้ปัญหา
solution = routing.SolveWithParameters(search_parameters)

# แสดงผล
if solution:
    index = routing.Start(0)
    route = []
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        route.append(list(locations.keys())[node])
        index = solution.Value(routing.NextVar(index))
    route.append(list(locations.keys())[manager.IndexToNode(index)])
    print("เส้นทางที่ดีที่สุด:", " -> ".join(route))
else:
    print("ไม่พบเส้นทางที่เหมาะสม")

# สร้างโมเดล
manager = pywrapcp.RoutingIndexManager(len(distance_matrix), 1, 0)  # 1 รถ, เริ่มที่จุด 0
routing = pywrapcp.RoutingModel(manager)

def distance_callback(from_index, to_index):
    return int(distance_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)] * 100000)

transit_callback_index = routing.RegisterTransitCallback(distance_callback)
routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

# เพิ่ม constraint: ให้จบทริปที่จุดเริ่ม
routing.AddDimension(
    transit_callback_index,
    0,  # no slack
    10000000,  # maximum distance
    True,  # start cumul to zero
    "Distance"
)

# Solve!
search_parameters = pywrapcp.DefaultRoutingSearchParameters()
search_parameters.first_solution_strategy = (
    routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

solution = routing.SolveWithParameters(search_parameters)

# แสดงผล
if solution:
    index = routing.Start(0)
    route = []
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        route.append(location_order[node])
        index = solution.Value(routing.NextVar(index))
    route.append(location_order[manager.IndexToNode(index)])
    print("เส้นทางที่ดีที่สุด:", " → ".join(route))
else:
    print("ไม่พบเส้นทางที่เหมาะสม")
