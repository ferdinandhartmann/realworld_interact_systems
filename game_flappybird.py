# Create three Python game files with EMG/keyboard toggle input (pygame-based).

import os, textwrap, json, pathlib

# base = "/mnt/data"
# os.makedirs(base, exist_ok=True)

# emg_input_code = r'''
# emg_input.py
# Unified input layer for keyboard *or* EMG (flexor/extensor) signals.
# You can plug in your real EMG stream by implementing `RealEMGInput.read()`.
# '''

from typing import Tuple, Optional


# flappy_code = r'''
# flappy_emg.py
# Flappy Bird using pygame with dual control:
# - Keyboard: SPACE/UP to flap
# - EMG: flexor activation > threshold to flap
#
# Toggle control mode at runtime with "M". Shows current mode on screen.
# '''

import math, random, sys
import pygame as pg
from game_input import KeyboardInput, RealEMGInput, SmoothedInput

WIDTH, HEIGHT = 400, 600
FPS = 60

BIRD_X = 80
GRAVITY = 0.35
FLAP_VEL = -6.5
PIPE_GAP = 150
PIPE_SPEED = 3.0
SPAWN_EVERY = 1500  # ms

FONT_NAME = "arial"

USE_EMG = False  # default: keyboard. Press "M" to toggle at runtime.
EMG_FLAP_THRESHOLD = 0.35

def make_pipes():
    gap_y = random.randint(120, HEIGHT-120)
    top = pg.Rect(WIDTH, 0, 60, gap_y - PIPE_GAP//2)
    bottom = pg.Rect(WIDTH, gap_y + PIPE_GAP//2, 60, HEIGHT - (gap_y + PIPE_GAP//2))
    return top, bottom

def collide(bird_rect, pipes):
    for p in pipes:
        if bird_rect.colliderect(p):
            return True
    if bird_rect.bottom >= HEIGHT or bird_rect.top <= 0:
        return True
    return False

def draw_text(surf, text, size, x, y, color=(255,255,255)):
    font = pg.font.SysFont(FONT_NAME, size, bold=True)
    img = font.render(text, True, color)
    rect = img.get_rect()
    rect.midtop = (x,y)
    surf.blit(img, rect)

def main():
    global USE_EMG
    pg.init()
    screen = pg.display.set_mode((WIDTH, HEIGHT))
    pg.display.set_caption("Flappy EMG")
    clock = pg.time.Clock()

    # Input sources
    kb = KeyboardInput(pg)
    real = RealEMGInput()
    input_src = SmoothedInput(kb if not USE_EMG else real, alpha=0.3, deadzone=0.05)

    bird = pg.Rect(BIRD_X, HEIGHT//2, 28, 20)
    vel_y = 0.0

    pipes = []
    spawn_timer = pg.time.get_ticks()
    score = 0
    started = False
    running = True

    while running:
        dt = clock.tick(FPS)
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_m:
                    USE_EMG = not USE_EMG
                    input_src = SmoothedInput(kb if not USE_EMG else real, alpha=0.3, deadzone=0.05)
                if not USE_EMG and (event.key in (pg.K_SPACE, pg.K_UP)):
                    vel_y = FLAP_VEL
                    started = True

        # Read input
        flex, ext = input_src.read()
        if USE_EMG and flex > EMG_FLAP_THRESHOLD:
            vel_y = FLAP_VEL
            started = True

        if started:
            vel_y += GRAVITY
            bird.y += int(vel_y)

        # Spawn & move pipes
        now = pg.time.get_ticks()
        if now - spawn_timer > SPAWN_EVERY:
            pipes.extend(make_pipes())
            spawn_timer = now

        for p in pipes:
            p.x -= int(PIPE_SPEED)

        # Score: when a pipe pair passes bird
        # Pair handling: pipes list is [top, bottom, top, bottom, ...], count only top pipes
        for i in range(0, len(pipes), 2):
            if pipes[i].right == BIRD_X:  # rare exact, so do a range check
                score += 1
        # Better: when pipe just crosses bird_x
        for i in range(0, len(pipes), 2):
            if pipes[i].right < BIRD_X <= pipes[i].right + PIPE_SPEED:
                score += 1

        # Remove off-screen pipes
        pipes = [p for p in pipes if p.right > 0]

        # Collisions
        if collide(bird, pipes):
            # Reset
            bird = pg.Rect(BIRD_X, HEIGHT//2, 28, 20)
            vel_y = 0.0
            pipes = []
            score = 0
            started = False
            spawn_timer = pg.time.get_ticks()

        # Draw
        screen.fill((25, 25, 35))
        # Pipes
        for idx, p in enumerate(pipes):
            color = (50, 200, 90) if idx % 2 == 0 else (50, 200, 90)
            pg.draw.rect(screen, color, p)

        # Bird
        pg.draw.rect(screen, (255, 220, 0), bird, border_radius=6)

        # HUD
        mode = "EMG" if USE_EMG else "Keyboard"
        draw_text(screen, f"Mode: {mode}  Score: {score}", 20, WIDTH//2, 10)
        draw_text(screen, f"Flex:{flex:.2f} Ext:{ext:.2f}  (M to toggle)", 18, WIDTH//2, 36, (180,180,200))

        pg.display.flip()

    pg.quit()
    sys.exit()

if __name__ == "__main__":
    main()

