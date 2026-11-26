#!/bin/bash
set -e

# 1. Cargar ROS 2 base
source "/opt/ros/humble/setup.bash"

# 2. Cargar workspace
if [ -f "/root/ws/install/setup.bash" ]; then
    source "/root/ws/install/setup.bash"
fi

# 3. Ejecutar el comando final
exec "$@"