# Game Archaeology — trajectory generator

This repository holds the generator that produces the game archive behind the
**Game Archaeology** challenge.

## Why the games are generated

An earlier build of this challenge drew its positions from the public
lichess.org January 2013 archive. That build was withdrawn: the released FEN is a
unique key into the archive, so matching a position back to its source game and
replaying the recorded moves recovers the labels outright. Measured on that
build, the lookup scored **99.2821 out of 100**, against a best honest model of
34.05. A rule in the problem statement forbidding the lookup does not fix a
dataset whose input *is* the answer's index.

The games here are therefore played rather than archived. No public corpus
contains them.

## Keying

Every synthetic player's style — blunder rate, evaluation noise, greed, king
aggression, pawn-push preference, centre preference, resignation threshold — is
derived from `HMAC-SHA256(secret, "player:<id>")`, and each game's move-level
randomness from `HMAC-SHA256(secret, "game:<gid>:<white>:<black>")`.

**The secret is not published.** Running this code produces *a* valid dataset; it
does not reproduce *the* dataset. That is deliberate: a published seed would let
anyone regenerate the withheld trajectories and read the answers straight off
them, which is the same failure the lookup exploited.

## Layout

| file | role |
| --- | --- |
| `selfplay.py` | move generation, evaluation, policy derivation, one game |
| `gen_archive.py` | player pools, pairings, parallel play, archive writing |

The labelling harness and grading metric that turn a finished game into its
released label and score are not part of this repository.

## Player pools

Train players are named `A00000…`, test players `B00000…`. The pools are
prefix-disjoint by construction, so no account can be learned in training and
scored in test. Any position reached by more than one trajectory is dropped from
both splits, so no released position carries contradictory labels and none
appears on both sides.

## Licence

Generator code: MIT. The generated archive and the released dataset are original
output of this code and are placed under **CC0 1.0**.
