"""Bound memory before reading uploads or allocating dense chart grids."""
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_QUOTES = 20_000
MAX_SURFACE_CELLS = 100_000

def check_upload_size(size):
    if size > MAX_UPLOAD_BYTES:
        raise ValueError('CSV upload exceeds 5 MB. Split it into smaller snapshots.')

def check_surface_size(strikes, expiries):
    if strikes * expiries > MAX_SURFACE_CELLS:
        raise ValueError('Too many unique strikes and expiries for a dense surface. Upload one synchronized snapshot or fewer expiries (maximum 100,000 grid cells).')
