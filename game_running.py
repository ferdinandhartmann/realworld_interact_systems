# runner_emg.py
# Endless runner with jump/duck:
# - Keyboard: UP/SPACE = jump, DOWN = duck
# - EMG: flex -> jump (higher flex => higher jump); ext -> duck while active
# Toggle control mode at runtime with "M".

import math, random, sys
import pygame as pg
from game_input import KeyboardInput, RealEMGInput, SmoothedInput

WIDTH, HEIGHT = 800, 360
FPS = 100

GROUND_Y = 300
SCROLL_SPEED = 6.0

JUMP_BASE = 8       # base jump impulse
JUMP_BOOST = 2     # scaled by flex [0..1]
GRAVITY = 0.8 
AIR_DRAG = 0.99       # mild air damping
DUCK_SCALE = 0.5
EMG_JUMP_DEADZONE = 0.15
EMG_DUCK_THRESHOLD = 0.25
COYOTE_TIME = 120     # ms after leaving ground where jump is still allowed
OBSTACLE_EVERY = (900, 1500)  # ms range
player_w, player_h = 34, 60

FONT_NAME = "arial"

USE_EMG = False  # default: keyboard. Press "M" to toggle at runtime.


pg.mixer.init(frequency=44100, size=-16, channels=1)
# Load your sound effects
# jump_sound = pg.mixer.Sound("sounds/jump.wav")
# duck_sound = pg.mixer.Sound("sounds/duck.wav")
# hit_sound = pg.mixer.Sound("sounds/hit.wav")
# score_sound = pg.mixer.Sound("sounds/score.wav")

# Optional: adjust volume (0.0–1.0)
# jump_sound.set_volume(0.4)
# duck_sound.set_volume(0.3)
# hit_sound.set_volume(0.5)
# score_sound.set_volume(0.3)


import numpy as np
import pygame as pg

pg.mixer.init(frequency=44100, size=-16, channels=1)
SAMPLE_RATE = 44100

def tone(freq=440, dur=0.15, vol=0.5):
    """Generate a simple sine-wave tone and return as pygame Sound."""
    n = int(SAMPLE_RATE * dur)
    t = np.linspace(0, dur, n, False)
    wave = np.sin(2 * np.pi * freq * t)
    audio = (wave * (2**15 - 1) * vol).astype(np.int16)
    return pg.sndarray.make_sound(audio)

# Pre-generate sounds
jump_sound  = tone(900, 0.2, 0.2)
duck_sound  = tone(400, 0.22, 0.34)
hit_sound   = tone(200, 0.15, 0.56)
score_sound = tone(1000, 0.12, 0.4)




def draw_text(surf, text, size, x, y, color=(255,255,255)):
    font = pg.font.SysFont(FONT_NAME, size, bold=True)
    img = font.render(text, True, color)
    rect = img.get_rect()
    rect.topleft = (x,y)
    surf.blit(img, rect)

def make_obstacle():
    kind = random.choice(["small", "tall", "wide", "overhead"])

    if kind == "small":
        rect = pg.Rect(WIDTH + 30, GROUND_Y - 30, 26, 30)      # jump over
    elif kind == "tall":
        rect = pg.Rect(WIDTH + 30, GROUND_Y - 50, 28, 50)      # jump over
    elif kind == "wide":
        rect = pg.Rect(WIDTH + 30, GROUND_Y - 35, 60, 35)      # jump over
    elif kind == "overhead":
        height = 40
        y_top = GROUND_Y - player_h  - 20  # hangs above player
        rect = pg.Rect(WIDTH + 40, y_top, 60, height)          # duck under
    return rect


