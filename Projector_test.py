import pygame
import sys

pygame.init()

# Change this if your projector is not display 1
PROJECTOR_DISPLAY_INDEX = 1

displays = pygame.display.get_desktop_sizes()
print("Detected displays:", displays)

if len(displays) <= PROJECTOR_DISPLAY_INDEX:
    print("Projector display not found.")
    pygame.quit()
    sys.exit()

proj_width, proj_height = displays[PROJECTOR_DISPLAY_INDEX]

# Open a borderless fullscreen window on the projector
screen = pygame.display.set_mode(
    (proj_width, proj_height),
    pygame.NOFRAME,
    display=PROJECTOR_DISPLAY_INDEX
)

pygame.display.set_caption("Projector Test")

font_big = pygame.font.SysFont("Arial", 64)
font_small = pygame.font.SysFont("Arial", 32)

clock = pygame.time.Clock()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

    screen.fill((0, 0, 0))  # black background

    # Draw some simple test graphics
    pygame.draw.rect(screen, (0, 255, 0), (200, 150, 300, 180), 0)
    pygame.draw.rect(screen, (255, 0, 0), (600, 150, 300, 180), 0)
    pygame.draw.circle(screen, (0, 0, 255), (500, 500), 100)

    text1 = font_big.render("Projection test", True, (255, 255, 255))
    text2 = font_small.render("Press ESC to quit", True, (200, 200, 200))

    screen.blit(text1, (200, 50))
    screen.blit(text2, (200, 700))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()