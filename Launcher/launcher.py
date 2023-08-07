from gpiozero import Button

import subprocess
import time
import signal
import sys

from PIL import Image, ImageDraw
from adafruit_extended_bus import ExtendedI2C as I2C
import adafruit_ssd1306

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 32
I2C_BUS = 3
I2C_ADDR = 0x3c

WIFI_ICON_PATH = "assets/wifi.png"

# Init buttons and display
button1: Button
button2 = Button(22, pull_up = False)
button3: Button

i2c = I2C(I2C_BUS)
oled = adafruit_ssd1306.SSD1306_I2C(DISPLAY_WIDTH, DISPLAY_HEIGHT, i2c, addr = I2C_ADDR)

def get_wifi_state() -> bool:
    output = subprocess.check_output(['ifconfig', 'wlan0']).decode('utf-8').strip()
    return ('UP' in output.split('\n')[0])

def get_ssid() -> str:
    return subprocess.check_output(["iwgetid", "wlan0"]).decode('utf-8').strip().split("\"")[-2]

wifi_status = get_wifi_state()
current_goal = "blue"
robot_program_running = False
exit_code = None
shuting_down = False

wifi_icon = Image.open(WIFI_ICON_PATH)

robot_program: subprocess.Popen


def update_display():
    frame = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    draw = ImageDraw.Draw(frame)

    y = 0

    draw.text((0, y), "Goal: {}".format(current_goal), fill = 255)
    y += 10

    if (get_wifi_state()):
        frame.paste(wifi_icon, (128 - wifi_icon.width, 0))
        draw.text((0, y), "SSID: {}".format(get_ssid()), fill=255)
        y += 10

    if exit_code is not None:
        text = ""

        if (exit_code == 0):
            text = "Finished successfully"
        else:
            text = "Error ({})".format(exit_code)

        draw.text((0, y), text, fill=255)

    oled.image(frame.rotate(180))
    oled.show()


def unbind_buttons():
    button1.when_released = None
    button2.when_released = None
    button3.when_released = None
    button3.when_held = None


# BUTTON FUNCTIONS
def change_goal():
    global current_goal

    if current_goal == "blue":
        current_goal = "yellow"
    elif current_goal == "yellow":
        current_goal = "none"
    else:
        current_goal = "blue"

def launch_program():
    global robot_program, robot_program_running

    unbind_buttons()

    button1.close()
    button3.close()

    robot_program = subprocess.Popen(["python3", "../RoboCupOpen/robot.py", current_goal, str(wifi_status)], cwd = "../RoboCupOpen", stdout = subprocess.DEVNULL, stderr = subprocess.STDOUT)
    robot_program_running = True

    button2.when_pressed = terminate_program

def change_wifi_status():
    global wifi_status

    wifi_status = not wifi_status

    if (wifi_status):
        subprocess.call(["sudo", "ifconfig", "wlan0", "up"])
    else:
        subprocess.call(["sudo", "ifconfig", "wlan0", "down"])

def shut_down():
    global shuting_down
    shuting_down = True

    unbind_buttons()

    frame = Image.new("1", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    draw = ImageDraw.Draw(frame)
    draw.text((0, 0), "Shutting down", fill = 255)
    draw.text((0, 13), "See you later :)", fill = 255)
    oled.image(frame.rotate(180))
    oled.show()

    subprocess.call(["sudo", "shutdown", "now"])
    sys.exit()

def terminate_program():
    robot_program.send_signal(signal.SIGINT)




def bind_buttons():
    global button1, button3

    button1 = Button(10, pull_up = False)
    button3 = Button(27, pull_up = False, hold_time = 2)

    button1.when_released = change_goal
    button2.when_released = launch_program
    button3.when_released = change_wifi_status
    button3.when_held = shut_down


bind_buttons()

while True:
    if robot_program_running:
        if (robot_program.poll() is not None):
            exit_code = robot_program.poll()
            robot_program_running = False

            bind_buttons()
    else:
        if (not shuting_down):
            update_display()

    time.sleep(0.25)
