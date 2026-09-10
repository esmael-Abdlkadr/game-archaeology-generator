"""Generate the private trajectory archive as player PAIRS, several games per pair.

Each case of the challenge is one pair of synthetic players and the final
positions of several games between them. Every player belongs to exactly one
pair; train pairs use the `A` prefix and test pairs the `B` prefix, so the pools
are disjoint by construction. Every draw is keyed to the withheld secret, so no
public archive contains these games.

    python dev/gen_archive_pairs.py
"""
import os, sys, time
from pathlib import Path
from multiprocessing import get_context

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'dev'))

TRAIN_PAIRS, TEST_PAIRS, GAMES_PER_PAIR = 32000, 20000, 5
OUT = ROOT / 'raw_gen_v3'
FILES = 'abcdefgh'
sp = None


def sq(i):
    return FILES[i % 8] + str(i // 8 + 1)


def one(job):
    gid, w, b, k = job
    r = sp.play(w, b, gid)
    if r is None:
        return None
    return (w, b, k, ' '.join(sq(f) + sq(t) + (p.lower() if p else '') for f, t, p in r['moves']))


def run(prefix, n_pairs, salt, path, workers):
    jobs = [(f'{salt}{i}_{k}', f'{prefix}{2 * i:05d}', f'{prefix}{2 * i + 1:05d}', k)
            for i in range(n_pairs) for k in range(GAMES_PER_PAIR)]
    t0, kept = time.time(), 0
    with open(path, 'w') as fh, get_context('fork').Pool(workers) as pool:
        for n, res in enumerate(pool.imap_unordered(one, jobs, chunksize=64)):
            if res is None:
                continue
            w, b, k, mv = res
            fh.write(f'[White "{w}"]\n[Black "{b}"]\n[Round "{k}"]\n{mv}\n\n')
            kept += 1
            if kept % 20000 == 0:
                print(f'  {path.name}: {kept} kept / {n + 1} played  {time.time() - t0:.0f}s', flush=True)
    print(f'{path.name}: {kept} games in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    os.environ.setdefault('ARCHAEO_SECRET', (ROOT / '.secret').read_text().strip())
    import selfplay
    sp = selfplay
    OUT.mkdir(exist_ok=True)
    workers = max(1, (os.cpu_count() or 4) - 1)
    print(f'workers {workers}', flush=True)
    run('A', TRAIN_PAIRS, 'trainpair', OUT / 'pool_train.txt', workers)
    run('B', TEST_PAIRS, 'testpair', OUT / 'pool_test.txt', workers)
