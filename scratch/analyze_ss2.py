from PIL import Image

img = Image.open("/home/jai/.gemini/antigravity-ide/brain/c09f66f0-abd6-44a0-b95b-92dcdfdab97c/desktop_transparent_live.png").convert("RGB")
w, h = img.size
non_black_pixels = []
for y in range(0, h, 10):
    for x in range(0, w, 10):
        r, g, b = img.getpixel((x, y))
        if r > 10 or g > 10 or b > 10:
            non_black_pixels.append((x, y))

if non_black_pixels:
    xs = [p[0] for p in non_black_pixels]
    ys = [p[1] for p in non_black_pixels]
    print(f"Character bounding box roughly: X={min(xs)}-{max(xs)}, Y={min(ys)}-{max(ys)}")
else:
    print("No character pixels found.")
