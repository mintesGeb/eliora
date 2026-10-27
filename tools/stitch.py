import sys, numpy as np
from PIL import Image
top, bot, out = sys.argv[1:4]
a = np.asarray(Image.open(top).convert('RGB')).astype(np.float32)
b = np.asarray(Image.open(bot).convert('RGB')).astype(np.float32)
h = a.shape[0]
# find shift s so that b[0:h-s] == a[s:h]
best = min(range(20, 260), key=lambda s: np.mean(np.abs(a[s:h] - b[0:h-s])))
full = np.vstack([a, b[h-best:h]]).astype(np.uint8)
Image.fromarray(full).save(out, quality=95)
print(out, full.shape, 'shift', best)
