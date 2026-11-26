TERMINAL 1: 

hello-robot@stretch-se3-3110:~$ pwd 

/home/hello-robot 

hello-robot@stretch-se3-3110:~$ stretch_robot_home.py 

hello-robot@stretch-se3-3110:~$ ros2 launch stretch_nav2 offline_mapping.launch.py 

 

TERMINAL 2: 

hello-robot@stretch-se3-3110:~$ pwd 

/home/hello-robot 

hello-robot@stretch-se3-3110:~$ ros2 launch stretch_core d435i_basic.launch.py 

 

TERMINAL 3: 

hello-robot@stretch-se3-3110:~/Desktop$ pwd 

/home/hello-robot/Desktop 

hello-robot@stretch-se3-3110:~/ament_ws$ ros2 run stretch_core capture_stretch3_OVO 

 

ROS DOMAIN 

export ROS_DOMAIN_ID=225 

echo $ROS_DOMAIN_ID 

 

REBUILD Y SOURCE 

cd ~/PycharmProjects/navigator/navigator_ws 

source /opt/ros/jazzy/setup.bash    

colcon build 

source install/setup.bash 

 

ENV 

source ocr_venv/bin/activate 

 

OCR 

ros2 run stretch_ocr ocr 

 

Docker: 
 
docker run -it --rm --net=host --gpus all --ipc=host -v /home/alexis/PycharmProjects/navigator/navigator_ws:/root/ws -e ROS_DOMAIN_ID=30 mi_ros2_deepseek 
 
 

  

TODO 

cd ~/PycharmProjects/navigator/navigator_ws 

source /opt/ros/jazzy/setup.bash    

colcon build 

source install/setup.bash 

ros2 run stretch_ocr ocr 

 
export ROS_DOMAIN_ID=225 

ros2 topic hz /camera/color/image_raw 

ping 192.168.10.2 