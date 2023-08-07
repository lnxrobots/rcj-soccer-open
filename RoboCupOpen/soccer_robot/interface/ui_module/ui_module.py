import soccer_robot.constants as con
from soccer_robot.module.module import Module
from .display import Display

import gpiozero
import multiprocessing as mp
import subprocess
import time
from ctypes import c_bool

BUTTON_MIN_PRESS_INTERVAL = 0.5

class UIModule(Module):
    """Module for showing data on display and handling button events"""

    module_name = "UIModule"

    @classmethod
    def init(cls, debug=True) -> None:
        super().init()
        cls._debug_mode = debug
        cls._display = Display()
        cls._status = mp.Array('c', bytearray([0 for i in range(con.UI_MAX_STATUS)]))
        cls._line_threshold = mp.Value('i', 0)
        cls._goalie = mp.Value(c_bool, False)
        cls._last_display_update = 0
        cls._last_wifi_fetch = 0
        cls._last_ip_fetch = 0
        cls._wifi_on = False
        cls._ip_addr = ''

        cls._button_one_status = mp.Value("b", True)
        cls._button_one_last_time = 0.0

    @classmethod
    def set_line_threshold(cls, thresh):
        with cls._line_threshold.get_lock():
            cls._line_threshold.value = thresh

    @classmethod
    def get_line_threshold(cls):
        with cls._line_threshold.get_lock():
            return cls._line_threshold.value

    @classmethod
    def set_goalie(cls, goalie):
        with cls._goalie.get_lock():
            cls._goalie.value = goalie

    @classmethod
    def get_goalie(cls):
        with cls._goalie.get_lock():
            return cls._goalie.value

    @classmethod
    def set_status(cls, status):
        if len(status) > con.UI_MAX_STATUS:
            status = status[:con.UI_MAX_STATUS]
        with cls._status.get_lock():
            cls._status.value = status.encode('utf-8')

    @classmethod
    def get_status(cls):
        with cls._status.get_lock():
            status = cls._status.value
        return status.decode('utf-8')

    @classmethod
    def get_button_one_status(cls) -> bool:
        return cls._button_one_status.value

    @classmethod
    def fetch_ip_addr(cls):
        cls._ip_addr = subprocess.check_output(['hostname', '-I']).decode('ascii').strip()

    @classmethod
    def fetch_wifi_state(cls):
        output = subprocess.check_output(['ifconfig', 'wlan0']).decode('utf-8').strip()
        cls._wifi_on = 'UP' in output.split('\n')[0]

    @classmethod
    def on_run(cls, _stop_flag):
        button_one = gpiozero.Button(con.BUTTON_MOTORS_PIN, pull_up = False, bounce_time = con.BUTTON_MOTORS_BOUNCE)

        def button_one_pressed():
            if time.time() - cls._button_one_last_time > BUTTON_MIN_PRESS_INTERVAL:
                cls._button_one_status.value = not cls._button_one_status.value
                cls._button_one_last_time = time.time()

        button_one.when_pressed = button_one_pressed

        while not _stop_flag.value:
            round_start = time.time()

            if round_start-cls._last_display_update >= 1/con.DISPLAY_FPS:
                cls._display.update(
                    cls._ip_addr, cls._wifi_on, cls._debug_mode,
                    cls.get_goalie(), cls.get_line_threshold(), cls.get_status()
                )
                cls._last_display_update = round_start

            if round_start-cls._last_ip_fetch >= con.UI_IP_INTERVAL:
                cls.fetch_ip_addr()
                cls._last_ip_fetch = round_start

            if round_start-cls._last_wifi_fetch >= con.UI_WIFI_INTERVAL:
                cls.fetch_wifi_state()
                cls._last_wifi_fetch = round_start

            minimal_delay = min(1/con.DISPLAY_FPS, con.UI_WIFI_INTERVAL)
            time.sleep(max(minimal_delay - (time.time()-round_start), 0))

        cls._display.clear()
