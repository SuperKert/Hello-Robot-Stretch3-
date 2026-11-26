import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
import numpy as np
import time

class ExplorerNode(Node):
    def __init__(self):
        super().__init__('explorer')
        self.get_logger().info("Explorer Node Started")

        # Subscriber to the map
        self.map_sub = self.create_subscription(
            OccupancyGrid, '/map', self.map_callback, 10)

        # Nav2 action client
        self.nav_to_pose_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # Track visited frontiers
        self.visited_frontiers = set()

        # Map + robot position
        self.map_data = None
        self.robot_position = (0, 0)  # Placeholder — needs real pose subscriber

        # Timer to run exploration every 5s
        self.timer = self.create_timer(5.0, self.explore)

    # Timestamp helper
    def ts(self):
        """Return timestamp formatted like ROS2 log prefix."""
        t = self.get_clock().now().to_msg()
        return f"[{t.sec}.{t.nanosec:09d}]"

    # Map callback
    def map_callback(self, msg):
        self.map_data = msg
        self.get_logger().info(f"{self.ts()} Map received")

    # Navigation functions
    def navigate_to(self, x, y):
        goal_msg = PoseStamped()
        goal_msg.header.frame_id = 'map'
        goal_msg.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.position.x = x
        goal_msg.pose.position.y = y
        goal_msg.pose.orientation.w = 1.0

        nav_goal = NavigateToPose.Goal()
        nav_goal.pose = goal_msg

        self.get_logger().info(f"{self.ts()} Navigating to goal: x={x}, y={y}")

        self.nav_to_pose_client.wait_for_server()
        send_goal_future = self.nav_to_pose_client.send_goal_async(nav_goal)
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().warning(f"{self.ts()} Goal rejected!")
            return

        self.get_logger().info(f"{self.ts()} Goal accepted")
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.navigation_complete_callback)

    def navigation_complete_callback(self, future):
        try:
            result = future.result().result
            self.get_logger().info(f"{self.ts()} Navigation completed with result: {result}")
        except Exception as e:
            self.get_logger().error(f"{self.ts()} Navigation failed: {e}")

    # Frontier detection
    def find_frontiers(self, map_array):
        frontiers = []
        rows, cols = map_array.shape

        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                if map_array[r, c] == 0:  # Free cell
                    neighbors = map_array[r-1:r+2, c-1:c+2].flatten()
                    if -1 in neighbors:
                        frontiers.append((r, c))

        self.get_logger().info(f"{self.ts()} Found {len(frontiers)} frontiers")
        return frontiers

    # Frontier selection
    def choose_frontier(self, frontiers):
        robot_row, robot_col = self.robot_position
        min_distance = float('inf')
        chosen_frontier = None

        for frontier in frontiers:
            if frontier in self.visited_frontiers:
                continue

            distance = np.sqrt((robot_row - frontier[0])**2 + (robot_col - frontier[1])**2)
            if distance < min_distance:
                min_distance = distance
                chosen_frontier = frontier

        if chosen_frontier:
            self.visited_frontiers.add(chosen_frontier)
            self.get_logger().info(f"{self.ts()} Chosen frontier: {chosen_frontier}")
        else:
            self.get_logger().warning(f"{self.ts()} No valid frontier found")

        return chosen_frontier

    # Exploration loop
    def explore(self):
        if self.map_data is None:
            self.get_logger().warning(f"{self.ts()} No map data available")
            return

        start = time.perf_counter()
        self.get_logger().info(f"{self.ts()} Exploration cycle started")

        # Convert map to numpy array
        map_array = np.array(self.map_data.data).reshape(
            (self.map_data.info.height, self.map_data.info.width))

        t1 = time.perf_counter()
        self.get_logger().info(f"{self.ts()} Map conversion took {t1 - start:.4f} s")

        # Detect frontiers
        frontiers = self.find_frontiers(map_array)

        t2 = time.perf_counter()
        self.get_logger().info(f"{self.ts()} Frontier detection took {t2 - t1:.4f} s")

        if not frontiers:
            self.get_logger().info(f"{self.ts()} No frontiers found. Exploration complete!")
            return

        # Choose frontier
        chosen_frontier = self.choose_frontier(frontiers)

        t3 = time.perf_counter()
        self.get_logger().info(f"{self.ts()} Frontier selection took {t3 - t2:.4f} s")

        if not chosen_frontier:
            self.get_logger().warning(f"{self.ts()} No frontiers to explore")
            return

        # Convert frontier to world coordinates
        goal_x = chosen_frontier[1] * self.map_data.info.resolution + self.map_data.info.origin.position.x
        goal_y = chosen_frontier[0] * self.map_data.info.resolution + self.map_data.info.origin.position.y

        # Send Nav2 command
        self.navigate_to(goal_x, goal_y)

        t4 = time.perf_counter()
        self.get_logger().info(f"{self.ts()} Navigation command took {t4 - t3:.4f} s")
        self.get_logger().info(f"{self.ts()} Total explore() cycle time: {t4 - start:.4f} s")

    # def shudown_robot(self):
    #     
    #
    #
    #     self.get_logger().info("Shutting down robot exploration")


def main(args=None):
    rclpy.init(args=args)
    explorer_node = ExplorerNode()

    try:
        explorer_node.get_logger().info("Starting exploration...")
        rclpy.spin(explorer_node)
    except KeyboardInterrupt:
        explorer_node.get_logger().info("Exploration stopped by user")
    finally:
        explorer_node.destroy_node()
        rclpy.shutdown()
