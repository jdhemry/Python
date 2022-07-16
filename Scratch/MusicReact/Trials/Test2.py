#! /usr/bin/python3

import pygame
from numpy.random import random, randint

WIDTH, HEIGHT = 800, 600


def main():

    pygame.init()
    pygame.display.set_caption("video noise")

    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    font = pygame.font.SysFont('Courier New, courier, monospace', 32, bold=True)

    running = True
    clock = pygame.time.Clock()
    dt = 0
    text = font.render('fps: ?', False, (255, 255, 0))

    # main loop
    while running:
        noise = randint(0, 255, (WIDTH, HEIGHT))
        pixels = pygame.surfarray.pixels3d(screen)
        for i in range(3):
            pixels[:, :, i] = noise
        del pixels
        # it makes sense to throttle the framerate (which is what the 30 in
        # clock.tick(30) achieves) because it is pointless to have a framerate
        # higher than the screen refresh rate (which is usually 60). To run at
        # full speed, remove the 30
        dt += clock.tick(30)
        # don't refresh the OSD more than once per sec.
        if dt > 1000:
            dt = 0
            text = font.render(f'fps: {clock.get_fps():.1f}', True, (255, 255, 0))
        screen.blit(text, (10, 10))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False


if __name__ == '__main__':
    main()

