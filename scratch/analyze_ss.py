from PIL import Image

img = Image.open("/home/jai/.gemini/antigravity-ide/brain/c09f66f0-abd6-44a0-b95b-92dcdfdab97c/desktop_transparent_live.png").convert("RGB")
w, h = img.size
black_pixels = 0
for y in range(h):
    for x in range(w):
        r, g, b = img.getpixel((x, y))
        if r < 5 and g < 5 and b < 5:
            black_pixels += 1

print(f"Total size: {w}x{h} ({w*h} pixels)")
print(f"Black pixels: {black_pixels} ({black_pixels / (w*h) * 100:.2f}%)")
