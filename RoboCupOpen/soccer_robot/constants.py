from soccer_robot.mathf.vector2 import Vector2

import socket
import math

hostname = socket.gethostname()

ROBOT_NAMES = ["lnx-robot1", "lnx-robot2"]

try:
    ROBOT_INDEX = ROBOT_NAMES.index(hostname)
except ValueError:
    raise ValueError("Unknown hostname: {}".format(hostname))

if ROBOT_INDEX == 0:
    from .constants_robot1 import *
elif ROBOT_INDEX == 1:
    from .constants_robot2 import *
else:
    raise ImportError("No constants file for {}".format(hostname))

if CAMERA_INDEX == 0:
    # imx219
    CAMERA_SIZE = (820, 616)
    CAMERA_RAW_SIZE = (820, 616) # TODO: test
    CAMERA_FPS = 30
    CAMERA_FOV = 160
    CAMERA_F_LEN_MM = 3.15
    CAMERA_DIAG_MM = 4.6
    CAMERA_DISTANCE_MULTIPLIER = 1/2
    CAMERA_VERTICAL_CROP_01 = 0.4
    CAMERA_TUNING_FILE = "soccer_robot/assets/imx219_without_ct.json"
    SLOT_BOUNDING_BOX = (0.5, 0.93, 0.3, 0.14) # x, y, w, h
elif CAMERA_INDEX == 1:
    # rpi camera 3
    CAMERA_SIZE = (1152, 648)
    CAMERA_RAW_SIZE = (1152, 648)
    CAMERA_FPS = 30
    CAMERA_FOV = 120
    CAMERA_F_LEN_MM = 2.75
    CAMERA_DIAG_MM = 7.4
    CAMERA_DISTANCE_MULTIPLIER = 3/2
    CAMERA_VERTICAL_CROP_01 = 0.25
    CAMERA_TUNING_FILE = ""
    SLOT_BOUNDING_BOX = (0.5, 0.97, 0.3, 0.14)
elif CAMERA_INDEX == 2:
    # Arducam B0310
    CAMERA_SIZE = (1152, 648)
    CAMERA_RAW_SIZE = (2304, 1296)
    CAMERA_FPS = 30
    CAMERA_FOV = 152.2
    CAMERA_F_LEN_MM = 2.87
    CAMERA_DIAG_MM = 7.4
    CAMERA_DISTANCE_MULTIPLIER = 1
    CAMERA_VERTICAL_CROP_01 = 0.13
    CAMERA_TUNING_FILE = ""
    SLOT_BOUNDING_BOX = (0.5, 0.83, 0.3, 0.18)

CAMERA_WIDTH, CAMERA_HEIGHT = CAMERA_SIZE
CAMERA_DIAG_PX = math.sqrt(CAMERA_WIDTH**2+CAMERA_HEIGHT**2)
CAMERA_F_LEN_PX = CAMERA_DIAG_PX/2/math.tan(math.radians(CAMERA_FOV/2))
CAMERA_SENSOR_SIZE = (
    CAMERA_DIAG_MM/CAMERA_DIAG_PX * CAMERA_WIDTH,
    CAMERA_DIAG_MM/CAMERA_DIAG_PX * CAMERA_HEIGHT
)
SENSOR_DATA = list(zip(SENSOR_ANGLES, SENSOR_DIST))
MOTOR_SPEED_TO_MOTION = MOTOR_SPEED_TO_RPM/60 * ROBOT_WHEEL_D*math.pi

BACK_OFF_POS = Vector2(*TRACKER_HEATMAP_POINTS[BACK_OFF_SECTOR])
