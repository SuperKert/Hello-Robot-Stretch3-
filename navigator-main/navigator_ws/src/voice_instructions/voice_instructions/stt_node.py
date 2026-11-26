import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import speech_recognition as sr


class STTNode(Node):
    def __init__(self):
        super().__init__('stt_node')
        self.publisher_ = self.create_publisher(String, '/instrucciones_voz', 10)

        # Configuramos el reconocedor
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

        # Ajuste inicial para el ruido ambiental
        with self.microphone as source:
            self.get_logger().info("Ajustando ruido ambiental... silencio por favor.")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)

        # Timer para revisar el micro continuamente
        self.create_timer(0.1, self.listen_loop)
        self.get_logger().info("Microfóno listo. ¡Te escucho!")

    def listen_loop(self):
        with self.microphone as source:
            try:
                # Escuchamos una frase (phrase_time_limit evita que se quede colgado)
                audio = self.recognizer.listen(source, timeout=1.0, phrase_time_limit=5.0)

                # Convertimos audio a texto usando Google (Gratis y no requiere API Key)
                text = self.recognizer.recognize_google(audio, language="es-ES")

                self.get_logger().info(f"He escuchado: {text}")

                # Publicamos el texto para que el nodo de Mistral lo reciba
                msg = String()
                msg.data = text
                self.publisher_.publish(msg)

            except sr.WaitTimeoutError:
                pass  # No se escuchó nada, seguimos esperando
            except sr.UnknownValueError:
                self.get_logger().warn("No he entendido el audio.")
            except Exception as e:
                self.get_logger().error(f"Error: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = STTNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()