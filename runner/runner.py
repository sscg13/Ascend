import argparse
import os
import random
import subprocess
import tempfile
import threading
import time
from typing import NamedTuple
from sprt import calculate_sprt

POSITION_LENGTH = 30

def rank(card):
    if card == 54:
        return 14
    elif card == 53:
        return 13
    else:
        return (card - 1) // 4

def generate_deck(deck_size):
    full_deck = list(range(1, 55))
    random.shuffle(full_deck)
    hand1 = full_deck[ : deck_size]
    hand2 = full_deck[deck_size : 2 * deck_size]
    ranks1 = [0] * 15
    ranks2 = [0] * 15
    for card in hand1:
        ranks1[rank(card)] = ranks1[rank(card)] + 1
    for card in hand2:
        ranks2[rank(card)] = ranks2[rank(card)] + 1
    deck1 = "".join(str(count) for count in ranks1)
    deck2 = "".join(str(count) for count in ranks2)
    return [deck1, deck2]

class TimeConfig(NamedTuple):
    base: int
    increment: int    

class BookEntry(NamedTuple):
    position: str
    decisive: int
    total: int

def parse_book_line(line, line_number=None):
    """Parse a legacy position line or a position with persisted statistics."""
    content = line.strip()
    if not content:
        raise ValueError("empty book line")

    if "|" not in content:
        position = content
        decisive = 0
        total = 0
    else:
        position_part, stats_part = content.split("|", 1)
        position = position_part.strip()
        try:
            decisive_part, total_part = stats_part.split("/", 1)
            decisive = int(decisive_part.strip())
            total = int(total_part.strip())
        except (ValueError, TypeError) as error:
            raise ValueError(f"invalid book statistics: {content!r}") from error

    if len(position) != POSITION_LENGTH:
        raise ValueError(
            f"expected a {POSITION_LENGTH}-character position, got {len(position)}"
        )
    if not position.isdigit():
        raise ValueError(f"position must contain only digits: {position!r}")
    if decisive < 0 or total < 0 or decisive > total:
        raise ValueError(f"invalid book statistics: {decisive} / {total}")

    return BookEntry(position, decisive, total)

def load_book(bookfile):
    entries = []
    with open(bookfile, "r", encoding="ascii", newline="") as book:
        for line_number, line in enumerate(book, 1):
            try:
                entries.append(parse_book_line(line, line_number))
            except ValueError as error:
                raise ValueError(f"{bookfile}:{line_number}: {error}") from error
    if not entries:
        raise ValueError(f"book is empty: {bookfile}")
    return entries

def save_book(bookfile, entries):
    """Atomically persist positions and their decisive/total pair counts."""
    book_dir = os.path.dirname(os.path.abspath(bookfile))
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="ascii", newline="\n", dir=book_dir,
            prefix=".book-", suffix=".tmp", delete=False
        ) as temp_book:
            temp_name = temp_book.name
            for entry in entries:
                temp_book.write(
                    f"{entry.position} | {entry.decisive} / {entry.total}\n"
                )
            temp_book.flush()
            os.fsync(temp_book.fileno())
        os.replace(temp_name, bookfile)
        temp_name = None
    finally:
        if temp_name is not None:
            try:
                os.remove(temp_name)
            except FileNotFoundError:
                pass

