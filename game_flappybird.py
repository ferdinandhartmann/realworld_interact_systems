import os, textwrap, json, pathlib
from turtle import mode
from typing import Tuple, Optional
import math, random, sys
import pygame as pg
from game_input import KeyboardInput, EMGInput, SmoothedInput, EEGBlinkInput
import threading
import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets
import pyqtgraph as pygraph
import threading


WIDTH, HEIGHT = 800, 1200
FPS = 100

BIRD_X = 160
GRAVITY = 0.18
FLAP_VEL = -7.0
PIPE_GAP = 450
PIPE_SPEED = 3.0
SPAWN_EVERY = 1500  # ms
EEG_FS = 1000

FONT_NAME = "arial"

MODE = 2  # 0 = keyboard, 1 = EMG, 2 = EEG

EMG_FLAP_THRESHOLD = 0.35

EEG_THRESHOLD = 35.05
MAX_VISIBLE_TIME = 3.0  # seconds

#############################
#           SOUNDS
############################
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

############################## Plotting
THRESHOLD = 35.3

# --- PyQtGraph setup for live signal ---
app = QtWidgets.QApplication([])
plot_win = pygraph.GraphicsLayoutWidget(show=True, title="Live Signal Monitor")
plot = plot_win.addPlot(title="Signal (µV)")
plot.setYRange(30, 40)
plot.showGrid(x=True, y=True)
curve = plot.plot(pen="y")
threshold_line = pygraph.InfiniteLine(
    pos=THRESHOLD, angle=0, pen=pygraph.mkPen("r", width=2, style=QtCore.Qt.DashLine)
)
plot.addItem(threshold_line)

signal_buffer = np.zeros(300)
plot_lock = threading.Lock()

def update_plot(new_value):
    global signal_buffer
    with plot_lock:
        signal_buffer = np.roll(signal_buffer, -1)
        signal_buffer[-1] = new_value
        curve.setData(signal_buffer)


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


def main(eeg_input=None, screen=None):
    global MODE
    # pg.init()
    # screen = pg.display.set_mode((WIDTH, HEIGHT))

    # # --- Show connecting screen ---
    # font = pg.font.SysFont(FONT_NAME, 33, bold=False)
    # # font2 = pg.font.SysFont(FONT_NAME, 25, bold=False)
    # screen.fill((20, 24, 32))
    # text = font.render("Connecting to BITalino Device...", True, (255, 255, 180))
    # rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))
    # # text2 = font2.render(
    # #     "Please move your arm into the resting position ...", True, (255, 255, 180)
    # # )
    # # rect2 = text.get_rect(center=(WIDTH // 2 - 30, HEIGHT // 2 + 80))
    # screen.blit(text, rect)
    # # screen.blit(text2, rect2)
    # pg.display.flip()

    pg.display.set_caption("Flappy Bird")
    clock = pg.time.Clock()

    # Input sources
    if MODE == 0:
        kb = KeyboardInput(pg)
    if MODE == 1:
        emg = EMGInput()
    if MODE == 2:
        eeg = EEGBlinkInput() if eeg_input is None else eeg_input

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
            update_plot()  # adjust scaling

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

    # --- Create EEG plot window ---
    app = pygraph.mkQApp("EEG Plot")
    plot_win = pygraph.GraphicsLayoutWidget(show=True, title="EEG Live Data (µV)")
    plot_win.setGeometry(0, 500, 1000, 600)  # position next to game window
    plot = plot_win.addPlot(title="EEG Signal")
    plot.showGrid(x=True, y=True)
    plot.setYRange(34.5, 36)
    curve = plot.plot(pen="y")
    thresh_line = pygraph.InfiniteLine(
        pos=EEG_THRESHOLD,
        angle=0,
        pen=pygraph.mkPen("r", width=2, style=QtCore.Qt.DashLine),
    )
    plot.addItem(thresh_line)

    eeg_ref = None  # global reference to EEG reader

    # --- Run pygame + EEG in a thread ---
    def run_game():
        global eeg_ref
        os.environ["SDL_VIDEO_WINDOW_POS"] = "1000,200"
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

        eeg_ref = EEGBlinkInput()
        try:
            main(eeg_ref, screen)
        finally:
            if eeg_ref:
                eeg_ref.close()
            # quit the Qt app once game closes
            QtCore.QTimer.singleShot(100, app.quit)

    game_thread = threading.Thread(target=run_game, daemon=True)
    game_thread.start()

    # --- Plot update timer ---
    def update_plot():
        global eeg_ref
        if eeg_ref is None:
            return
        with eeg_ref.buffer_lock:
            data = eeg_ref.live_plot_buffer.copy()
            offset = (eeg_ref.total_samples - len(data)) / EEG_FS
        if data.size == 0:
            return
        t = offset + np.arange(len(data)) / EEG_FS
        curve.setData(t, data, pen="w")
        # print(f"Data size: {data.size}, Time range: {t[0]:.2f} to {t[-1]:.2f}")
        plot.setXRange(max(0, t[-1] - MAX_VISIBLE_TIME), t[-1])
        # print(f"Plot X range: {plot.viewRange()[0]}")
        # print(f"t last: {t[-1]:.2f}, t first: {t[0]:.2f}")

    timer = QtCore.QTimer()
    timer.timeout.connect(update_plot)
    timer.start(50)  # update every 50 ms

    # --- Run the Qt loop (main thread) ---
    app.exec_()
