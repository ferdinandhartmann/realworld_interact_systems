import os, textwrap, json, pathlib
from turtle import mode
from typing import Tuple, Optional
import math, random, sys
import pygame as pg
from game_input import KeyboardInput, EMGInput, SmoothedInput, EEGBlinkInput

WIDTH, HEIGHT = 800, 1200
FPS = 100

BIRD_X = 160
GRAVITY = 0.18
FLAP_VEL = -7.0
PIPE_GAP = 450
PIPE_SPEED = 3.0
SPAWN_EVERY = 1500  # ms

FONT_NAME = "arial"

MODE = 2  # 0 = keyboard, 1 = EMG, 2 = EEG

EMG_FLAP_THRESHOLD = 0.35

pg.mixer.init(frequency=44100, size=-16, channels=1)
# Load your sound effects
SOUNDS_DIR = "game_sounds"

brass_fail_drops = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "brass_fail_drops.mp3"))
game_over = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "game_over.mp3"))
losing_horn = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "losing_horn.mp3"))
fail_sounds = [brass_fail_drops, game_over, losing_horn]

fall_down_whistle = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "fall_down_whistle.mp3"))

cartoon_jump = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "cartoon_jump.mp3"))
# cartoon_jump = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "point_lower.mp3"))

hitting_sandbag = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "hitting_sandbag.mp3"))

oha_ohh = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "oha_ohh.mp3"))
uh = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "uh.mp3"))
hit_sounds = [uh]

get_coin = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "get_coin.mp3"))
get_coin_low = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "get_coin_low.mp3"))
point_smooth_beep = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "point_smooth_beep.mp3"))
score_sounds = [point_smooth_beep]

levelup = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "levelup_trimmed.mp3"))
start = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "start.mp3"))

hitting_sandbag.set_volume(0.3)
point_smooth_beep.set_volume(0.3)
oha_ohh.set_volume(0.4)
losing_horn.set_volume(0.8)
cartoon_jump.set_volume(0.5)

def make_pipes():
    gap_y = random.randint(240, HEIGHT - 240)
    top = pg.Rect(WIDTH, 0, 120, gap_y - PIPE_GAP // 2)
    bottom = pg.Rect(WIDTH, gap_y + PIPE_GAP // 2, 120, HEIGHT - (gap_y + PIPE_GAP // 2))
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
    global MODE
    pg.init()
    screen = pg.display.set_mode((WIDTH, HEIGHT))

    # --- Show connecting screen ---
    font = pg.font.SysFont(FONT_NAME, 33, bold=False)
    # font2 = pg.font.SysFont(FONT_NAME, 25, bold=False)
    screen.fill((20, 24, 32))
    text = font.render("Connecting to BITalino Device...", True, (255, 255, 180))
    rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))
    # text2 = font2.render(
    #     "Please move your arm into the resting position ...", True, (255, 255, 180)
    # )
    # rect2 = text.get_rect(center=(WIDTH // 2 - 30, HEIGHT // 2 + 80))
    screen.blit(text, rect)
    # screen.blit(text2, rect2)
    pg.display.flip()

    pg.display.set_caption("Flappy Bird")
    clock = pg.time.Clock()

    # Input sources
    if MODE == 0:
        kb = KeyboardInput(pg)
    if MODE == 1:
        emg = EMGInput()
    if MODE == 2:
        eeg = EEGBlinkInput()

    input_src = (
        kb if MODE == 0 else SmoothedInput(emg) if MODE == 1 else eeg
    )
    bird = pg.Rect(BIRD_X, HEIGHT // 2, 56, 40)
    vel_y = 0.0

    pipes = []
    spawn_timer = pg.time.get_ticks()
    score = 0
    started = False
    running = True

    play_start_timer = 100 

    while running:
        dt = clock.tick(FPS)
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_m:
                    MODE = (MODE + 1) % 3
                    input_src = (
                        kb if MODE == 0 else (SmoothedInput(emg) if MODE == 1 else eeg)
                    )

                if MODE == 0 and (event.key in (pg.K_SPACE, pg.K_UP)):
                    vel_y = FLAP_VEL
                    cartoon_jump.play()
                    started = True

        if play_start_timer >= 1:
            play_start_timer += dt
            if play_start_timer >= 400:
                play_start_timer = 0
                start.play()

        # Read input
        if MODE == 1:
            flex, ext = input_src.read()
            if flex > EMG_FLAP_THRESHOLD:
                vel_y = FLAP_VEL
                cartoon_jump.play()
                started = True

        if MODE == 2:
            blink = eeg.read()
            if blink > 0.0:
                vel_y = FLAP_VEL
                cartoon_jump.play()
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

        # Score: when pipe just crosses bird_x
        for i in range(0, len(pipes), 2):
            if pipes[i].right < BIRD_X <= pipes[i].right + PIPE_SPEED:
                score += 1
                point_smooth_beep.play()

        # Remove off-screen pipes
        pipes = [p for p in pipes if p.right > 0]

        # Collisions
        if collide(bird, pipes):
            # Reset
            uh.play()
            bird = pg.Rect(BIRD_X, HEIGHT // 2, 56, 40)
            vel_y = 0.0
            pipes = []
            score = 0
            started = False
            spawn_timer = pg.time.get_ticks()
            play_start_timer = 1

        # Draw
        screen.fill((25, 25, 35))

        # Pipes
        for idx, p in enumerate(pipes):
            color = (50, 200, 90) if idx % 2 == 0 else (50, 200, 90)
            pg.draw.rect(screen, color, p)

        # Bird
        pg.draw.rect(screen, (255, 220, 0), bird, border_radius=12)

        # HUD
        mode_names = ["Keyboard", "EMG", "EEG Blink"]
        draw_text(screen, f"Mode: {mode_names[MODE]}  Score: {score}", 40, WIDTH // 2, 20)
        if MODE == 1:
            draw_text(screen, f"Flex:{flex:.2f} Ext:{ext:.2f}  (M to toggle)", 36, WIDTH // 2, 72, (180, 180, 200))

        pg.display.flip()
    pg.quit()
    sys.exit()

if __name__ == "__main__":
    main()
