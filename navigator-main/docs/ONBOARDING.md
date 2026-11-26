
# 🦾 Hello Robot Stretch 3 — Basic Usage and Setup for NavigatorD

## 1. Introduction

This repository contains the code and documentation required to work with the **Hello Robot Stretch 3**, focusing on:

- **Speech synthesis** (text-to-speech) and **speech recognition** (speech-to-text)  
- **Place identification** on an abstract map (represented as a graph)  
- **Social navigation**: avoiding people and behaving respectfully in shared environments  

![Stretch 3](https://docs.hello-robot.com/0.3/getting_started/images/stretch3_full.png)

In this README, you will find the steps to:

1. Power on the robot and connect via network / SSH  
2. Initialize the ROS 2 environment and free the robot’s control  
3. Move the robot using Python and ROS 2  
4. Control it with a joystick / gamepad  
5. Send commands via voice  

---

## 2. Connecting to the Robot via Network / SSH

The Stretch 3 includes an **Intel NUC** inside, running Ubuntu. You can connect in two ways: **tethered (wired)** or **untethered (wireless)**.

### 2.1 Tethered Setup

- In the robot’s “trunk” (next to the On/Off button), there are USB, HDMI, and Ethernet ports connected directly to the internal NUC.  
- Connect a monitor (HDMI), keyboard, and mouse (USB) to the robot, then power it on.  
- The Ubuntu desktop will appear; log in using the default credentials.

![Stretch 3 Trunk](https://docs.hello-robot.com/0.3/getting_started/images/stretch3_trunk_labeled.png)

### 2.2 Wireless Setup (SSH / Network)

To control the robot remotely:

```bash
ssh -X hello-robot@<robot-IP>
````

> The `-X` flag enables X forwarding for graphical interfaces (useful for running RViz or other GUIs remotely).

---

## 3. Robot Startup, Control Release, and System Basics

### 3.1 Releasing Control of the Robot

By default, when powered on, Stretch runs a gamepad teleoperation demo that locks the hardware for other processes.
To run your own nodes, you must first free that control:

```bash
stretch_free_robot_process.py
```

This command terminates the process that monopolizes the robot’s hardware, allowing your own application to connect.

You can also disable the automatic startup of this demo by going to **“Startup Applications”**, finding the entry `hello_robot_gamepad_teleop`, and disabling it.

### 3.2 System Check and Homing

To verify that all systems are functional:

```bash
stretch_system_check.py
```

This script tests sensors, actuators, and subsystems, and reports any issues found.

If any motor hasn’t completed its *homing* routine, execute:

```bash
stretch_robot_home.py
```

This will perform homing for each joint (base, arm, wrist, etc.).
Afterward, run `stretch_system_check.py` again to confirm everything is ready.

---

## 4. Python Control: Stretch Body Library

The **Stretch Body** library allows direct hardware control from Python.
Here’s a simple example:

```python
import stretch_body.robot

r = stretch_body.robot.Robot()
if not r.startup():
    raise RuntimeError("Failed to connect to the hardware")

# If not homed, perform homing
if not r.is_homed():
    r.home()

# Control base velocity
r.base.start_velocity_control()
r.base.set_velocity(0.1, 0.0)  # move forward at 0.1 m/s

# Stop at the end
r.stop()
```

> ⚠️ If you encounter an error like:
>
> ```
> Another process is already using Stretch. Try running "stretch_free_robot_process.py"
> ```
>
> It means another process is currently using the hardware. Run `stretch_free_robot_process.py` to release it.

The official documentation also covers sending position commands, reading joint states, and using trapezoidal motion profiles.

---

## 5. Basic ROS 2 Usage for Stretch 3

The ROS 2 system (“stretch_ros2”) contains all necessary packages to interact with the robot’s hardware.

### 5.1 Robot Drivers

The main package is **stretch_core**, which includes the **Stretch Driver** node.
With it, you can:

* Send motion commands (position / velocity)
* Read joint states
* Control sensors (lidar, cameras, microphone, IMU)

To launch with RViz:

```bash
ros2 launch stretch_core stretch_driver.launch.py rviz:=True
```

The driver supports multiple control modes:

* **Position mode** – control by joint position
* **Velocity mode** – control the base velocity using the `Twist` topic

### 5.2 Keyboard Teleoperation

To move the entire robot using the keyboard:

1. In one terminal, launch the Stretch driver:

   ```bash
   ros2 launch stretch_core stretch_driver.launch.py
   ```

2. In another terminal, run:

   ```bash
   ros2 run stretch_core keyboard_teleop
   ```

   This node connects to the driver and lets you move the base, arm, wrist, head, and gripper using the keyboard.

#### 🕹 Keyboard Command Menu

```
---------- KEYBOARD TELEOP MENU -----------

               i HEAD UP                    
  j HEAD LEFT            l HEAD RIGHT       
               , HEAD DOWN                  

  7 BASE ROTATE LEFT     9 BASE ROTATE RIGHT
  home                   page-up            

               8 LIFT UP                    
               ↑ up-arrow                     
  4 BASE FORWARD         6 BASE BACK        
  ← left-arrow            → right-arrow        
               2 LIFT DOWN                  
               ↓ down-arrow                   

               w ARM OUT                    
  a WRIST FORWARD        d WRIST BACK       
               x ARM IN                     

               5 GRIPPER CLOSE              
               0 GRIPPER OPEN               

  step size:  b BIG, m MEDIUM, s SMALL     

               q QUIT                       

-------------------------------------------
```

Press **Ctrl + C** to stop the node.

#### Base-Only Mode (Navigation Teleop)

If you only want to control the mobile base:

* Launch the driver in navigation mode:

  ```bash
  ros2 launch stretch_core stretch_driver.launch.py mode:=navigation
  ```

* Then, in another terminal:

  ```bash
  ros2 run teleop_twist_keyboard teleop_twist_keyboard cmd_vel:=stretch/cmd_vel
  ```

This allows you to control the base only via the velocity topic `cmd_vel`.

---

## 6. Gamepad / Joystick Control

For smoother control, Stretch supports teleoperation via gamepad.

* If the default gamepad teleop demo is active, you must **free the hardware** first (`stretch_free_robot_process.py`).
* The current teleop script is `stretch_gamepad_controller.py` (previously `stretch_xbox_controller_teleop.py`), combining position and velocity control for better responsiveness.

Steps:

1. Connect the gamepad to the robot (USB)
2. Ensure the hardware is released
3. Run the teleoperation node
4. Use the joysticks and buttons to move the base, arm, wrist, gripper, etc.

---

## 7. Voice Teleoperation

This example combines the **ReSpeaker microphone array** with *Follow Joint Trajectory* tutorials to **voice-control only the robot’s mobile base**.

1. In one terminal, launch the robot driver:

   ```bash
   ros2 launch stretch_core stretch_driver.launch.py
   ```

2. In another terminal, launch the ReSpeaker node:

   ```bash
   ros2 launch respeaker_ros2 respeaker.launch.py
   ```

3. In a third terminal, run the voice teleoperation node:

   ```bash
   cd ament_ws/src/stretch_tutorials/stretch_ros_tutorials/
   python3 voice_teleoperation_base.py
   ```

4. You will see a **voice command menu** in the terminal:

   ```
   ------------ VOICE TELEOP MENU ------------

   VOICE COMMANDS              
   "forward": BASE FORWARD                   
   "back"   : BASE BACK                      
   "left"   : BASE ROTATE LEFT               
   "right"  : BASE ROTATE RIGHT              
   "stretch": BASE ROTATES TOWARDS SOUND     

   STEP SIZE                 
   "big"    : BIG                            
   "medium" : MEDIUM                         
   "small"  : SMALL                          

   "quit"   : QUIT AND CLOSE NODE            

   -------------------------------------------
   ```

5. To stop sending `twist` messages:

   * Press **Ctrl + C**, or
   * Say **“quit”** to automatically close the node.

---
