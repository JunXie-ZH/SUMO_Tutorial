import random

import psycopg2
import os
import sys
import optparse
import traci
from sumolib import checkBinary
import pandas as pd
import numpy as np
import datetime


if 'SUMO_HOME' in os.environ:
    os.environ['SUMO_HOME']='E:\\sumo-1.8.0\\'
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

def get_options():
    optParser = optparse.OptionParser()
    optParser.add_option("--nogui", action="store_true",
                         default=False, help="run the commandline version of sumo")
    options, args = optParser.parse_args()
    return options


class Half_perception:
    def __init__(self,ParkingInformation):

        self.ParkingOcc = ParkingInformation

        # 遍历所有停车区域，获取每一个区域的占有率
        Occ = list(map(lambda x: float(traci.simulation.getParameter(x,"parkingArea.occupancy")), list(ParkingInformation["ParkingArea"])))

        self.ParkingOcc["Occupancy"]=Occ

        # 感知停车场状态，以“停车区域--占有率”表示
    def Perceived_occupancy(self):

        # 遍历所有停车区域，获取每一个区域的占有率
        Occ = list(map(lambda x: float(traci.simulation.getParameter(x,"parkingArea.occupancy")), list(ParkingInformation["ParkingArea"])))

        # 构建一个datafrmame来存储“停车区域--占有率”
        self.ParkingOcc["Occupancy"]=Occ

        return self.ParkingOcc

    # 获取可用停车区域
    def get_AvailableParking(self):
        # 获取“停车区域--占有率”关系表
        ParkingOcc = self.ParkingOcc

        # 获取占有率小于1的停车区域列表
        AvailableParking = list(ParkingOcc[ParkingOcc["Occupancy"] < 1]["ParkingArea"])

        return AvailableParking


class Com_perception:
    def __init__(self,ParkingInformation):

        self.ParkingCapacity = ParkingInformation
        # 遍历所有停车区域，获取每一个区域的总容量
        Capacity = list(map(lambda x: float(traci.simulation.getParameter(x, "parkingArea.capacity")), list(ParkingInformation["ParkingArea"])))
        self.ParkingCapacity["Capacity"]=Capacity

        # 函数Add_update用于当车辆决定选择某个停车区域后，更新停车区域的剩余容量，即使该车辆还未行驶到停车区
    def Add_update(self, parkingArea):
        # 车辆进入停车场后，选择停在parkingArea（可用），则parkingArea的容量减1
        self.ParkingCapacity.loc[(self.ParkingCapacity.ParkingArea == parkingArea),
                                 'Capacity'] -= 1

    # 函数Leave_update用于当车辆离开停车位时，更新停车区域的剩余容量
    # parkInformation为存储的“车辆--停车区域”关系表，即每个车辆停在了哪个停车区
    def Leave_update(self, VehiclePark):
        # traci.simulation.getStopEndingVehiclesIDList()获取准备离开停车位的车辆列表
        for veh in list(traci.simulation.getStopEndingVehiclesIDList()):
            # 获取这些车辆所停的停车区域
            parkingArea = VehiclePark[VehiclePark.Veh == veh]["park"].values[0]

            # 更新该区域容量
            self.ParkingCapacity.loc[(self.ParkingCapacity.ParkingArea == parkingArea),
                                     'Capacity'] += 1

    # 获取“停车区域--剩余容量”
    def get_ParkingCapacity(self):
        return self.ParkingCapacity

    # 获取可用停车区域
    def get_AvailableParking(self):
        # 获取“停车区域--剩余容量”关系表
        ParkingCapacity = self.get_ParkingCapacity()

        # 获取剩余容量大于0的停车区域列表
        AvailableParking = list(ParkingCapacity[ParkingCapacity["Capacity"] > 0]
                                ["ParkingArea"])

        return AvailableParking


class Allocation:
    def __init__(self,parkingInformation):
        # 实例化感知模块
        # self.Perception = Half_perception(parkingInformation)  # 半感知
        self.Perception = Com_perception(parkingInformation)   # 全感知

    # 随机策略
    def Random_allocation(self):
        # 获取可用的停车区域列表
        AvailableParking = self.Perception.get_AvailableParking()

        # 利用random.choice从AvailableParking中随机选取一个可用的停车区域
        TargetParking = random.choice(AvailableParking)

        return TargetParking

    # 贪婪策略
    def Greedy_allocation(self,Entry):

        AvailableParking = self.Perception.get_ParkingCapacity()
        AvailableParking=AvailableParking[AvailableParking["Capacity"] > 0]
        AvailableParking=AvailableParking.reset_index(drop=True)

        AvailableParking=AvailableParking.sort_values(by=Entry, ascending=True)
        AvailableParking = AvailableParking.reset_index(drop=True)

        TargetParking = AvailableParking["ParkingArea"][0]

        return TargetParking


