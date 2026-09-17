from PIL import ImageGrab
import os

img = ImageGrab.grab()
img.save("/home/jai/.gemini/antigravity-ide/brain/c09f66f0-abd6-44a0-b95b-92dcdfdab97c/desktop_transparent_pil.png")
print("Saved screenshot with PIL.")
