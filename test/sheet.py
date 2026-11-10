# Kontaktbogen aus den Standbildern von test/figuren.cjs.
# Aufruf: python test/sheet.py <ordner> "<muster>" <ausgabe.png> <spalten>
#   z. B.  python test/sheet.py out "man-*-side.png" test/screens/figuren/mann-side.png 6
import sys, os, glob
from PIL import Image, ImageDraw

d, pat, out, cols = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
fs = sorted(glob.glob(os.path.join(d, pat)))
ims = [Image.open(f).convert('RGB') for f in fs]
w, h = ims[0].size
w2, h2 = w // 2, h // 2
rows = (len(ims) + cols - 1) // cols
S = Image.new('RGB', (cols * w2, rows * (h2 + 14)), (60, 60, 60))
dr = ImageDraw.Draw(S)
for i, (f, im) in enumerate(zip(fs, ims)):
    x, y = (i % cols) * w2, (i // cols) * (h2 + 14)
    S.paste(im.resize((w2, h2)), (x, y + 14))
    name = os.path.basename(f)[:-4]
    dr.text((x + 3, y + 1), name.split('-', 1)[1], fill=(255, 255, 255))
S.save(out)
print(out, len(fs))
