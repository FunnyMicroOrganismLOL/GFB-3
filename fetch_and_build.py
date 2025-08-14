#!/usr/bin/env python3

import os
import sys
import io
import subprocess
from collections import defaultdict

import requests
import chess.pgn

BOTS = [
    "SoggiestShrimp", "AttackKing_Bot", "PositionalAI", "mayhem23111",
    "InvinxibleFlxsh", "YoBot_v2", "VEER-OMEGA-BOT", "MaggiChess16",
    "NimsiluBot", "pangubot", "Loss-Not-Defined", "Alexnajax_Fan",
    "strain-on-veins", "BOTTYBADDY11", "ChampionKitten",
    "LeelaMultiPoss", "ToromBot",
    "NNUE_Drift", "Strain-On-Veins", "Yuki_1324"
]
MIN_RATING = 2375
MAX_PLIES = 24
MAX_GAMES_PER_BOT = 5000
MIN_FEN_GAMES = 3
SPEEDS = ["blitz", "rapid", "classical", "bullet", "ultraBullet", "correspondence"]
MASTER_PGN = "master_chess960_book.pgn"
API_BASE = "https://lichess.org"

def headers():
    token = os.getenv("TOKEN", "").strip()
    h = {"Accept": "application/x-chess-pgn"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h

def export_games(username):
    params = {
        "max": str(MAX_GAMES_PER_BOT),
        "perfType": "chess960",
        "rated": "true",
        "moves": "true",
        "opening": "true"
    }
    url = f"{API_BASE}/api/games/user/{username}.pgn"
    r = requests.get(url, params=params, headers=headers(), stream=True)
    r.raise_for_status()
    return r.text

def parse_pgn_stream(pgn_text):
    buf = io.StringIO(pgn_text)
    while True:
        game = chess.pgn.read_game(buf)
        if not game:
            break
        yield game

def is_good_game(game):
    hd = game.headers
    if hd.get("Variant", "").lower() != "chess960":
        return False
    if hd.get("SetUp") != "1" or not hd.get("FEN"):
        return False
    if hd.get("Speed", "").lower() not in [s.lower() for s in SPEEDS]:
        return False
    try:
        wr = int(hd.get("WhiteElo", "0"))
        br = int(hd.get("BlackElo", "0"))
    except ValueError:
        return False
    if wr < MIN_RATING or br < MIN_RATING:
        return False
    if hd.get("Result") not in ("1-0", "0-1", "1/2-1/2"):
        return False
    return True

def trim_game(game):
    board = chess.Board(game.headers["FEN"])
    new_game = chess.pgn.Game()
    for k, v in game.headers.items():
        new_game.headers[k] = v
    node = new_game
    ply = 0
    for mv in game.mainline_moves():
        if ply >= MAX_PLIES:
            break
        node = node.add_variation(mv)
        ply += 1
    return new_game

def write_pgn(games, path):
    with open(path, "w", encoding="utf-8") as f:
        for g in games:
            f.write(str(g))
            f.write("\n\n")

def main():
    games_by_fen = defaultdict(list)
    seen = set()
    for bot in BOTS:
        print(f"Downloading for {bot}...")
        try:
            pgn_text = export_games(bot)
        except Exception as e:
            print(f"Failed for {bot}: {e}")
            continue

        pgn_count = 0
        for g in parse_pgn_stream(pgn_text):
            pgn_count += 1
            if not is_good_game(g):
                continue
            fen = g.headers["FEN"]
            key = (fen, g.board().variation_san(g.mainline_moves()))
            if key in seen:
                continue
            seen.add(key)
            tg = trim_game(g)
            games_by_fen[fen].append(tg)
            print(f"Stored game #{pgn_count} from {bot}, speed={g.headers.get('Speed','?')}")

    final_games = []
    for fen, arr in games_by_fen.items():
        if len(arr) >= MIN_FEN_GAMES:
            final_games.extend(arr)

    print(f"Kept {len(final_games)} games after filtering.")
    write_pgn(final_games, MASTER_PGN)
    print(f"Master PGN saved to {MASTER_PGN}")

    print("Building Polyglot book using create_polyglot.py...")
    subprocess.run([sys.executable, "create_polyglot.py"], check=True)
    print("Book creation complete.")

if __name__ == "__main__":
    main()
