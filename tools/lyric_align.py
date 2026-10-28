import numpy as np, subprocess

def flux_env(song, hop=800):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", song, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32); n = len(x) // hop
    S = np.log1p(np.abs(np.fft.rfft(x[: n * hop].reshape(n, hop) * np.hanning(hop), axis=1)) * 20)
    f = np.r_[0, np.maximum(S[1:] - S[:-1], 0).sum(axis=1)]
    return f / f.max(), hop / 16000

def fit_grid(song, sections, sig=0.12):
    """Fit a bar grid: line k of section s starts at off + (cumulative bars)*bar. Returns line start times."""
    f, dt = flux_env(song)
    # smooth for tolerance
    k = np.exp(-0.5 * (np.arange(-4, 5) * dt / sig) ** 2); fs = np.convolve(f, k / k.sum(), mode="same")
    best = None
    for beat in np.arange(0.78, 0.93, 0.0025):
        bar = 4 * beat
        for gap in (0, 1, 2):
            idx = []; c = 0
            for s in sections:
                for li in range(len(s)): idx.append(c); c += 1
                c += gap
            idx = np.array(idx)
            for off in np.arange(2.0, 14.0, 0.05):
                t = off + idx * bar
                if t[-1] + bar > len(f) * dt: continue
                sc = fs[(t / dt).astype(int)].sum()
                if best is None or sc > best[0]: best = (sc, beat, gap, off, t)
    return best


def fit_sections(song, sections):
    """Global bar grid, then refine each section's start and bar length (tempo can ease up on the 'faster' chorus).
    Returns a list of (start, end) per lyric line, flattened in order."""
    f, dt = flux_env(song)
    k = np.exp(-0.5 * (np.arange(-4, 5) * dt / 0.12) ** 2); fs = np.convolve(f, k / k.sum(), mode="same")
    sc, beat, gap, off, t = fit_grid(song, sections)
    bar = 4 * beat; total = len(f) * dt
    out = []; prev_end = 0.0; c = 0
    for s in sections:
        n = len(s); nominal = off + c * bar
        best = None
        for sh in np.arange(-2.0, 2.01, 0.05):
            for sc_ in np.arange(0.84, 1.121, 0.01):
                b = bar * sc_; st = nominal + sh
                if st < prev_end - 0.2 or st + n * b > total: continue
                ts = st + np.arange(n) * b
                score = fs[(ts / dt).astype(int)].sum() - 0.02 * abs(sh) - 0.5 * abs(sc_ - 1)
                if best is None or score > best[0]: best = (score, st, b)
        if best is None: best = (0, nominal, bar)
        _, st, b = best
        for i in range(n): out.append((st + i * b, st + (i + 1) * b - 0.12))
        prev_end = st + n * b; c += n + gap
    # last line (outro) gets a little extra time
    if len(out) > 1 and out[-1][0] < out[-2][1] + 0.1:
        st = out[-2][1] + 0.15; out[-1] = (st, st + 3.4)
    out[-1] = (out[-1][0], min(out[-1][1] + 1.2, total - 0.3))
    return out
