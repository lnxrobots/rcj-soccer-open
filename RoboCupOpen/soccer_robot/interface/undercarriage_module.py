from soccer_robot.module.module import Module
from soccer_robot.logger.logger_module import LoggerModule
from soccer_robot.constants import UNDERCARRIAGE_SERIAL_PORT, UNDERCARRIAGE_BOUD_RATE, MOTOR_CONF

import multiprocessing
import serial
import json
import enum
import time

import os

class MessageType(enum.Enum):
    NONE = -1
    INIT = 0
    DISCONNECT = 1
    ERROR = 2
    MOTORS = 3
    SENSORS = 4
    SENSOR_STAT_RESET_RQ = 5
    SENSOR_STAT_RESET_RS = 6
    SENSOR_STAT_READ_RQ = 7
    SENSOR_STAT_READ_RS = 8
    SENSOR_LOG_READ_RQ = 9
    SENSOR_LOG_READ_RS = 10

class UndercarriageModule(Module):
    module_name = "UndercarriageModule"

    @classmethod
    def init(cls) -> None:
        super().init()

        cls._motor_values = multiprocessing.Array("i", [0] * 4)
        cls._color_sensor_values = multiprocessing.Array("i", [0] * 16)

        cls._motor_message_interval = multiprocessing.Value("d", 0.006)

        cls._sensor_stat_samples = multiprocessing.Value("i", 0)

        cls._sensor_stat_values = multiprocessing.Array("i", [0]*16*3)
        cls._sensor_histogram_values = multiprocessing.Array("i", [0]*16*8)
        # 0 - after innit, 1 - reset wanted, 2 - waiting for reset, 3 - reset done
        cls._stat_reset_state = multiprocessing.Value("i", 0)
        cls._stat_read_state = multiprocessing.Value("i", 0)

        # 0 - after innit, 1 - log wanted, 2 - waiting for log data, 3 - part of log received, 4 - complete log data received
        cls._log_read_state = multiprocessing.Value("i", 0)
        cls._sensor_log_values = multiprocessing.Array("i", [0]*6144)
        cls._sensor_log_info = multiprocessing.Array("i", [0]*4) #Id, From, Count, Received,
        #cls._sensor_to_log_values = multiprocessing.Array("i", [0]*16*20) # !!!value needs to match with LOG_HISTORY value from teensy!!!(LOG_HISTORY = 20)

    @classmethod
    def on_run(cls, stop_flag) -> None:
        # Workaround for poor communicatining performance
        # TODO: Invastigate the issue
        os.nice(-10)

        serial_connection = serial.Serial(UNDERCARRIAGE_SERIAL_PORT, UNDERCARRIAGE_BOUD_RATE, timeout = 1)
        serial_connection.flush()

        os.nice(-10)

        init = {
            "type": MessageType.INIT.value,
            "mc": MOTOR_CONF
        }

        init_json = json.dumps(init)
        serial_connection.write((init_json + "\n").encode())

        LoggerModule.log_info("Init packet sent: {}".format(init_json))

        last_message_time = time.time()

        while not stop_flag.value:
            # Check for incoming messages

            LoggerModule.log_info("In wating: {}".format(serial_connection.in_waiting))

            if serial_connection.in_waiting:

                try:
                    line = serial_connection.readline().decode("utf-8").rstrip()
                except:
                    LoggerModule.log_error("Undercarriage message cannot be parsed")
                    continue

                json_file = json.loads(line)
                message_type = json_file["type"]

                if (message_type == MessageType.INIT.value):
                    LoggerModule.log_info("Undercarriage successfully initted")

                elif (message_type == MessageType.DISCONNECT.value):
                    LoggerModule.log_info("Undercarriage disconnected")

                elif (message_type == MessageType.ERROR.value):
                    LoggerModule.log_warning("Undercarriage error: " + json_file["message"])

                elif (message_type == MessageType.MOTORS.value):
                    pass

                elif (message_type == MessageType.SENSORS.value):
                    with cls._color_sensor_values.get_lock():
                        cls._color_sensor_values[0:16] = json_file["v"]

                elif (message_type == MessageType.SENSOR_STAT_RESET_RS.value):
                    with cls._stat_reset_state.get_lock():
                        cls._stat_reset_state.value = 3

                elif (message_type == MessageType.SENSOR_STAT_READ_RS.value):
                    with cls._sensor_stat_values.get_lock():
                        cls._sensor_stat_samples.value = json_file["count"]

                        cls._sensor_stat_values[0:16] = json_file["v"]
                        cls._sensor_stat_values[16:32] = json_file["u"]
                        cls._sensor_stat_values[32:48] = json_file["w"]

                    with cls._sensor_histogram_values.get_lock():
                        cls._sensor_histogram_values[0:128] = json_file["h"]

                    with cls._stat_read_state.get_lock():
                        cls._stat_read_state.value = 3

                elif (message_type == MessageType.SENSOR_LOG_READ_RS.value):
                    with cls._log_read_state.get_lock() and cls._sensor_log_info.get_lock() and cls._sensor_log_values.get_lock():
                        message_id = json_file["id"]
                        message_from = json_file["f"]
                        message_size = json_file["s"]
                        message_data = json_file["v"]
                        LoggerModule.log_debug(json_file)

                        if(cls._sensor_log_info[0] == message_id and cls._log_read_state.value == 2):
                            cls._log_read_state.value = 3

                        if(cls._sensor_log_info[0] == message_id and cls._sensor_log_info[3] + cls._sensor_log_info[1] == message_from):
                            cls._sensor_log_values[message_from - cls._sensor_log_info[1]:message_from + len(message_data) - cls._sensor_log_info[1]] = message_data
                            cls._sensor_log_info[3] += len(message_data)
                            if (cls._sensor_log_info[3] >= cls._sensor_log_info[2] or cls._sensor_log_info[3] + cls._sensor_log_info[1] >= message_size):
                                cls._log_read_state.value = 4

                        LoggerModule.log_debug(cls._log_read_state.value)
                        LoggerModule.log_debug(cls._sensor_log_info[0:4])

                        LoggerModule.log_debug(cls._log_read_state.value)
                        LoggerModule.log_debug(cls._sensor_log_info[0:4])
                    
            message_json = ""
            if (time.time() - last_message_time >=  cls._motor_message_interval.value):
                last_message_time = time.time()

                with cls._motor_values.get_lock():
                    checksum = cls._motor_values[0] + cls._motor_values[1] + cls._motor_values[2] + cls._motor_values[3]

                    motor_message = {
                    "type": 3,
                    "v": cls._motor_values[0:4],
                    "cs": checksum
                    }

                message_json = json.dumps(motor_message, separators=(',', ':'))

            if (message_json == ""):
                with cls._stat_reset_state.get_lock():
                    state = cls._stat_reset_state.value
                    if(state == 1):
                        cls._stat_reset_state.value = 2
                if(state == 1):
                    request_message = {
                    "type": MessageType.SENSOR_STAT_RESET_RQ.value
                    }
                    message_json = json.dumps(request_message, separators=(',', ':'))

            if (message_json == ""):
                with cls._stat_read_state.get_lock():
                    state = cls._stat_read_state.value
                    if(state == 1):
                        cls._stat_read_state.value = 2
                if(state == 1):
                    request_message = {
                    "type": MessageType.SENSOR_STAT_READ_RQ.value
                    }
                    message_json = json.dumps(request_message, separators=(',', ':'))

            if (message_json == ""):
                with cls._log_read_state.get_lock():
                    state = cls._log_read_state.value
                    if(state == 1):
                        cls._log_read_state.value = 2
                if(state == 1):
                    with cls._sensor_log_info.get_lock():
                        request_message = {
                        "type": MessageType.SENSOR_LOG_READ_RQ.value,
                        "id": cls._sensor_log_info[0],
                        "f": cls._sensor_log_info[1],
                        "c": cls._sensor_log_info[2]
                        }
                        cls._sensor_log_info[3] = 0
                    message_json = json.dumps(request_message, separators=(',', ':'))

            if (message_json != ""):
                serial_connection.write((message_json + "\n").encode())
        disconnect = {
            "type": MessageType.DISCONNECT.value
        }

        disconnect_json = json.dumps(disconnect)
        serial_connection.write((disconnect_json + "\n").encode())

        serial_connection.close()



    # TODO: Check whether motor values are in range
    @classmethod
    def set_motor_values(cls, first, second, third, fourth) -> None:
        with cls._motor_values.get_lock():
            cls._motor_values[0] = first
            cls._motor_values[1] = second
            cls._motor_values[2] = third
            cls._motor_values[3] = fourth

    @classmethod
    def get_motor_values(cls) -> tuple:
        with cls._motor_values.get_lock():
            return cls._motor_values[0:4]

    @classmethod
    def get_color_sensor_values(cls) -> tuple:
        with cls._color_sensor_values.get_lock():
            return cls._color_sensor_values[0:16]

    @classmethod
    def get_sensor_stats_samples(cls) -> tuple:
        with cls._sensor_stat_samples.get_lock():
            return cls._sensor_stat_samples.value

    @classmethod
    def get_sensor_stats_values(cls) -> tuple:
        with cls._sensor_stat_values.get_lock():
            return cls._sensor_stat_values[0:16*3]

    @classmethod
    def get_sensor_histogram_values(cls) -> tuple:
        with cls._sensor_histogram_values.get_lock():
            return cls._sensor_histogram_values[0:16*8]

    @classmethod
    def request_stat_reset(cls):
        with cls._stat_reset_state.get_lock():
            cls._stat_reset_state.value = 1

    @classmethod
    def get_stat_reset_state(cls):
        with cls._stat_reset_state.get_lock():
            return cls._stat_reset_state.value

    @classmethod
    def request_stat_read(cls):
        with cls._stat_read_state.get_lock():
            cls._stat_read_state.value = 1

    @classmethod
    def get_stat_read_state(cls):
        with cls._stat_read_state.get_lock():
            return cls._stat_read_state.value

    @classmethod
    def request_log_read(cls, id, frm, cnt):
        with cls._log_read_state.get_lock():
            cls._log_read_state.value = 1
        with cls._sensor_log_info.get_lock():
            cls._sensor_log_info[0] = id
            cls._sensor_log_info[1] = frm
            cls._sensor_log_info[2] = cnt
            cls._sensor_log_info[3] = 0

    @classmethod
    def get_log_read_state(cls):
        with cls._log_read_state.get_lock():
            return cls._log_read_state.value

    @classmethod
    def get_sensor_log_values(cls) -> tuple:
        with cls._sensor_log_values.get_lock() and cls._sensor_log_info.get_lock() and cls._log_read_state.get_lock():
            if (cls._log_read_state.value == 4):
                return cls._sensor_log_values[0:cls._sensor_log_info[3]]
        return []
