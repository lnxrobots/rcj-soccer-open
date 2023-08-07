import math

class Vector2:
    def __init__(self, x: float = 0, y: float = 0, a: float = None, m: float = None) -> None:
        self.x = x
        self.y = y
        if not (a is None and m is None):
            self.set_angle_magn(a, m)

    def get_magnitude(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def set_angle_magn(self, angle: float = None, magn: float = None) -> None:
        a = angle if angle is not None else self.get_angle()
        m = magn if magn is not None else self.get_magnitude()
        self.x = m*math.sin(a)
        self.y = m*math.cos(a)

    def normalized(self) -> 'Vector2':
        magnitude: float = self.get_magnitude()
        return self / magnitude

    def get_angle(self) -> float:
        # Get angle in rad between -pi and pi
        rad = math.atan2(self.x, self.y)

        # Calculate angle between 0 and 2pi
        if rad < 0:
            rad += 2 * math.pi

        return rad

    @staticmethod
    def distance(firstVector2: 'Vector2', secondVector2: 'Vector2') -> float:
        difference: Vector2 = firstVector2 - secondVector2
        return difference.get_magnitude()

    def __add__(self, other: 'Vector2'):
        x = self.x + other.x
        y = self.y + other.y
        return Vector2(x, y)

    def __sub__(self, other: 'Vector2'):
        x = self.x - other.x
        y = self.y - other.y
        return Vector2(x, y)

    def __mul__(self, other: 'Vector2'):
        x = self.x * other.x
        y = self.y * other.y
        return Vector2(x, y)

    def __mul__(self, other: float):
        x = self.x * other
        y = self.y * other
        return Vector2(x, y)

    def __truediv__(self, other: 'Vector2'):
        x = self.x / other.x
        y = self.y / other.y
        return Vector2(x, y)

    def __truediv__(self, other: float):
        x = self.x / other
        y = self.y / other
        return Vector2(x, y)

    def __str__(self):
        return "({0}, {1})".format(self.x, self.y)

    def __iter__(self):
        return iter([self.x, self.y])

    def __eq__(self, other: 'Vector2'):
        return self.x == other.x and self.y == other.y

Vector2.zero = Vector2(0, 0)
Vector2.north = Vector2(0, 1)
