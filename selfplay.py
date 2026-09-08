"""Private trajectory generator.

Defect 1 of the review: the released FEN was a unique key into the public
lichess archive, so replaying the matched game recovered the labels outright.
A rubric ban cannot fix that.  These trajectories are produced here, keyed to a
withheld secret, so no archive anywhere contains the game that made a position.
"""
import hashlib, hmac, os, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from prepare import (START, N_OFF, K_OFF, DIAG, ORTH, _on, _slide, _hops,
                     _attacks, _king, in_check, apply_move, VALUES)

SECRET = os.environ.get('ARCHAEO_SECRET', '').encode()
MAX_PLIES = 320
VAL = {'P': 100, 'N': 320, 'B': 330, 'R': 500, 'Q': 900, 'K': 0}
CENTRE = np.zeros(64)
for _sq in range(64):
    _r, _f = _sq // 8, _sq % 8
    CENTRE[_sq] = 10.0 - 2.5 * (abs(3.5 - _r) + abs(3.5 - _f))


def _keyed(*parts):
    msg = ':'.join(str(p) for p in parts).encode()
    return int.from_bytes(hmac.new(SECRET, msg, hashlib.sha256).digest()[:8], 'big')


def pawn_moves(board, i, white, ep):
    out = []
    step = 8 if white else -8
    one = i + step
    last = 7 if white else 0
    if _on(one) and board[one] == '.':
        out.append((one, 'Q' if one // 8 == last else ''))
        if one // 8 == last:
            out.append((one, 'N'))
        home = (i // 8 == 1) if white else (i // 8 == 6)
        two = i + 2 * step
        if home and _on(two) and board[two] == '.':
            out.append((two, ''))
    for dd in (step - 1, step + 1):
        t = i + dd
        if _on(t) and abs((t % 8) - (i % 8)) == 1:
            if (board[t] != '.' and board[t].isupper() != white) or t == ep:
                out.append((t, 'Q' if t // 8 == last else ''))
                if t // 8 == last:
                    out.append((t, 'N'))
    return out


def legal_moves(board, white, ep, cr):
    """Every legal (frm, to, promo) for the side to move."""
    moves = []
    for i, p in enumerate(board):
        if p == '.' or p.isupper() != white:
            continue
        u = p.upper()
        if u == 'P':
            cand = pawn_moves(board, i, white, ep)
        elif u == 'N':
            cand = [(t, '') for t in _hops(board, i, N_OFF, white)]
        elif u == 'K':
            cand = [(t, '') for t in _hops(board, i, K_OFF, white)]
        elif u == 'B':
            cand = [(t, '') for t in _slide(board, i, DIAG, white)]
        elif u == 'R':
            cand = [(t, '') for t in _slide(board, i, ORTH, white)]
        else:
            cand = [(t, '') for t in _slide(board, i, DIAG + ORTH, white)]
        for t, promo in cand:
            nb, _ = apply_move(board, i, t, promo, ep, white)
            if not in_check(nb, white):
                moves.append((i, t, promo))
    k = _king(board, white)
    home = 4 if white else 60
    if k == home and not _attacks(board, k, not white):
        for side, empty, through in (('K', (home + 1, home + 2), home + 1),
                                     ('Q', (home - 1, home - 2, home - 3), home - 1)):
            flag = side if white else side.lower()
            if not cr.get(flag):
                continue
            if any(board[s] != '.' for s in empty):
                continue
            if _attacks(board, through, not white):
                continue
            to = home + 2 if side == 'K' else home - 2
            nb, _ = apply_move(board, k, to, '', ep, white)
            if not in_check(nb, white):
                moves.append((k, to, ''))
    return moves


def update_cr(cr, board, frm, to):
    out = dict(cr)
    p = board[frm]
    if p == 'K':
        out['K'] = out['Q'] = False
    elif p == 'k':
        out['k'] = out['q'] = False
    for sq, flag in ((0, 'Q'), (7, 'K'), (56, 'q'), (63, 'k')):
        if frm == sq or to == sq:
            out[flag] = False
    return out


def material(board, white):
    return sum(VAL[c.upper()] for c in board if c != '.' and c.isupper() == white)


def insufficient(board):
    men = [c.upper() for c in board if c != '.' and c.upper() != 'K']
    if not men:
        return True
    return len(men) == 1 and men[0] in ('N', 'B')


def policy(pid):
    """A synthetic player's fixed style, derived from the withheld secret."""
    r = np.random.default_rng(_keyed('player', pid) % (2 ** 32))
    return dict(
        blunder=float(r.uniform(0.004, 0.10)),
        temp=float(r.uniform(4.0, 55.0)),
        sees_hang=float(r.uniform(0.35, 0.99)),
        greed=float(r.uniform(0.5, 2.0)),
        check_bonus=float(r.uniform(-10.0, 90.0)),
        push=float(r.uniform(0.0, 12.0)),
        centre=float(r.uniform(0.0, 3.0)),
        resign=float(r.uniform(300, 1600)),
    )


def _hangs(board, to, white):
    return _attacks(board, to, not white)


def score_move(board, frm, to, promo, white, ep, pol):
    nb, _ = apply_move(board, frm, to, promo, ep, white)
    s = (material(nb, white) - material(nb, not white)) * pol['greed']
    tgt = board[to]
    if tgt != '.':
        s += VAL[tgt.upper()] * (pol['greed'] - 1.0) * 0.2
    if in_check(nb, not white):
        s += pol['check_bonus']
    p = board[frm].upper()
    if p == 'P':
        rank = to // 8 if white else 7 - to // 8
        s += pol['push'] * rank
    if p in ('N', 'B', 'Q', 'P'):
        s += pol['centre'] * CENTRE[to]
    if promo:
        s += VAL[promo] * 0.5
    if np.random.random() < pol['sees_hang'] and _hangs(nb, to, white):
        s -= VAL[p] * 0.45
    return s, nb


def play(white_id, black_id, gid):
    rng = np.random.default_rng(_keyed('game', gid, white_id, black_id) % (2 ** 32))
    np.random.seed(int(rng.integers(0, 2 ** 31)))
    pols = {True: policy(white_id), False: policy(black_id)}
    board, white, ep = START[:], True, -1
    cr = {'K': True, 'Q': True, 'k': True, 'q': True}
    plies = checks = quiet = 0
    swing, played = [], []
    while plies < MAX_PLIES:
        moves = legal_moves(board, white, ep, cr)
        if not moves:
            break
        pol = pols[white]
        if rng.random() < pol['blunder']:
            frm, to, promo = moves[int(rng.integers(len(moves)))]
            nb, _ = apply_move(board, frm, to, promo, ep, white)
        else:
            scored = [score_move(board, f, t, pr, white, ep, pol) for f, t, pr in moves]
            vals = np.array([s for s, _ in scored]) + rng.normal(0, pol['temp'], len(scored))
            k = int(np.argmax(vals))
            frm, to, promo = moves[k]
            nb = scored[k][1]
        played.append((frm, to, promo))
        cap = board[to] != '.' or (board[frm].upper() == 'P' and to == ep)
        quiet = 0 if (cap or board[frm].upper() == 'P') else quiet + 1
        cr = update_cr(cr, board, frm, to)
        _, new_ep = apply_move(board, frm, to, promo, ep, white)
        board, ep = nb, new_ep
        white = not white
        plies += 1
        if in_check(board, white):
            checks += 1
        swing.append(material(board, True) - material(board, False))
        if quiet >= 100 or insufficient(board):
            break
        d = swing[-1] * (1 if not white else -1)
        if plies > 24 and d < -pols[white]['resign'] and rng.random() < 0.22:
            break
    if plies < 20:
        return None
    s = np.asarray(swing, dtype=float) / 100.0
    comeback = float(max((s - np.minimum.accumulate(s)).max(),
                         (np.maximum.accumulate(s) - s).max()))
    return dict(moves=played, board=board[:], white_to_move=white, ep=ep, cr=dict(cr),
                plies=plies, checks=checks, pressure=checks / plies,
                comeback=comeback,
                material=(material(board, True) + material(board, False)) / 100.0,
                white_id=white_id, black_id=black_id)