class Runner:

    def __init__(self, engine1, engine2):
        self.engine1 = engine1[0]
        self.engine2 = engine2[0]
        self.basetc1 = TimeConfig(engine1[1], engine1[2])
        self.basetc2 = TimeConfig(engine2[1], engine2[2])
        self.results = [0, 0, 0]
    
    def reset_time(self, tc1, tc2):
        tc1[0] = self.basetc1.base
        tc1[1] = self.basetc1.increment
        tc2[0] = self.basetc2.base
        tc2[1] = self.basetc2.increment

    def play_game(self, engine1, engine2, deck1, deck2, hidden, tc1, tc2):
        engine1.stdin.write("newgame\n")
        engine1.stdin.write("deck engine " + deck1 + "\n")
        if not hidden:
            engine1.stdin.write("deck opponent " + deck2 + "\n")
        engine1.stdin.flush()
        engine2.stdin.write("newgame\n")
        if not hidden:
            engine2.stdin.write("deck engine " + deck1 + "\n")
            engine2.stdin.write("deck opponent " + deck2 + "\n")
        else:
            engine2.stdin.write("deck engine " + deck2 + "\n")
        engine2.stdin.flush()
        players = [engine1, engine2]
        times = [tc1, tc2]
        player = 0
        results = [-1, -2]
        while True:
            if results[0] == results[1]:
                return results[0]
            engine = players[player]
            tc = times[player]
            engine.stdin.write("go time " + str(tc[0]) + " inc " + str(tc[1]) + "\n")
            engine.stdin.flush()
            search_start = time.monotonic()
            while True:
                line = engine.stdout.readline().strip()
                parts = line.split()
                if parts[0] == "bestmove":
                    search_end = time.monotonic()
                    time_taken = int(1000 * (search_end - search_start))
                    tc[0] = tc[0] - time_taken + tc[1]
                    if tc[0] < 0:
                        return player
                    move = parts[1]
                    engine1.stdin.write("move " + move + "\n")
                    engine1.stdin.flush()
                    engine2.stdin.write("move " + move + "\n")
                    engine2.stdin.flush()
                    player = 1 - player
                    break
                elif parts[0] == "info":
                    score_index = parts.index("score")
                    score = int(parts[score_index + 1])
                    if score < -1800:
                        results[player] = player
                    elif score > 1800:
                        results[player] = 1 - player
                        
    def play_pair(self, hidden, decks):
        engineA = subprocess.Popen(
            [self.engine1], stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, text=True, bufsize=1
        )
        engineB = subprocess.Popen(
            [self.engine2], stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, text=True, bufsize=1
        )
        tc1 = [self.basetc1.base, self.basetc1.increment]
        tc2 = [self.basetc2.base, self.basetc2.increment]
        result1 = self.play_game(engineA, engineB, decks[0], decks[1], hidden, tc1, tc2)
        self.reset_time(tc1, tc2)
        result2 = self.play_game(engineB, engineA, decks[0], decks[1], hidden, tc2, tc1)
        result = result1 - result2
        engineA.stdin.write("quit\n")
        engineA.stdin.flush()
        engineB.stdin.write("quit\n")
        engineB.stdin.flush()
        print("Game pair result: " + str(result) + " (Deck: " + decks[0] + decks[1] + ")")
        return result
    
    def play_match(self, hidden, count, bookfile):
        if bookfile == "":
            for i in range(count):
                result = self.play_pair(hidden, generate_deck(22))
                self.results[1 + result] = self.results[1 + result] + 1
        else:
            entries = load_book(bookfile)
            for i in range(count):
                entry_index = random.randrange(len(entries))
                entry = entries[entry_index]
                decks = [entry.position[0:15], entry.position[15:30]]
                result = self.play_pair(hidden, decks)
                self.results[1 + result] = self.results[1 + result] + 1
                entries[entry_index] = BookEntry(
                    entry.position,
                    entry.decisive + (1 if result != 0 else 0),
                    entry.total + 1,
                )
                save_book(bookfile, entries)


def main():
    parser = argparse.ArgumentParser(
        description="Run an SPRT match between two engines using local book files."
    )
    parser.add_argument(
        "engine1",
        nargs="?",
        default="extend",
        help="path to the first engine executable (default: extend)",
    )
    parser.add_argument(
        "engine2",
        nargs="?",
        default="ttmove",
        help="path to the second engine executable (default: ttmove)",
    )
    args = parser.parse_args()

    results = [0, 0, 0]
    exe1 = [args.engine1, 1000, 100]
    exe2 = [args.engine2, 1000, 100]
    num_threads = 4

    batch_num = 1

    print(f"Testing {exe2} vs {exe1}")

    while True:
        print(f"--- Starting Batch {batch_num} ---")
        
        runners = []
        threads = []
        
        for thread_idx in range(num_threads):
            runner = Runner(exe1, exe2)
            runners.append(runner)
            
            book_name = f"newbook{thread_idx}.txt"
            thread = threading.Thread(target=runner.play_match, args=(False, 8, book_name))
            threads.append(thread)
            thread.start()
            print(f"Launched thread {thread_idx}")

        for thread in threads:
            thread.join()

        for runner in runners:
            for j in range(3):
                results[j] += runner.results[j]

        print("[W, D, L]:", results)
        
        llr, status = calculate_sprt(results) 
        
        print(f"Current LLR: {llr:.4f} | Status: {status}\n")
        
        if status != "LIVE": 
            print(f"Test concluded! Final Result: {status}")
            break
        
        batch_num += 1


if __name__ == "__main__":
    main()

#print(generate_deck())

"""book_length = os.path.getsize("balanced0.txt") // 32
with open("balanced0.txt", 'r') as book:
    for i in range(10):
        rand_line = random.randint(0, book_length - 1)
        print(rand_line)
        book.seek(32 * rand_line, os.SEEK_SET)
        deck = book.readline().strip()
        print(deck)"""
