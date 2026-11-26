# 🚀Autonomous Explorer Node for Frontier Exploration

This guide explains how to launch the autonomous frontier-exploration node using multiple terminals in ROS 2.

Link for github repo: https://github.com/AniArka/Autonomous-Explorer-and-Mapper-ros2-nav2

## Launch Procedure
The system requires 4 terminals, executed in order.
Firstly check which version of files is saved in: /demo_repos/explorer/frontlogs and choose next number when launching commands both for autonomous node and for saved maps in order to keep record of trials made!!! 🤖

## Terminal 1 - Start Explorer Node
```bash
cd demo_repos/explorer/
source install/setup.bash
```
⚠️ Run the explorer only after all other terminals are running!

To start autonomous explorer node:
```bash
ros2 run custom_explorer explorer
```
To start autonomous explorer node with logs saved into frontlogs directory:
```bash
ros2 run custom_explorer explorer \
  2>&1 | tee frontlogs/frontier_exploration_v"NUMBER".log
```
Example of Opening saved logs: /demo_repos/explorer/frontlogs
```bash
cat frontier_exploration_v5.log
```
```bash
less frontier_exploration_v5.log
```

## Terminal 2 — Launch Navigation with Map
Launches **RVIZ** with already saved map of laboratory.
```bash
ros2 launch stretch_nav2 navigation.launch.py map:=${HELLO_FLEET_PATH}/maps/1311nov.yaml
```
## Terminal 3 — Launch Online Async Nodes
Launches nodes responsible of background robot processes that continuously publish sensor data and system updates needed for navigation to work.
```bash
ros2 launch stretch_nav2 online_async_launch.py
```
⚠️ Emergency Stop Instructions

- White button on the robot is the emergency stop. Located on side of robot head!
- To restore power and bring all nodes back online,
**press and HOLD** the white button for 3 seconds!!!
  
## Terminal 4 — Save Map Info to demo_repos/explorer/maps
Creates two files: 
maps/map_v"nr".yaml - image of occupancy grid and maps/map_v"nr".pgm - metadata (resolution, origin, etc.)
```bash
ros2 run nav2_map_server map_saver_cli -f map_v"NUMBER"
```
Command for Converting .pgm into .png picture format! (Right now not needed to do, maybe in future!)
```bash
gm convert map_v"number".pgm map_v"number".png
```
Example of Opening saved maps: /demo_repos/explorer/maps
```bash
cat map_v2.yaml
```
```bash
xdg-open map_v2.pgm
```

## 🛠 Troubleshooting
❗ Explorer node not starting

In Case of Other Proccess Running then:
```bash
stretch_free_robot_process.py
```

Make sure the workspace was sourced:
```bash
source install/setup.bash
```

🗺️ MAP Sanity check:
```bash
eog ${HELLO_FLEET_PATH}/maps/1311nov.pgm
```
