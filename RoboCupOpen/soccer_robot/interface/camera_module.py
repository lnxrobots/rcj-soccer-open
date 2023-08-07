from soccer_robot.module.module import Module
from soccer_robot.interface.undercarriage_module import UndercarriageModule
from soccer_robot.logger.logger_module import LoggerModule
from soccer_robot.utils.timer import Timer

import soccer_robot.constants as con

from picamera2 import Picamera2
import cv2
import numpy

import multiprocessing
from multiprocessing import shared_memory
import os
import time

class CameraModule(Module):
    module_name = "CameraModule"

    @classmethod
    def init(cls, debug=True) -> None:
        super().init()

        cls._ball_position = multiprocessing.Array("f", [-1, -1, 0, 0])
        cls._goal_position = multiprocessing.Array("f", [-1, -1, 0, 0])

        cls._ball_color_bounds = multiprocessing.Array("i", [0] * 6)
        cls._goal_color_bounds = multiprocessing.Array("i", [0] * 6)
        cls._vertical_crop_01 = multiprocessing.Value("d", con.CAMERA_VERTICAL_CROP_01)
        cls._enable_goal_detection = multiprocessing.Value("b", True)

        cls._is_new_frame = multiprocessing.Value("b", False)
        cls._debug_mode = debug

        if cls._debug_mode:
            cls._frame_buffer = shared_memory.SharedMemory(create = True, size = con.CAMERA_FRAMEBUFFER_SIZE)
            cls._frame_buffer_size = multiprocessing.Value("i", 0)
            cls._frame_buffer_lock = multiprocessing.Lock()

    @classmethod
    def on_run(cls, stop_flag) -> None:
        # Set libcamera log level to errors only
        os.environ["LIBCAMERA_LOG_LEVELS"] = "3"

        tuning = None
        if con.CAMERA_TUNING_FILE:
            tuning = Picamera2.load_tuning_file(os.path.join(os.getcwd(), con.CAMERA_TUNING_FILE))

        try:
            camera = Picamera2(tuning=tuning)
        except Exception as e:
            LoggerModule.log_error("Failed to init camera, PiCamera is not connected")
            return

        camera_config = camera.create_video_configuration(
            main={"format": "RGB888", "size": (con.CAMERA_WIDTH, con.CAMERA_HEIGHT)},
            raw={"size": con.CAMERA_RAW_SIZE},
            controls={"FrameDurationLimits": (int(10 ** 6 / con.CAMERA_FPS), int(10 ** 6 / con.CAMERA_FPS))}
        )
        camera.configure(camera_config)
        camera.set_controls({"AwbEnable": False})
        camera.start()

        cv2.setUseOptimized(True)

        # TODO: Load boundaries from file

        cls.is_new_raw_frame = False

        last_store_time = 0
        last_frame_time = time.time()

        # Obtain frame from camera
        job = camera.capture_array(signal_function = cls._on_frame_captured)
        while not stop_flag.value:
            current_time = time.time()

            if time.time() - last_frame_time > 2:
                LoggerModule.log_error("Camera capturing failed, restarting ...")


                LoggerModule.log_info("Stopping")

                camera.close()

                LoggerModule.log_info("Stopped")

                time.sleep(1)

                LoggerModule.log_info("Reiniting")

                try:
                    camera = Picamera2(tuning=tuning)
                except Exception as e:
                    LoggerModule.log_error("Failed to init camera, PiCamera is not connected")
                    return

                camera_config = camera.create_video_configuration(
                    main={"format": "RGB888", "size": (con.CAMERA_WIDTH, con.CAMERA_HEIGHT)},
                    raw={"size": con.CAMERA_RAW_SIZE},
                    controls={"FrameDurationLimits": (int(10 ** 6 / con.CAMERA_FPS), int(10 ** 6 / con.CAMERA_FPS))}
                )
                camera.configure(camera_config)
                camera.set_controls({"AwbEnable": False})
                camera.start()

                LoggerModule.log_info("reinited")

                job = camera.capture_array(signal_function = cls._on_frame_captured)
                last_frame_time = time.time()


            if cls.is_new_raw_frame:
                cls.is_new_raw_frame = False
                last_frame_time = time.time()

                raw_frame = camera.wait(job)

                job = camera.capture_array(signal_function = cls._on_frame_captured)

                # Convert BGR to HSV
                cropped_frame = raw_frame[int(con.CAMERA_HEIGHT * cls.get_vertical_crop()) : con.CAMERA_HEIGHT, 0 : con.CAMERA_WIDTH]
                hsv = cv2.cvtColor(cropped_frame, cv2.COLOR_BGR2HSV)

                # Draw crop line
                #cv2.line(img = raw_frame, pt1 = (0, int(CAMERA_HEIGHT * cls._vertical_crop_01.value)), pt2 = (CAMERA_WIDTH, int(CAMERA_HEIGHT * cls._vertical_crop_01.value)), color = (0, 0, 255), thickness = 2)


                #LoggerModule.log_robot_data(str(bounding_box_timer.get()) + " " + str(ball_bounding_box[2] * ball_bounding_box[3]))
                #LoggerModule.log_debug(bounding_box_timer.get())

                #cv2.rectangle(raw_frame, (goal_x, goal_y), (goal_x + goal_w, goal_y + goal_h), (0, 255, 0), 2)

                ball_bounding_box = cls._calculate_bounding_box(hsv, cls._ball_color_bounds)
                with cls._ball_position.get_lock():
                    cls._ball_position[0:4] = list(ball_bounding_box)

                if (cls._enable_goal_detection.value):
                    goal_bounding_box = cls._calculate_bounding_box(hsv, cls._goal_color_bounds, True)
                    with cls._goal_position.get_lock():
                        cls._goal_position[0:4] = list(goal_bounding_box)
                else:
                    with cls._goal_position.get_lock():
                        cls._goal_position[0:4] = [-1, -1, 0, 0]

                # In debug_mode also encode and store the image to the shared memory to be later used by the visualizer
                """
                if cls._debug_mode and (current_time-last_store_time) >= VISUALIZER_MESSAGE_INTERVAL:
                    last_store_time = current_time
                    cls._store_image_in_frame_buffer(raw_frame)
                """
                if cls._debug_mode:
                    cls._store_image_in_frame_buffer(raw_frame)

        camera.stop()
        camera.close()

    @classmethod
    def on_stop(cls) -> None:
        # Clear the shared memory
        if cls._debug_mode:
            cls._frame_buffer.close()
            cls._frame_buffer.unlink()

    @classmethod
    def set_ball_color_bounderies(cls, minH: int, minS: int, minV: int, maxH: int, maxS: int, maxV: int) -> None:
        with cls._ball_color_bounds.get_lock():
            cls._ball_color_bounds[0] = minH
            cls._ball_color_bounds[1] = minS
            cls._ball_color_bounds[2] = minV
            cls._ball_color_bounds[3] = maxH
            cls._ball_color_bounds[4] = maxS
            cls._ball_color_bounds[5] = maxV

    @classmethod
    def set_goal_color_bounderies(cls, minH: int, minS: int, minV: int, maxH: int, maxS: int, maxV: int) -> None:
        with cls._goal_color_bounds.get_lock():
            cls._goal_color_bounds[0] = minH
            cls._goal_color_bounds[1] = minS
            cls._goal_color_bounds[2] = minV
            cls._goal_color_bounds[3] = maxH
            cls._goal_color_bounds[4] = maxS
            cls._goal_color_bounds[5] = maxV

    @classmethod
    def set_enable_goal(cls, enable_goal: bool) -> None:
        with cls._enable_goal_detection.get_lock():
            cls._enable_goal_detection.value = enable_goal

    # Returns tuple containing (frame_buffer memory adress, size of frame_buffer, lock)
    @classmethod
    def get_frame_buffer(cls) -> tuple:
        if cls._debug_mode:
            with cls._frame_buffer_size.get_lock():
                with cls._is_new_frame.get_lock():
                    cls._is_new_frame.value = False
                return (cls._frame_buffer, cls._frame_buffer_size.value, cls._frame_buffer_lock)
        else:
            LoggerModule.log_error("Cannot get frame_buffer, set DEBUG_MODE to True to enable storing frames in frame buffers")

    @classmethod
    def get_ball_position(cls) -> tuple:
        with cls._ball_position.get_lock():
            return cls._ball_position[0:4]

    @classmethod
    def get_goal_position(cls) -> tuple:
        with cls._goal_position.get_lock():
            return cls._goal_position[0:4]

    @classmethod
    def is_new_frame(cls) -> bool:
        with cls._is_new_frame.get_lock():
            return cls._is_new_frame.value

    @classmethod
    def get_vertical_crop(cls):
        with cls._vertical_crop_01.get_lock():
            return cls._vertical_crop_01.value

    @classmethod
    def _on_frame_captured(cls, raw_frame):
        cls.is_new_raw_frame = True

    @classmethod
    # X, Y is in the middle of bounding box, and all values are normalized between 0, 1
    # To get original the value multiple it with camera resolution
    def _calculate_bounding_box(cls, hsv_frame, color_bounderies, center_height=False):
        lower_boundery = numpy.array(color_bounderies[0:3])
        upper_boundery = numpy.array(color_bounderies[3:6])

        if (lower_boundery[0] > upper_boundery[0]):
            first_mask = cv2.inRange(hsv_frame, numpy.array((lower_boundery[0], lower_boundery[1], lower_boundery[2])), numpy.array((180, upper_boundery[1], upper_boundery[2])))
            second_mask = cv2.inRange(hsv_frame, numpy.array((0, lower_boundery[1], lower_boundery[2])), numpy.array((upper_boundery[0], upper_boundery[1], upper_boundery[2])))

            mask = cv2.bitwise_or(first_mask, second_mask)
        else:
            mask = cv2.inRange(hsv_frame, lower_boundery, upper_boundery)

        x, y, w, h = -1, -1, 0, 0
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        #cls._store_image_in_frame_buffer(second_mask)

        if contours:
            max_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(max_contour)

            if center_height:
                s = w*con.GOAL_HEIGHT_SAMPLE
                t = time.perf_counter()
                condition = (max_contour[:, :, 0] >= x+(w-s)/2)[:, 0] & (max_contour[:, :, 0] <= x+(w+s)/2)[:, 0]
                ys = max_contour[condition][:, 0, 1]
                upper, lower = ys[ys < y+h/2], ys[ys > y+h/2]
                if len(upper) and len(lower):
                    h = numpy.average(lower) - numpy.average(upper)

        if x == -1 or y == -1:
            return (-1, -1, 0, 0)

        return (int(x + w / 2) / con.CAMERA_WIDTH,
                (int(y + h / 2) + con.CAMERA_HEIGHT * cls.get_vertical_crop()) / con.CAMERA_HEIGHT,
                w / con.CAMERA_WIDTH,
                h / con.CAMERA_HEIGHT)


    @classmethod
    def _store_image_in_frame_buffer(cls, raw_frame_array) -> None:

        # Downscale the frame
        raw_frame_array = cv2.resize(raw_frame_array, (con.VISUALIZE_IMAGE_WIDTH, con.VISUALIZE_IMAGE_HEIGHT))

        # Encode the frame
        result, encoded_frame = cv2.imencode(".jpg", raw_frame_array, [int(cv2.IMWRITE_JPEG_QUALITY), con.CAMERA_ENCODE_QUALITY])

        if (not result):
            LoggerModule.log_warning("Failed to encode image")
            return

        if (encoded_frame.nbytes > con.CAMERA_FRAMEBUFFER_SIZE):
            LoggerModule.log_warning("Failed to store frame in the frame_buffer: frame buffer too small ({} > {}), try increasing frame_buffer size".format(encoded_frame.nbytes, con.CAMERA_FRAMEBUFFER_SIZE))
            return

        # Create a reference to frame_buffer and copy encoded_frame to it
        frame_buffer = numpy.ndarray(shape = encoded_frame.shape, dtype = encoded_frame.dtype, buffer = cls._frame_buffer.buf)

        with cls._frame_buffer_size.get_lock():
            cls._frame_buffer_size.value = encoded_frame.shape[0]

        with cls._frame_buffer_lock:
            frame_buffer[:] = encoded_frame[:]

        with cls._is_new_frame.get_lock():
            cls._is_new_frame.value = True