def main():
    global USE_EMG
    pg.init()
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    pg.display.set_caption("Runner EMG")
    clock = pg.time.Clock()

    # Input
    kb = KeyboardInput(pg)
    real = RealEMGInput()
    input_src = SmoothedInput(kb if not USE_EMG else real, alpha=0.25, deadzone=0.05)

    # Player
    player = pg.Rect(120, GROUND_Y - player_h, player_w, player_h)
    player_y = float(player.bottom)  # use float for vertical position
    vy = 0.0
    ducking = False
    on_ground = True
    last_on_ground_ms = pg.time.get_ticks()

    # World
    obstacles = []
    # next_obstacle_ms = pg.time.get_ticks() + random.randint(*OBSTACLE_EVERY)
    next_obstacle_ms = pg.time.get_ticks() + 1000  # start after 1s
    now = pg.time.get_ticks()
    score = 0
    alive = True

    while True:
        dt = clock.tick(FPS)
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_m:
                    USE_EMG = not USE_EMG
                    input_src = SmoothedInput(
                        kb if not USE_EMG else real, alpha=0.25, deadzone=0.05
                    )
        
        # --- Obstacle spawning ---
        now = pg.time.get_ticks()

        if alive and now >= next_obstacle_ms:
            obstacles.append(make_obstacle())

            # choose a random time (in milliseconds) until the next spawn
            next_obstacle_ms = now + random.randint(800, 1400)


        # Read inputs
        flex, ext = input_src.read()
        keys = pg.key.get_pressed()

        if not USE_EMG:
            request_jump = keys[pg.K_SPACE] or keys[pg.K_UP]
            request_duck = keys[pg.K_DOWN]
        else:
            request_jump = flex > EMG_JUMP_DEADZONE
            request_duck = ext > EMG_DUCK_THRESHOLD

        # --- Ground contact check ---
        if player_y >= GROUND_Y:
            on_ground = True
            player_y = GROUND_Y
            vy = 0.0
            last_on_ground_ms = pg.time.get_ticks()
        else:
            on_ground = False

        # --- Jump logic ---
        if request_jump:
            can_jump = on_ground or (pg.time.get_ticks() - last_on_ground_ms) <= COYOTE_TIME
            if can_jump:
                if USE_EMG:
                    impulse = JUMP_BASE + JUMP_BOOST * max(0.0, min(1.0, flex))
                else:
                    impulse = JUMP_BASE + 0.8 * JUMP_BOOST
                vy = -impulse
                on_ground = False
                jump_sound.play()

        # --- Ducking (only when grounded) ---
        if request_duck and on_ground and not ducking:
            duck_sound.play()
        ducking = bool(request_duck and on_ground)
        current_h = int(player_h * (DUCK_SCALE if ducking else 1.0))
        player.height = current_h

        # --- Physics integration ---
        vy += GRAVITY           # gravity = acceleration
        vy *= AIR_DRAG          # smooth drag
        player_y += vy          # integrate position

        # --- Clamp to ground ---
        if player_y > GROUND_Y:
            player_y = GROUND_Y
            vy = 0.0
            on_ground = True

        # --- Update rect position ---
        player.bottom = int(player_y)

        # --- Debug (optional) ---
        # print(f"pos={player_y:.2f}, vel={vy:.2f}, ground={on_ground}")

        # --- Obstacles ---
        now = pg.time.get_ticks()
        if now >= next_obstacle_ms and alive:
            obstacles.append(make_obstacle())
            next_obstacle_ms = now + random.randint(*OBSTACLE_EVERY)

        for ob in obstacles:
            ob.x -= int(SCROLL_SPEED)

        # Remove and score
        keep = []
        for ob in obstacles:
            if ob.right > 0:
                keep.append(ob)
            else:
                score += 1
                score_sound.play()
        obstacles = keep

        # --- Collisions ---
        if alive:
            for ob in obstacles:
                if player.colliderect(ob):
                    hit_sound.play()
                    alive = False
                    death_time = pg.time.get_ticks()
                    break
        else:
            # Auto-restart after 1.5 seconds
            if pg.time.get_ticks() - death_time > 1500:
                # Reset world
                obstacles = []
                score = 0
                alive = True
                player_y = GROUND_Y
                vy = 0.0
                on_ground = True
                next_obstacle_ms = pg.time.get_ticks() + 1000



        # Draw
        screen.fill((20, 24, 32))

        # Ground
        pg.draw.line(screen, (180,180,180), (0, GROUND_Y), (WIDTH, GROUND_Y), 2)
        # Frame number
        draw_text(screen, f"Frame: {pg.time.get_ticks() // (1000 // FPS)}", 18, WIDTH - 150, 8, (200, 200, 200))

        # Obstacles
        for ob in obstacles:
            pg.draw.rect(screen, (100, 200, 210), ob, border_radius=6)

        # Player
        pg.draw.rect(screen, (255, 230, 90) if alive else (180,80,80), player, border_radius=6)

        # HUD
        mode = "EMG" if USE_EMG else "Keyboard"
        draw_text(screen, f"Mode: {mode}  Score: {score}", 20, 10, 8)
        draw_text(screen, f"Flex:{flex:.2f} Ext:{ext:.2f}  (M to toggle)", 18, 10, 32, (180,180,200))
        if not alive:
            draw_text(screen, "Game Over - press M to toggle input or close window", 18, 10, 56, (255,150,150))

        pg.display.flip()

if __name__ == "__main__":
    main()

