from typing import Tuple, Optional

class InputSource:
    def read(self) -> Tuple[float, float]:
        """Return (flex, ext) in [0,1]. Override in subclasses."""
        return 0.0, 0.0

class KeyboardInput(InputSource):
    """
    Maps keyboard to pseudo-EMG:
      - Flex: SPACE or UP = 1.0 (press & hold)
      - Ext:  DOWN = 1.0 (press & hold)
    """
    def __init__(self, pygame):
        self.pg = pygame

    def read(self) -> Tuple[float, float]:
        keys = self.pg.key.get_pressed()
        flex = 1.0 if (keys[self.pg.K_SPACE] or keys[self.pg.K_UP]) else 0.0
        ext  = 1.0 if keys[self.pg.K_DOWN] else 0.0
        return flex, ext

class RealEMGInput(InputSource):
    """
    Skeleton for *real* EMG input. Replace `read()` with your acquisition code.
    Ensure you normalize to [0,1] (after rectification, filtering, smoothing).
    """
    def __init__(self):
        # Example: set up your serial/socket/device here.
        # self.dev = ...
        # self.flex_bias = 0.0
        # self.ext_bias  = 0.0
        pass

    def read(self) -> Tuple[float, float]:
        # >>> Replace this with your real EMG access <<<<
        # Example pseudo-code:
        # raw_flex = get_flex_channel_value()
        # raw_ext  = get_ext_channel_value()
        # flex = normalize(abs(raw_flex - self.flex_bias))
        # ext  = normalize(abs(raw_ext  - self.ext_bias))
        # return clamp(flex,0,1), clamp(ext,0,1)
        return 0.0, 0.0

class SmoothedInput(InputSource):
    """
    Wraps another InputSource and applies exponential smoothing & deadzones.
    """
    def __init__(self, source: InputSource, alpha: float = 0.25, deadzone: float = 0.05):
        self.src = source
        self.alpha = float(alpha)
        self.dead = float(deadzone)
        self.flex = 0.0
        self.ext  = 0.0

    def read(self) -> Tuple[float, float]:
        f, e = self.src.read()

        # clamp
        f = 0.0 if f < self.dead else max(0.0, min(1.0, f))
        e = 0.0 if e < self.dead else max(0.0, min(1.0, e))

        # smooth
        self.flex = self.alpha * f + (1 - self.alpha) * self.flex
        self.ext  = self.alpha * e + (1 - self.alpha) * self.ext
        return self.flex, self.ext
