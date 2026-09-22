"""Generate LocalVoice's original, reproducible vector/raster icon (no remote service)."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1] / 'assets'
root.mkdir(exist_ok=True)
size = 1024
im = Image.new('RGBA', (size, size))
d = ImageDraw.Draw(im)
d.rounded_rectangle((30, 30, 994, 994), radius=230, fill='#101d2b')
d.rounded_rectangle((65, 65, 959, 959), radius=205, outline='#24485a', width=6)
# Speech bubble silhouette with a rhythmic voice waveform.
d.rounded_rectangle((194, 235, 830, 731), radius=175, fill='#1cc4ac')
d.polygon([(323, 680), (310, 823), (498, 709)], fill='#1cc4ac')
for x, height in [(326, 110), (419, 225), (512, 335), (605, 225), (698, 110)]:
    d.rounded_rectangle((x-24, 483-height//2, x+24, 483+height//2), radius=24, fill='#102936')
im.save(root / 'localvoice.png')
im.save(root / 'localvoice.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
(root / 'localvoice.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
<rect x="30" y="30" width="964" height="964" rx="230" fill="#101d2b"/>
<rect x="65" y="65" width="894" height="894" rx="205" fill="none" stroke="#24485a" stroke-width="6"/>
<rect x="194" y="235" width="636" height="496" rx="175" fill="#1cc4ac"/>
<path d="M323 680L310 823L498 709Z" fill="#1cc4ac"/>
<g stroke="#102936" stroke-width="48" stroke-linecap="round">
<path d="M326 452v62M419 395v176M512 340v286M605 395v176M698 452v62"/>
</g></svg>''', encoding='utf-8')
