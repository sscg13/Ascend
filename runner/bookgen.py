import random
import subprocess
import threading

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

class Generator:
    def __init__(self, engine, nodes):
        self.engine = engine
        self.nodes = nodes
    
    def generate_book(self, count, deck_size, bound, output_file):
        success = 0
        engin = subprocess.Popen(
            [self.engine], stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, text=True, bufsize=1
        )

        with open(output_file, 'w') as f:
            while success < count:
                deck = generate_deck(deck_size)
                engin.stdin.write("newgame\n")
                engin.stdin.write("deck engine " + deck[0] + "\n")
                engin.stdin.write("deck opponent " + deck[1] + "\n")
                engin.stdin.write("go nodes " + str(self.nodes) + "\n")
                engin.stdin.flush()
                score = -2000
                while True:
                    line = engin.stdout.readline().strip()
                    parts = line.split()
                    if parts[0] == "bestmove":
                        break
                    elif parts[0] == "info":
                        score_index = parts.index("score")
                        score = int(parts[score_index + 1])
                print("Score: " + str(score))
                if abs(score) < bound:
                    f.write(deck[0] + deck[1] + "\n")
                    success = success + 1
        engin.stdin.write("quit\n")
        engin.stdin.flush()

exe = "extend"
nodecount = 10000000
bookcount = 10000
bound = 128
decksize = 22
num_threads = 4
threads = []
generators = []

for i in range(num_threads):
    generator = Generator(exe, nodecount)
    generators.append(generator)
    thread = threading.Thread(target=generator.generate_book, args=(bookcount, decksize + i, bound, "newbook"+str(i)+".txt"))
    threads.append(thread)
    thread.start()
    print("Launched thread " + str(i))

for thread in threads:
    thread.join()