"""
Create a modern Twenty Dots logo with all game colors.
"""
from PIL import Image, ImageDraw, ImageFont
import math

# Logo dimensions
width = 512
height = 512

# Create image with transparent background
img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Game colors
colors = {
    'red': (231, 76, 60),
    'blue': (52, 152, 219),
    'green': (46, 204, 113),
    'purple': (155, 89, 182),
    'yellow': (241, 196, 15)
}

# Background circle (dark gradient effect)
center_x, center_y = width // 2, height // 2
bg_radius = 240

# Draw background circle with subtle gradient
for i in range(bg_radius, 0, -2):
    alpha = int(255 * (i / bg_radius) * 0.15)
    color = (26, 26, 46, alpha)
    draw.ellipse([center_x - i, center_y - i, center_x + i, center_y + i], 
                 fill=color, outline=None)

# Draw outer ring with all colors
ring_thickness = 30
segments = 5
for i, (color_name, color_rgb) in enumerate(colors.items()):
    start_angle = (360 / segments) * i - 90
    end_angle = start_angle + (360 / segments) + 2  # +2 for slight overlap
    
    # Draw arc segment
    for thickness in range(ring_thickness):
        radius = 200 - thickness
        alpha = 255 - int(thickness * 3)  # Fade towards inside
        draw.arc([center_x - radius, center_y - radius, 
                  center_x + radius, center_y + radius],
                 start=start_angle, end=end_angle,
                 fill=(*color_rgb, alpha), width=3)

# Draw grid pattern of dots (6x6 like the game)
dot_grid_size = 6
grid_area = 280
grid_offset_x = center_x - grid_area // 2
grid_offset_y = center_y - grid_area // 2
dot_spacing = grid_area // (dot_grid_size + 1)

# Create interesting dot pattern
dot_pattern = [
    [2, 0, 1, 3, 0, 2],  # rows of color indices
    [1, 3, 0, 2, 1, 0],
    [0, 2, 4, 1, 3, 1],  # 4 = yellow (wild)
    [3, 1, 0, 2, 0, 3],
    [2, 0, 1, 0, 2, 1],
    [0, 3, 2, 1, 3, 0]
]

color_list = list(colors.values())

for row in range(dot_grid_size):
    for col in range(dot_grid_size):
        x = grid_offset_x + (col + 1) * dot_spacing
        y = grid_offset_y + (row + 1) * dot_spacing
        
        color_idx = dot_pattern[row][col]
        dot_color = color_list[color_idx]
        
        # Draw dot with glow effect
        dot_radius = 18
        
        # Outer glow
        for glow in range(8, 0, -1):
            alpha = int(100 * (glow / 8))
            draw.ellipse([x - dot_radius - glow, y - dot_radius - glow,
                         x + dot_radius + glow, y + dot_radius + glow],
                        fill=(*dot_color, alpha))
        
        # Main dot with gradient effect
        for r in range(dot_radius, 0, -1):
            brightness = 1.0 + (dot_radius - r) / dot_radius * 0.3
            bright_color = tuple(min(255, int(c * brightness)) for c in dot_color)
            draw.ellipse([x - r, y - r, x + r, y + r],
                        fill=bright_color)
        
        # Highlight
        highlight_offset = dot_radius // 3
        highlight_size = dot_radius // 2
        draw.ellipse([x - highlight_offset - highlight_size // 2,
                     y - highlight_offset - highlight_size // 2,
                     x - highlight_offset + highlight_size // 2,
                     y - highlight_offset + highlight_size // 2],
                    fill=(255, 255, 255, 180))

# Draw "20" in the center with stylized font
try:
    # Try to load a bold font, fall back to default if not available
    try:
        font_large = ImageFont.truetype("arialbd.ttf", 120)
        font_small = ImageFont.truetype("arial.ttf", 24)
    except:
        try:
            font_large = ImageFont.truetype("Arial Bold.ttf", 120)
            font_small = ImageFont.truetype("Arial.ttf", 24)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
except:
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()

# Draw "20" with rainbow gradient
text = "20"
# Get text bbox to center it
bbox = draw.textbbox((0, 0), text, font=font_large)
text_width = bbox[2] - bbox[0]
text_height = bbox[3] - bbox[1]
text_x = center_x - text_width // 2
text_y = center_y - text_height // 2 - 20

# Draw text shadow
for offset in range(5, 0, -1):
    draw.text((text_x + offset, text_y + offset), text, 
              fill=(0, 0, 0, 50), font=font_large)

# Draw main text with gradient (yellow to white)
draw.text((text_x, text_y), text, fill=(241, 196, 15, 255), font=font_large)

# Add "DOTS" text below
dots_text = "DOTS"
bbox = draw.textbbox((0, 0), dots_text, font=font_small)
dots_width = bbox[2] - bbox[0]
dots_x = center_x - dots_width // 2
dots_y = text_y + text_height + 10

draw.text((dots_x, dots_y), dots_text, fill=(255, 255, 255, 200), font=font_small)

# Save the logo
img.save('twenty_dots_logo.png', 'PNG')
print("Logo created successfully: twenty_dots_logo.png")

# Also create a smaller icon version (256x256)
icon = img.resize((256, 256), Image.Resampling.LANCZOS)
icon.save('twenty_dots_icon.png', 'PNG')
print("Icon created successfully: twenty_dots_icon.png")

# Create an even smaller version for taskbar (64x64)
taskbar_icon = img.resize((64, 64), Image.Resampling.LANCZOS)
taskbar_icon.save('twenty_dots_taskbar.png', 'PNG')
print("Taskbar icon created successfully: twenty_dots_taskbar.png")
