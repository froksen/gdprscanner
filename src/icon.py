from PIL import Image, ImageDraw, ImageFont

ICON_SIZE = 64
ICON_BG_COLOR = "#2563EB"
ICON_FG_COLOR = "#FFFFFF"


def create_icon_image() -> Image.Image:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw rounded rectangle as shield shape
    draw.rounded_rectangle(
        [(2, 2), (ICON_SIZE - 3, ICON_SIZE - 3)],
        radius=12,
        fill=ICON_BG_COLOR,
    )
    # Draw "G" glyph
    try:
        font = ImageFont.truetype("segoeuib.ttf", 32)
    except (OSError, IOError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "G", font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (ICON_SIZE - text_w) // 2
    y = (ICON_SIZE - text_h) // 2 - bbox[1]
    draw.text((x, y), "G", fill=ICON_FG_COLOR, font=font)
    return img
