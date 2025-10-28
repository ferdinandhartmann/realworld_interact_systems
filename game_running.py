# runner_emg.py
# Endless runner with jump/duck:
# - Keyboard: UP/SPACE = jump, DOWN = duck
# - EMG: flex -> jump (higher flex => higher jump); ext -> duck while active
# Toggle control mode at runtime with "M".

import math, random, sys
import pygame as pg
from game_input import KeyboardInput, EMGInput, SmoothedInput
import numpy as np
import pygame as pg
import os

WIDTH, HEIGHT = 1400, 750
FPS = 120

GROUND_Y = 600
SCROLL_SPEED = 6.0

JUMP_BASE = 11  # base jump impulse
JUMP_BOOST = 3.85  # scaled by flex [0..1]
JUMP_BOOST_2 = 1.5  # scaled by flex [0..1]
GRAVITY = 0.7
AIR_DRAG = 0.99 # mild air damping
DUCK_SCALE = 0.5
EMG_JUMP_DEADZONE = 0.5
EMG_DUCK_THRESHOLD = -0.09
ADDITIONAL_OFFSET = -0.15
OBSTACLE_EVERY = (650, 1300)  # ms range
player_w, player_h = 34, 60
MAX_JUMPS = 2

LEVEL_UP_THRESHOLD = 10

FONT_NAME = "arial"

USE_EMG = True


pg.mixer.init(frequency=44100, size=-16, channels=1)
# Load your sound effects
SOUNDS_DIR = "game_sounds"

brass_fail_drops = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "brass_fail_drops.mp3"))
game_over = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "game_over.mp3"))
losing_horn = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "losing_horn.mp3"))
fail_sounds = [brass_fail_drops, game_over, losing_horn]

fall_down_whistle = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "fall_down_whistle.mp3"))

# cartoon_jump = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "cartoon_jump.mp3"))
cartoon_jump = pg.mixer.Sound(os.path.join(SOUNDS_DIR, "point_lower.mp3"))

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


def draw_text(surf, text, size, x, y, color=(255, 255, 255)):
    font = pg.font.SysFont(FONT_NAME, size, bold=True)
    img = font.render(text, True, color)
    rect = img.get_rect()
    rect.topleft = (x, y)
    surf.blit(img, rect)


class Obstacle(pg.Rect):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hit = False


def make_obstacle():
    kind = random.choice(
        ["small", "tall", "wide", "overhead", "overhead_2", "overhead_higher"]
    )

    if kind == "small":
        width = 30
        height = 35
        rect = Obstacle(WIDTH + width, GROUND_Y - height, width, height)  # jump over
    elif kind == "tall":
        width = 30
        height = 60
        rect = Obstacle(WIDTH + width, GROUND_Y - height, width, height)  # jump over
    elif kind == "wide":
        width = 60
        height = 40
        rect = Obstacle(WIDTH + width, GROUND_Y - height, width, height)  # jump over
    elif kind == "overhead":
        width = 70
        height = 240
        y_top = GROUND_Y - player_h - 215  # hangs above player
        rect = Obstacle(WIDTH + width, y_top, width, height)  # duck under
    elif kind == "overhead_2":
        width = 35
        height = 70
        y_top = GROUND_Y - player_h - 60  # hangs above player
        rect = Obstacle(WIDTH + width, y_top, width, height)  # duck under
    elif kind == "overhead_higher":
        width = 250
        height = 40
        y_top = GROUND_Y - player_h - 120  # hangs above player
        rect = Obstacle(WIDTH + width / 10, y_top, width, height)  # duck under
    return rect


def calibrate_emg(screen, real_emg, duration=2.0):
    """Measure EMG rest offset for given duration (seconds)."""
    font = pg.font.SysFont(FONT_NAME, 30, bold=False)
    clock = pg.time.Clock()
    samples = []
    ext_vector = []

    start_time = pg.time.get_ticks()
    while (pg.time.get_ticks() - start_time) < duration * 1000:
        for event in pg.event.get():  # allow quitting during calibration
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()

        screen.fill((20, 24, 32))
        text = font.render(
            "Please stay in resting position. Calibrating offsets...", True, (230, 230, 160)
        )
        rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        screen.blit(text, rect)

        # --- countdown ---
        elapsed = (pg.time.get_ticks() - start_time) / 1000
        remaining = max(0, duration - elapsed)
        countdown_text = font.render(f"{remaining:.1f} s", True, (255, 255, 180))
        countdown_rect = countdown_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40))
        screen.blit(countdown_text, countdown_rect)

        # --- collect EMG data ---
        ratio = real_emg.read()
        samples.append(ratio)
        ext = real_emg.get_ext_std()
        ext_vector.append(ext)

        pg.display.flip()
        clock.tick(60)

    # --- compute baseline offset ---
    offset = float(np.mean(samples))
    real_emg.boost_ext_threshold = float(np.mean(ext_vector)) * 1.5
    print(f"✅ EMG baseline offset calibrated: {offset:.3f}")
    print(f"✅ EMG ext std threshold calibrated: {real_emg.boost_ext_threshold:.6f}")
    return offset


