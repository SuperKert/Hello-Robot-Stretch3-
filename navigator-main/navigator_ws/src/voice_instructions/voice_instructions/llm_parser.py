import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import os

# Importamos el cliente de Mistral
# Nota: Asegúrate de tener la librería instalada: pip install mistralai
from mistralai import Mistral


class MistralParserNode(Node):
    def __init__(self):
        super().__init__('mistral_parser_node')

        # --- CONFIGURACIÓN ---
        # Recuperamos la API Key de una variable de entorno por seguridad
        # Puedes ponerla "hardcoded" aquí para pruebas, pero no se recomienda.
        api_key = os.environ.get("MISTRAL_API_KEY", "TU_API_KEY_AQUI_SI_NO_USAS_ENV")

        self.client = Mistral(api_key=api_key)
        self.model = "mistral-large-latest"  # O "mistral-small", "open-mixtral-8x7b", etc.

        # --- SYSTEM PROMPT (Tu Prompt) ---
        self.system_prompt = """
        Eres un parser jerárquico de ubicaciones.
        Tu tarea es convertir una instrucción en lenguaje natural en un formato estructurado formado por tres elementos:
        floor → planta o nivel del edificio (por ejemplo: "floor 2", "floor 0", "floor 1")
        room → tipo de habitación o zona (por ejemplo: "bathroom", "kitchen", "bedroom", "living room", etc.)
        object → objeto de interés dentro de la habitación, si existe (por ejemplo: "mirror", "chair", "sink").

        FORMATO DE RESPUESTA:
        Siempre responde en este formato exacto:
        [floor X, room-name, object-name]

        REGLAS IMPORTANTES:
        Extrae solo la información literal del texto.
        Convierte referencias como “primera planta” a floor 1, “baja” a floor 0.
        Si la instrucción indica una acción, ignórala y quédate solo con la ubicación.
        No expliques tu razonamiento.
        No añadas texto adicional.

        EJEMPLOS:
        User: "llévame al lavabo de la segunda planta" -> Assistant: [floor 2,bathroom,]
        User: "quiero ir a la cocina en la planta baja" -> Assistant: [floor 0,kitchen,]
        User: "dónde está el espejo del baño en la planta 1" -> Assistant: [floor 1,bathroom,mirror]
        """

        # --- ROS 2 INTERFACE ---
        # Suscriptor: Escucha lo que dice el humano
        self.subscription = self.create_subscription(
            String,
            '/instrucciones_voz',
            self.listener_callback,
            10)

        # Publicador: Envía el comando parseado al robot
        self.publisher_ = self.create_publisher(String, '/navegacion/objetivo', 10)

        self.get_logger().info('Nodo Mistral Parser iniciado. Esperando instrucciones...')

    def listener_callback(self, msg):
        user_input = msg.data
        self.get_logger().info(f'Instrucción recibida: "{user_input}"')

        # Llamamos a Mistral
        parsed_command = self.call_mistral(user_input)

        if parsed_command:
            # Publicamos el resultado
            msg_out = String()
            msg_out.data = parsed_command
            self.publisher_.publish(msg_out)
            self.get_logger().info(f'Comando enviado al robot: {parsed_command}')

    def call_mistral(self, user_text):
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_text}
            ]

            # Llamada síncrona a la API
            chat_response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=0.1  # Temperatura baja para ser más determinista
            )

            return chat_response.choices[0].message.content

        except Exception as e:
            self.get_logger().error(f'Error llamando a Mistral API: {e}')
            return None


def main(args=None):
    rclpy.init(args=args)
    node = MistralParserNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()