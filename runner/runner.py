import random
import subprocess
import time

def rank(card):
    if card == 54:
        return 14
    elif card == 53:
        return 13
    else:
        return (card - 1) // 4

def play_game(engine1, engine2, deck1, deck2, hidden):
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
    player = 0
    result = -1
    mate = False
    while True:
        engine = players[player]
        engine.stdin.write("go nodes 32768\n")
        engine.stdin.flush()
        while True:
            line = engine.stdout.readline().strip()
            parts = line.split()
            if parts[0] == "bestmove":
                move = parts[1]
                if mate:
                    return result
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
                    mate = True
                    result = player
                elif score > 1800:
                    mate = True
                    result = 1 - player
                    
def play_pair(engine1, engine2, hidden):
    engineA = subprocess.Popen(
        [engine1], stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, text=True, bufsize=1
    )
    engineB = subprocess.Popen(
        [engine2], stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, text=True, bufsize=1
    )
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
    result1 = play_game(engineA, engineB, deck1, deck2, hidden)
    result2 = play_game(engineB, engineA, deck1, deck2, hidden)
    result = result1 - result2
    engineA.stdin.write("quit\n")
    engineA.stdin.flush()
    engineB.stdin.write("quit\n")
    engineB.stdin.flush()
    print("Game pair result: " + str(result))
    return result

results = [0, 0, 0]
for i in range(400):
    result = play_pair("C:/Users/ckbao/Downloads/Ascend/engine", "C:/Users/ckbao/Downloads/Ascend/engine", False)
    results[1 + result] = results[1 + result] + 1

print(results)


