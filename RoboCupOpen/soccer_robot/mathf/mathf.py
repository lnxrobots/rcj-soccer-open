import soccer_robot.constants as con
from soccer_robot.mathf.vector2 import Vector2

import math

def get_line_pos(active_indexes):
    active = [con.SENSOR_DATA[i] for i in active_indexes]

    if len(active) == 0:
        return None
    elif len(active) == 1:
        return active[0]

    # Add the first sensor to the list for comparison
    active_temp = active + [(active[0][0]+360, active[0][1])]

    # Find the sensors with largest angle between them - marginal sensors
    marginal = None
    max_angle = 0
    for i in range(len(active_temp)-1):
        s1 = active_temp[i]
        s2 = active_temp[i+1]
        diff_angle = s2[0]-s1[0]
        if diff_angle > max_angle:
            max_angle = diff_angle
            marginal = [s1, s2]
            # Flip the sensors to flip the angle, if angle too large for a \triangle
            if diff_angle > 180:
                marginal = [s2, s1]

    (a1, r1), (a2, r2) = marginal
    g = math.radians(a2-a1)

    # Calculate height of the triangle center-s1-s2 (using area) and angle between s1 and height
    h = r1*r2*math.sin(g) / math.sqrt(r1*r1 + r2*r2 - 2*r1*r2*math.cos(g))
    l = (a1 + math.degrees(math.acos(h/r1))) % 360
    return l, h

def direction_to_motors(a, spin=0, v=80, should_round=True) -> list:
    """Works only for 4 motors. Spin -1 to 1"""
    #spin += 0.015

    right_a = math.radians(a-45)
    x = math.sin(right_a)
    y = math.cos(right_a)
    motors = list(map(lambda m: m-spin, [-x, y, x, -y]))
    k = v/max(list(map(abs, motors)))
    motors = list(map(lambda m: m*k, motors))

    if should_round:
        return list(map(round, motors))
    return motors

def motors_to_vel(motors):
    result = Vector2(0, 0)
    for m, a in zip(motors, [315, 45, 135, 225]):
        result += Vector2(a=math.radians(a), m=m)
    return result/4 * con.MOTOR_SPEED_TO_MOTION

def direction_to_spin(a):
    return clamp(((a + 180) % 360 - 180) / con.SPIN_MAX_SPEED_ANGLE, -1.0, 1.0)

def clamp(value, min_value, max_value):
    return max(min(value, max_value), min_value)

def lerp(a: float, b: float, t: float) -> float:
    return (1.0 - t) * a + b * t

def inv_lerp(a: float, b: float, v: float) -> float:
    return (v - a) / (b - a)

def remap(iMin: float, iMax: float, oMin: float, oMax: float, v: float):
    t: float = inv_lerp(iMin, iMax, v)
    return lerp(oMin, oMax, t)

def sign(value) -> int:
    if value > 0:
        return 1
    elif value < 0:
        return -1
    return 0

def img_coords_to_angles(x, y):
    cx, cy = x-con.CAMERA_WIDTH/2, y-con.CAMERA_HEIGHT/2
    xa = math.degrees(math.atan2(cx, con.CAMERA_F_LEN_PX)) % 360
    ya = math.degrees(math.atan2(cy, con.CAMERA_F_LEN_PX) + math.radians(con.CAMERA_MOUNT_ANGLE)) % 360
    return xa, ya
def img_coords_to_angle_dist(position, real_size=(con.BALL_DIAMETER, con.BALL_DIAMETER), i=0):
    x, y = position[:2]
    cx, cy = (x-0.5)*con.CAMERA_WIDTH, (y-0.5)*con.CAMERA_HEIGHT

    c_xa = math.atan2(cx, con.CAMERA_F_LEN_PX)
    # c_ya = math.atan2(cy, con.CAMERA_F_LEN_PX) + math.radians(con.CAMERA_MOUNT_ANGLE)

    c_dist = distance_from_size(position[2:], real_size, i)
    r_vec = Vector2(a=c_xa, m=c_dist)+Vector2(*con.CAMERA_MOUNT_POSITION[:2])

    return normalize_angle(math.degrees(r_vec.get_angle())), r_vec.get_magnitude()

def is_angle_between(angle, first, second):
    second = (second - first) % 360
    angle = (angle - first) % 360
    return (angle < second)

def normalize_angle(a):
    if a < 0:
        a += 360
    return a % 360

def distance_from_size(px_size, real_size=(con.BALL_DIAMETER, con.BALL_DIAMETER), i=0):
    if px_size[i] == 0:
        return -1
    image_size = con.CAMERA_SENSOR_SIZE[i] * px_size[i]
    distance_from_camera = real_size[i] * con.CAMERA_F_LEN_MM / image_size * con.CAMERA_DISTANCE_MULTIPLIER
    camera_height_relative = con.CAMERA_MOUNT_POSITION[2] - real_size[1]/2

    if distance_from_camera > camera_height_relative:
        return math.sqrt(distance_from_camera ** 2 - camera_height_relative ** 2)
    return 0.1

def distance_from_angle(v_angle, height=con.BALL_DIAMETER):
    camera_height_relative = con.CAMERA_MOUNT_POSITION[2] - height/2
    return camera_height_relative / math.tan(math.radians(v_angle))
