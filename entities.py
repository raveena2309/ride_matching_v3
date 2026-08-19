"""
entities.py
============
Core data structures for the ride-matching system.
Every other module operates on these three classes.
"""

class Driver:
    """Represents a single driver in the fleet."""
    def __init__(self, id, x, y, idle_time=0, capacity=4):
        self.id = id
        self.x = x                        # latitude
        self.y = y                        # longitude
        self.idle_time = idle_time        # minutes since last drop-off
        self.capacity = capacity          # max passengers (pooling)
        self.current_passengers = []      # list of Passenger objects assigned
        self.zone_id = None               # filled in later by zone assignment

    def is_available(self):
        return len(self.current_passengers) < self.capacity

    def __repr__(self):
        return f"Driver({self.id}, pos=({self.x:.4f},{self.y:.4f}), idle={self.idle_time}m)"


class Passenger:
    """Represents a single ride request."""
    def __init__(self, id, x, y, dest, wait=0, demand=1, cancel_risk=1):
        self.id = id
        self.x = x                # pickup latitude
        self.y = y                # pickup longitude
        self.dest = dest          # (lat, lon) tuple for destination
        self.wait = wait          # minutes waited so far
        self.demand = demand      # local demand intensity score
        self.cancel_risk = cancel_risk  # cancellation probability proxy

    def __repr__(self):
        return f"Passenger({self.id}, pickup=({self.x:.4f},{self.y:.4f}), wait={self.wait}m)"


class Zone:
    """Represents a city zone/grid-cell used for demand-aware repositioning."""
    def __init__(self, id, center_x, center_y):
        self.id = id
        self.center = (center_x, center_y)

    def __repr__(self):
        return f"Zone({self.id}, center={self.center})"


if __name__ == "__main__":
    d = Driver(1, 21.1450, 79.0880, idle_time=5, capacity=3)
    p = Passenger(101, 21.1452, 79.0882, dest=(21.1500, 79.0900), wait=10, demand=3, cancel_risk=2)
    z = Zone(1, 21.1450, 79.0880)

    print(d)
    print(p)
    print(z)
    print("Driver available?", d.is_available())