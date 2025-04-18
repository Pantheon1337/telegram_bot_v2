from PIL import Image, ImageDraw, ImageFont
import os

# Создаем директорию для изображений, если её нет
os.makedirs("images", exist_ok=True)

# Создаем новое изображение
image = Image.new('RGB', (800, 800), color='white')
draw = ImageDraw.Draw(image)

# Добавляем текст
try:
    font = ImageFont.truetype("arial.ttf", 40)
except:
    font = ImageFont.load_default()

text = "Нет изображения"
text_bbox = draw.textbbox((0, 0), text, font=font)
text_width = text_bbox[2] - text_bbox[0]
text_height = text_bbox[3] - text_bbox[1]

x = (800 - text_width) // 2
y = (800 - text_height) // 2

draw.text((x, y), text, font=font, fill='black')

# Сохраняем изображение
image.save("images/default_product.jpg") 