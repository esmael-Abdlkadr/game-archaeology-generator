"""Generate the private trajectory archive.

Every game is played here, keyed to a secret that is never published, so a
released final position cannot be matched against lichess or any other public
archive.  Train and test players are drawn from prefix-disjoint pools, which
makes the split verifiable without any archive lookup.
"""
import os, sys, time
from pathlib import Path
from multiprocessing import Pool
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('ARCHAEO_SECRET', (ROOT / '.secret').read_text().strip())
sys.path.insert(0, str(ROOT / 'dev'))
import selfplay as sp

TRAIN_PLAYERS, TRAIN_GAMES, TRAIN_CAP = 22000, 64000, 6
TEST_PLAYERS, TEST_GAMES, TEST_CAP = 27000, 27000, 2
OUT = ROOT / 'raw_gen'
FILES = 'abcdefgh'


def sq(i):
    return FILES[i % 8] + str(i // 8 + 1)


def pairings(prefix, n_players, n_games, cap, salt):
    rng = np.random.default_rng(sp._keyed('pairings', salt) % (2 ** 32))
    slots = np.repeat(np.arange(n_players), cap)
    rng.shuffle(slots)
    out, used = [], 0
    while len(out) < n_games and used + 2 <= len(slots):
        a, b = int(slots[used]), int(slots[used + 1])
        used += 2
        if a == b:
            continue
        out.append((f'{prefix}{a:05d}', f'{prefix}{b:05d}'))
    return out


def one(job):
    gid, w, b = job
    r = sp.play(w, b, gid)
    if r is None:
        return None
    return (w, b, ' '.join(
        sq(f) + sq(t) + (p.lower() if p else '') for f, t, p in r['moves']))


def run(prefix, n_players, n_games, cap, salt, path, workers):
    jobs = [(f'{salt}{i}', w, b) for i, (w, b) in
            enumerate(pairings(prefix, n_players, n_games, cap, salt))]
    t0 = time.time()
    kept = 0
    with open(path, 'w') as fh, Pool(workers) as pool:
        for k, res in enumerate(pool.imap_unordered(one, jobs, chunksize=64)):
            if res is None:
                continue
            w, b, mv = res
            fh.write(f'[White "{w}"]\n[Black "{b}"]\n{mv}\n\n')
            kept += 1
            if kept % 5000 == 0:
                print(f'  {path.name}: {kept} kept / {k + 1} played  {time.time() - t0:.0f}s',
                      flush=True)
    print(f'{path.name}: {kept} games in {time.time() - t0:.0f}s', flush=True)
    return kept


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    workers = max(1, (os.cpu_count() or 4) - 1)
    print(f'workers {workers}', flush=True)
    run('A', TRAIN_PLAYERS, TRAIN_GAMES, TRAIN_CAP, 'trainpool', OUT / 'pool_train.txt', workers)
    run('B', TEST_PLAYERS, TEST_GAMES, TEST_CAP, 'testpool', OUT / 'pool_test.txt', workers)