def main():
    global USE_EMG, _jump_base, _jump_boost, _jump_boost_2, SCROLL_SPEED, OBSTACLE_EVERY
    pg.init()
    screen = pg.display.set_mode((WIDTH, HEIGHT))

    # --- Show connecting screen ---
    font = pg.font.SysFont(FONT_NAME, 33, bold=False)
    font2 = pg.font.SysFont(FONT_NAME, 25, bold=False)
    screen.fill((20, 24, 32))
    text = font.render("Connecting to BITalino Device...", True, (255, 255, 180))
    rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40))
    text2 = font2.render("Please move your arm into the resting position ...", True, (255, 255, 180))
    rect2 = text.get_rect(center=(WIDTH // 2 -30, HEIGHT // 2 + 80))
    screen.blit(text, rect)
    screen.blit(text2, rect2)
    pg.display.flip()

    pg.display.set_caption("Runner EMG")
    clock = pg.time.Clock()

    real = None
    
    # Input
    kb = KeyboardInput(pg)
    if USE_EMG:
        real = EMGInput()
    input_src = kb if not USE_EMG else SmoothedInput(real)

    # --- Calibration phase ---
    if USE_EMG:
        EMG_OFFSET = calibrate_emg(screen, real)
        input_src = SmoothedInput(real)
        input_src.offset = EMG_OFFSET + ADDITIONAL_OFFSET
    else:
        input_src = kb

    # Player
    player = pg.Rect(120, GROUND_Y - player_h, player_w, player_h)
    player_y = float(player.bottom)  # use float for vertical position
    vy = 0.0
    ducking = False
    on_ground = True
    last_on_ground_ms = pg.time.get_ticks()
    jumps_remaining = MAX_JUMPS

    _jump_base = JUMP_BASE
    _jump_boost = JUMP_BOOST
    _jump_boost_2 = JUMP_BOOST_2

    # Add a variable to track player lives
    player_lives = 3

    # Add a cooldown timer for hit indication
    hit_cooldown = 0

    level_up_trigger = False

    # Add a variable to track the number of consecutive obstacles passed
    consecutive_obstacles = 0
    player_scale = 1.0

    # Add variables for squish effect
    squish_timer = 0
    SQUISH_DURATION = 110  # milliseconds
    SQUISH_AMOUNT = 0.25 # percentage of squish

    # World
    obstacles = []
    # next_obstacle_ms = pg.time.get_ticks() + random.randint(*OBSTACLE_EVERY)
    next_obstacle_ms = pg.time.get_ticks() + 1000  # start after 1s
    now = pg.time.get_ticks()
    score = 0
    alive = True

    start.play()

    play_faster_levelup_1 = True
    play_faster_levelup_2 = True

    while True:
        dt = clock.tick(FPS)
        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_m:  # check for mode toggle key
                    USE_EMG = not USE_EMG
                    input_src = kb if not USE_EMG else SmoothedInput(real)
                    start.play()

        now = pg.time.get_ticks()

        if score > 20 and alive:
            SCROLL_SPEED = 7.5
            OBSTACLE_EVERY = (500, 1000)
            if play_faster_levelup_1:
                levelup.play()
                play_faster_levelup_1 = False
        if score > 30 and alive:
            SCROLL_SPEED = 8.0
            OBSTACLE_EVERY = (400, 800)
            if play_faster_levelup_2:
                levelup.play()
                play_faster_levelup_2 = False

        # Read inputs
        ratio = input_src.read()
        keys = pg.key.get_pressed()

        if not USE_EMG:
            request_jump = keys[pg.K_SPACE] or keys[pg.K_UP]
            request_duck = keys[pg.K_DOWN]
        else:
            request_jump = ratio > EMG_JUMP_DEADZONE
            request_duck = ratio < EMG_DUCK_THRESHOLD

        # --- Ground contact check ---
        if player_y >= GROUND_Y:
            on_ground = True
            player_y = GROUND_Y
            vy = 0.0
            jumps_remaining = MAX_JUMPS
            last_on_ground_ms = pg.time.get_ticks()
        else:
            on_ground = False

        # --- Jump logic ---

        # --- Track rising edge of jump ---
        if "prev_jump" not in locals():
            prev_jump = False
        just_pressed_jump = request_jump and not prev_jump
        prev_jump = request_jump

        # --- Jump logic (with double jump) ---
        if just_pressed_jump:
            if jumps_remaining > 0:
                # Trigger squish effect on jump
                # squish_timer = SQUISH_DURATION
                if USE_EMG:
                    impulse = _jump_base + (
                        _jump_boost if jumps_remaining == 2 else _jump_boost_2
                    ) * max(0.0, ratio)
                else:
                    impulse = _jump_base + 1.5 * (
                        _jump_boost if jumps_remaining == 2 else _jump_boost_2
                    )

                vy = -impulse
                on_ground = False
                jumps_remaining -= 1
                cartoon_jump.play()

        # --- Ducking (only when grounded) ---
        if request_duck and on_ground and not ducking:
            hitting_sandbag.play()
        ducking = bool(request_duck and on_ground)
        current_h = int(player_h * player_scale * (DUCK_SCALE if ducking else 1.0))
        player.height = current_h

        # --- Physics integration ---
        vy += GRAVITY  # gravity = acceleration
        vy *= AIR_DRAG  # smooth drag
        player_y += vy  # integrate position

        # --- Clamp to ground ---
        if player_y > GROUND_Y:
            player_y = GROUND_Y
            if not on_ground:  # Trigger squish effect on landing
                squish_timer = SQUISH_DURATION
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

        # # Mark obstacles as hit to prevent multiple collisions
        # for ob in obstacles:
        #     ob.hit = False

        # Remove and score
        keep = []
        for ob in obstacles:
            if ob.right > 0:
                keep.append(ob)
            elif ob.left < player.left and not ob.hit:
                score += 1
                consecutive_obstacles += 1  # Increment consecutive obstacles passed
                random.choice(score_sounds).play()
        obstacles = keep

        # Check for level up condition
        if consecutive_obstacles >= LEVEL_UP_THRESHOLD and not level_up_trigger:
            level_up_trigger = True
            # player_scale = 0.5
            # player.height = int(player_h * player_scale)
            # player.bottom = GROUND_Y
            _jump_base = 16
            _jump_boost = 5  # Increase jump height significantly
            _jump_boost_2 = 4
            levelup.play()  # Play level up sound

        # Update hit cooldown timer
        if hit_cooldown > 0:
            hit_cooldown -= dt

        # --- Collisions ---
        alive = player_lives > 0

        if alive:
            for ob in obstacles:
                if player.colliderect(ob):
                    if (
                        player.bottom <= ob.top + 15
                    ): # Player lands on top of the obstacle
                        if vy > 0:
                            player_y = ob.top
                            vy = 0.0  # Reset vertical velocity
                            if not on_ground:
                                squish_timer = SQUISH_DURATION
                            on_ground = True
                            jumps_remaining = MAX_JUMPS  # Reset jumps
                    else:
                        if ob.hit == False:
                            ob.hit = True
                            random.choice(hit_sounds).play()
                            player_lives -= 1  # Decrement lives on collision
                            hit_cooldown = 500  # Set cooldown to 500ms
                            consecutive_obstacles = 0
                            level_up_trigger = False
                            # player.height = player_h
                            # player.bottom = GROUND_Y
                            _jump_base = JUMP_BASE
                            _jump_boost = JUMP_BOOST
                            _jump_boost_2 = JUMP_BOOST_2
                            if player_lives <= 0:
                                player.height = player_h 
                                alive = False
                                random.choice(fail_sounds).play()
                                death_time = pg.time.get_ticks()
                            break
        else:
            # Auto-restart after 1.5 seconds
            if pg.time.get_ticks() - death_time > 2000:
                # Reset world
                obstacles = []
                score = 0
                alive = True
                player_y = GROUND_Y
                vy = 0.0
                on_ground = True
                player_lives = 3
                consecutive_obstacles = 0
                level_up_trigger = False
                next_obstacle_ms = pg.time.get_ticks() + 800
                _jump_base = JUMP_BASE
                _jump_boost = JUMP_BOOST
                _jump_boost_2 = JUMP_BOOST_2
                player_scale = 1.0
                start.play()
                # player.height = player_h
                # player.bottom = GROUND_Y

        # Draw
        screen.fill((20, 24, 32))

        # Ground
        pg.draw.line(screen, (180, 180, 180), (0, GROUND_Y), (WIDTH, GROUND_Y), 2)
        # Frame number
        draw_text(
            screen,
            f"Frame: {pg.time.get_ticks() // (1000 // FPS)}",
            18,
            WIDTH - 150,
            8,
            (200, 200, 200),
        )

        # Obstacles
        for ob in obstacles:
            pg.draw.rect(screen, (100, 200, 210), ob, border_radius=6)




        if squish_timer > 0 and not request_duck:
            squish_factor = 1 - SQUISH_AMOUNT * (1 - math.cos(math.pi * (SQUISH_DURATION - squish_timer) / SQUISH_DURATION)) / 2
            squish_timer -= dt
            squished_height_pos = int(player_h * (1 - squish_factor))
            squished_height = int(player_h * squish_factor)
            player.bottom += squished_height_pos
            player.height = squished_height
        else:
            squish_factor = 1.0
            # player.height = player_h


        # Player
        player_color =  []
        if consecutive_obstacles >= LEVEL_UP_THRESHOLD:
            player_color = (255, 20, 147)
        elif alive and hit_cooldown <= 0:
            player_color = (255, 230, 90)
        else:
            player_color = (180, 80, 80)

        pg.draw.rect(
            screen,
            (player_color),
            player,
            border_radius=6,
        )

        # HUD
        mode = "EMG" if USE_EMG else "Keyboard"
        draw_text(screen, f"Mode: {mode}", 20, 10, 8)
        draw_text(
            screen,
            f"Score: {score}",
            40,
            600,
            180,
            (255, 255, 255),
        )
        if not alive:
            draw_text(
                screen,
                "Game Over - press M to toggle input or close window",
                35,
                230,
                250,
                (255, 150, 150),
            )
        if USE_EMG:
            # Draw horizontal bars for raw and smoothed ratios
            bar_x = 190
            bar_y = 105
            bar_width = 160
            bar_height = 20
            max_bar_width = 200

            lines_y_high = bar_y - 5
            lines_y_low = bar_y + bar_height + 5

            # Draw the zero line (horizontal, slightly extended above and below the bar)
            zero_line_x = bar_x
            pg.draw.line(
                screen,
                (255, 255, 255),
                (zero_line_x, lines_y_high),
                (zero_line_x, lines_y_low),
                2,
            )
            # Draw the EMG_JUMP_DEADZONE line
            jump_deadzone_y = int(EMG_JUMP_DEADZONE * bar_width)
            pg.draw.line(
                screen,
                (150, 150, 150),
                (zero_line_x + jump_deadzone_y, lines_y_high),
                (zero_line_x + jump_deadzone_y, lines_y_low),
                1,
            )

            # Draw the EMG_DUCK_THRESHOLD line
            duck_threshold_y = int(EMG_DUCK_THRESHOLD * bar_width)  #
            pg.draw.line(
                screen,
                (150, 150, 150),
                (zero_line_x + duck_threshold_y, lines_y_high),
                (zero_line_x + duck_threshold_y, lines_y_low),
                1,
            )
            # Draw the smoothed ratio bar
            bar_width_final = min(abs(int(ratio * bar_width)), max_bar_width)
            smoothed_ratio_color = (200, 200, 100)
            if ratio >= 0:
                pg.draw.rect(
                    screen,
                    smoothed_ratio_color,
                    (bar_x, bar_y, bar_width_final, bar_height),
                )
            else:
                pg.draw.rect(
                    screen,
                    smoothed_ratio_color,
                    (bar_x - bar_width_final, bar_y, bar_width_final, bar_height),
                )

            # Display the raw and smoothed ratio values
            draw_text(
                screen,
                f"Raw Ratio            :{input_src.src.ratio:.2f}",
                20,
                10,
                40,
                (200, 200, 100),
            )
            draw_text(
                screen, f"Smoothed Ratio: {ratio:.2f}", 20, 10, 65, (200, 200, 100)
            )

            # draw_text(screen, f"Jump Limit: {EMG_JUMP_DEADZONE:.2f}", 20, 250, 40, (200, 200, 100))
            # draw_text(
            #     screen,
            #     f"Duck Limit: {EMG_DUCK_THRESHOLD:.2f}",
            #     20,
            #     250,
            #     65,
            #     (200, 200, 100),
            # )

        draw_text(
            screen, f"Jumps Left: {jumps_remaining}", 20, 10, 130, (200, 200, 200)
        )
        # Display player lives on the screen
        lives_color = (
            (0, 255, 0)
            if player_lives == 3
            else (255, 255, 0) if player_lives == 2 else (255, 0, 0)
        )
        draw_text(screen, f"Lives: {player_lives}", 35, 600, 140, lives_color)

        # Display streak counter on the screen
        draw_text(
            screen, f"Streak: {consecutive_obstacles}", 20, 10, 160, (200, 200, 200)
        )

        pg.display.flip()


if __name__ == "__main__":
    main()
