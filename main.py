import pygame
from interface import EnergyVisualizerApp

def main():
    pygame.init()
    pygame.display.set_caption("Energy Visualizer (Starter)")
    # You can tweak window size here
    screen = pygame.display.set_mode((1280, 800))
    app = EnergyVisualizerApp(screen, grid_w=40, grid_h=25, cell_px=24)
    app.run()
    pygame.quit()

if __name__ == "__main__":
    main()