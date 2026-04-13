import pygame
import sys

pygame.init()

screen = pygame.display.set_mode((1280, 720))
pygame.display.set_caption("Projection test")

font = pygame.font.SysFont("Arial", 64)
clock = pygame.time.Clock()

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    screen.fill((0, 0, 0))
    pygame.draw.rect(screen, (0, 255, 0), (100, 100, 300, 200))
    pygame.draw.circle(screen, (255, 0, 0), (700, 300), 100)

    text = font.render("Projection test", True, (255, 255, 255))
    screen.blit(text, (100, 30))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()