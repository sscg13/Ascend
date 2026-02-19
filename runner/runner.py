import os
import random
import subprocess
import threading
import time
from typing import NamedTuple
from sprt import calculate_sprt

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
            book_length = os.path.getsize(bookfile) // 32
            with open(bookfile, 'r') as book:
                for i in range(count):
                    rand_line = random.randint(0, book_length - 1)
                    book.seek(32 * rand_line, os.SEEK_SET)
                    deck = book.readline().strip()
                    decks = [deck[0 : 15], deck[15 : 30]]
                    result = self.play_pair(hidden, decks)
                    self.results[1 + result] = self.results[1 + result] + 1


results = [0, 0, 0]
exe1 = ["extend", 1000, 100]
exe2 = ["ttmove", 1000, 100]
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

#print(generate_deck())

"""book_length = os.path.getsize("balanced0.txt") // 32
with open("balanced0.txt", 'r') as book:
    for i in range(10):
        rand_line = random.randint(0, book_length - 1)
        print(rand_line)
        book.seek(32 * rand_line, os.SEEK_SET)
        deck = book.readline().strip()
        print(deck)"""
