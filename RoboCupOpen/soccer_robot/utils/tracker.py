import soccer_robot.constants as con
from soccer_robot.mathf import mathf
from soccer_robot.mathf.vector2 import Vector2
from soccer_robot.utils.timer import Timer

import math

class Tracker:
    """Class for estimating the position of the robot"""

    def __init__(self):
        self.heatmap = [0]*len(con.TRACKER_HEATMAP_POINTS)
        self.position_since_goal = Vector2(0, 0)
        self.velocity = Vector2(0, 0)
        self._timer = Timer()

    def update(self, heading, line, seen_line, see_goal, goal_angle, goal_dist, motors, lock):
        since_update = self._timer.get()/1000
        self._timer.reset()

        # Calculate robot velocity from motor speeds
        self.velocity = Vector2(0, 0)
        if not lock:
            self.velocity = mathf.motors_to_vel(motors)
            self.velocity.set_angle_magn(angle=self.velocity.get_angle()+heading)

        if see_goal: # make heatmap based on goal
            camera_goal_vec = Vector2(a=math.radians(goal_angle + heading), m=goal_dist)
            position = Vector2(*con.GOAL_POSITION) - camera_goal_vec
            position = Vector2(
                mathf.clamp(position.x, -con.FIELD_SIZE[0]/2, con.FIELD_SIZE[0]/2),
                mathf.clamp(position.y, -con.FIELD_SIZE[1]/2, con.FIELD_SIZE[1]/2)
            )

            for i, p in enumerate(con.TRACKER_HEATMAP_POINTS):
                robot_point_dist = (Vector2(*p)-position).get_magnitude()
                self.heatmap[i] = max(0, 1-(robot_point_dist/con.TRACKER_GOAL_SPOT_R))
        else: # shift the heatmap if distance is sufficient
            self.position_since_goal += self.velocity * since_update
            if self.position_since_goal.get_magnitude() >= con.TRACKER_MIN_MOVE:
                dx, dy = map(round, self.position_since_goal.normalized())
                dy = -dy
                new_heatmap = [0]*len(self.heatmap)
                for i, v in enumerate(self.heatmap):
                    x = i % con.TRACKER_HEATMAP_WIDTH
                    y = i // con.TRACKER_HEATMAP_WIDTH
                    ni = (y+dy) * con.TRACKER_HEATMAP_WIDTH + (x+dx)
                    if 0 <= (x+dx) < con.TRACKER_HEATMAP_WIDTH and 0 <= ni < len(self.heatmap):
                        new_heatmap[ni] = v
                self.heatmap = new_heatmap.copy()
                self.position_since_goal = Vector2(0, 0)

        # Add probabilities based on lines
        if seen_line:
            line_sign = con.TRACKER_LINE_SIGNS[round((line+heading) / 90) % 4]
            for i, signs in enumerate(con.TRACKER_HEATMAP_LINES):
                if line_sign in signs:
                    self.heatmap[i] += con.TRACKER_LINE_ADDEND
                    self.heatmap[i] *= con.TRACKER_LINE_MULTIPLIER

        # Normalize
        k = sum(self.heatmap)
        if k != 0:
            self.heatmap = list(map(lambda v: v/k, self.heatmap))
