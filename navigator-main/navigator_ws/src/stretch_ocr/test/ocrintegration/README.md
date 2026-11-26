# Stretch OCR

This package provides OCR (Optical Character Recognition) capabilities for the Stretch robot using ROS2.

## Prerequisites

- ROS2 Jazzy
- Conda environment with OCR dependencies
- Stretch robot with D435i camera

## Setup Instructions

### 1. Set ROS Domain ID

Configure the ROS domain ID to ensure proper communication:

```bash
export ROS_DOMAIN_ID=45
echo $ROS_DOMAIN_ID  # Verify the domain ID is set
```

### 2. Build and Source the Workspace

Navigate to your ROS2 workspace, build the packages, and source the setup file:

```bash
cd ~/ros2_ws
colcon build
source install/setup.bash
```

### 3. Activate Conda Environment

Activate the conda environment with OCR dependencies and source ROS2:

```bash
conda activate deepseek-ocr
source /opt/ros/jazzy/setup.bash
```

## Running the System

The system requires three separate terminals running concurrently.

### Terminal 1: Navigation and Mapping

Launch the offline mapping system:

```bash
cd /home/hello-robot
stretch_robot_home.py
ros2 launch stretch_nav2 offline_mapping.launch.py
```

### Terminal 2: Camera Node

Launch the D435i camera node:

```bash
cd /home/hello-robot
ros2 launch stretch_core d435i_basic.launch.py
```

### Terminal 3: OVO Capture

Run the OVO capture node:

```bash
cd /home/hello-robot/Desktop
ros2 run stretch_core capture_stretch3_OVO
```

## Running the OCR Node

After completing the setup and launching the required nodes, run the OCR node:

```bash
ros2 run stretch_ocr ocr
```

## Troubleshooting

- Ensure all three terminal sessions have the correct ROS_DOMAIN_ID set
- Verify that the conda environment is activated before running the OCR node
- Check that the D435i camera is properly connected and recognized by the system 


## Contenedor Docker

Paso 1: Build the Docker image

```bash
docker build -t mi_ros2_deepseek .
```

Step 2: Deploy the container

```bash
# Recuerda: ROS_DOMAIN_ID debe ser el mismo que el del robot (ej. 30)
docker run -it --rm \
    --net=host \
    --gpus all \
    --ipc=host \
    -v ~/ruta_del_ws_ordenador:/root/ws \
    -e ROS_DOMAIN_ID=30 \
    mi_ros2_deepseek
```