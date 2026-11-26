import rclpy
from ocr_node import DeepSeekOCRNode


def run(args=None):
    rclpy.init(args=args)
    node = DeepSeekOCRNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()