class Environment:
    def __init__(self):
        # 获取所有停车区域的ID
        ParkingAreaList = traci.parkingarea.getIDList()

        EntryDistance_1 = []
        EntryDistance_2 = []

        for parkingSpace in ParkingAreaList:
            lane=traci.parkingarea.getLaneID(parkingSpace)
            edge=traci.lane.getEdgeID(lane)

            distance_1 = traci.simulation.getDistanceRoad("F5E5", 0 , edge , 0)
            distance_2 = traci.simulation.getDistanceRoad("A2B2", 0, edge , 0)

            EntryDistance_1.append(distance_1)
            EntryDistance_2.append(distance_2)

        # 构建一个datafrmame来存储“停车区域--容量”
        self.ParkingInformation = pd.DataFrame({"ParkingArea": ParkingAreaList,"EntryDistance_1":EntryDistance_1,"EntryDistance_2":EntryDistance_2})

    def get_ParkingInformation(self):
        return self.ParkingInformation


if __name__ == '__main__' :
    options = get_options()
    if options.nogui:
        sumoBinary = checkBinary('sumo')
    else:
        sumoBinary = checkBinary('sumo-gui')
    traci.start([sumoBinary, "-c", "./P1/test.sumocfg", "--tripinfo-output", "tripinfo.xml",
                 "--quit-on-end"])  # ,"--start"

    SetMaxspeed = list(
        map(lambda x: traci.edge.setMaxSpeed(x, 3), list(traci.edge.getIDList())))  #####将所有道路的最大速度设为6m/s

    # 实例化Environment类
    Env=Environment()
    ParkingInformation=Env.get_ParkingInformation()

    # 实例化分配策略
    AL=Allocation(ParkingInformation)

    # 实例化全感知模块
    PER=Com_perception(ParkingInformation)

    # “车辆--停车区域”关系表
    VehiclePark=pd.DataFrame(columns=['Veh', 'park'])


    for step in range(3600):
        if step%20==0:
            # 第一个入口
            # 选定车位
            parkingArea_1=AL.Greedy_allocation("EntryDistance_1")

            # 各类参数信息
            tripid = "trip_1_" + str(step)  # 出行ID
            origin = "F5E5"  # 出发路段
            destination = traci.lane.getEdgeID(traci.parkingarea.getLaneID(parkingArea_1))
            vehid = "v_1_" + str(step)  # 车辆ID

            # 添加需求
            traci.route.add(tripid, [origin, destination])
            traci.vehicle.add(vehid, tripid)
            traci.vehicle.setParkingAreaStop(vehid, parkingArea_1, duration=random.randint(600,3600))

            # 将该信息加入到VehiclePark
            VehiclePark=VehiclePark.append({'Veh':vehid,'park':parkingArea_1},ignore_index=True)

            # 更新全感知模块
            PER.Add_update(parkingArea_1)

            # 第二个入口
            # 选定车位
            parkingArea_2=AL.Greedy_allocation("EntryDistance_2")

            # 各类参数信息
            tripid_2 = "trip_2_" + str(step)  # 出行ID
            origin_2 = "A2B2"  # 出发路段
            destination_2 = traci.lane.getEdgeID(traci.parkingarea.getLaneID(parkingArea_2))
            vehid_2 = "v_2_" + str(step)  # 车辆ID

            # 添加需求
            traci.route.add(tripid_2, [origin_2, destination_2])
            traci.vehicle.add(vehid_2, tripid_2)
            traci.vehicle.setParkingAreaStop(vehid_2, parkingArea_2, duration=random.randint(600,3600))

            # 将该信息加入到VehiclePark
            VehiclePark = VehiclePark.append({'Veh': vehid_2, 'park': parkingArea_2}, ignore_index=True)

            # 更新全感知模块
            PER.Add_update(parkingArea_2)

        PER.Leave_update(VehiclePark)

        traci.simulationStep()


