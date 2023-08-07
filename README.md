# RoboCup Soccer Open

## Setup

### Install packages and libraries

```
sudo apt install python3-pip git i2c-tools python3-opencv python3-serial python3-websockets
```

```
sudo pip3 install Adafruit-Blinka adafruit-circuitpython-bno055 adafruit-extended-bus adafruit-circuitpython-ssd1306 pillow bluedot
```

### Enable software I2C and second UART, disable builtin Bluetooth

Add following lines to `/boot/config.txt`:

```
# Software i2c - custom
dtoverlay=i2c-gpio,bus=3

# Second and fifth UART - custom
dtoverlay=uart2
dtoverlay=uart5

# Uncomment to disable builtin bluetooth - custom
#dtoverlay=disable-bt
```

### Pairing robots

Pair using [bluedot manual](https://bluedot.readthedocs.io/en/latest/pairpipi.html).

### Camera

Obtain frames using [Picamera2](https://github.com/raspberrypi/picamera2).
