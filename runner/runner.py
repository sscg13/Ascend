import random
import subprocess
import threading
import time
from typing import NamedTuple

def rank(card):
    if card == 54:
        return 14
    elif card == 53:
        return 13
    else:
        return (card - 1) // 4

def generate_deck():
    full_deck = list(range(1, 55))
    random.shuffle(full_deck)
    deck_size = 22
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
                    parts = line.split()
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
        print("Game pair result: " + str(result))
        return result
    
    def play_match(self, hidden, count):
        for i in range(count):
            result = self.play_pair(hidden, generate_deck())
            self.results[1 + result] = self.results[1 + result] + 1

results = [0, 0, 0]
exe1 = ["base", 1000, 100]
exe2 = ["extend", 1000, 100]
num_threads = 4
threads = []
runners = []

for i in range(num_threads):
    runner = Runner(exe1, exe2)
    runners.append(runner)
    thread = threading.Thread(target=runner.play_match, args=(False, 300))
    threads.append(thread)
    thread.start()
    print("Launched thread " + str(i))

for thread in threads:
    thread.join()

for runner in runners:
    for i in range(3):
        results[i] = results[i] + runner.results[i]

print(exe2)
print("vs")
print(exe1)
print("[W, D, L]:")
print(results)

#print(generate_deck())
