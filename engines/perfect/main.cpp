#include <chrono>
#include <iostream>
#include <random>
#include <sstream>
#include <string>

using U64 = uint64_t;

constexpr int SCORE_INF = 2000;
constexpr int SCORE_MATE = 1900;
constexpr int SCORE_MAX_EVAL = 1800;
constexpr int MAX_PLY = 64;
constexpr int MAX_MOVES = 64;
constexpr int TT_SIZE = 131072;
constexpr int EXPECTED_PV_NODE = 3;
constexpr int EXPECTED_ALL_NODE = 2;
constexpr int EXPECTED_CUT_NODE = 1;

int move(int rank, int count) {
    return 16 * count + rank;
}
int rank(int play) {
    return play % 16;
}
int count(int play) {
    return play / 16;
}
U64 cardhashes[2][16][5];
U64 movehashes[96];
U64 colorhash;
void initializezobrist() {
    std::mt19937_64 mt(20346892);
    for (int i = 0; i < 15; i++) {
        for (int j = 0; j < 5; j++) {
            cardhashes[0][i][j] = mt();
            cardhashes[1][i][j] = mt();
        }
    }
    for (int i = 0; i < 96; i++) {
        movehashes[i] = mt();
    }
    colorhash = mt();
    for (int j = 0; j < 5; j++) {
        cardhashes[0][15][j] = (U64)0;
        cardhashes[1][15][j] = (U64)0;
    }
}
struct Board {
    int totals[2][2];
    int counts[2][16];
    int color = 0;
    U64 deckhashes[2];
    U64 hash(int play);
    U64 hashafter(int play);
    bool islegal(int curr, int next);
    void makemove(int play);
    void unmakemove(int play);
    int generatemoves(int play, int *movelist);
    int evaluate();
    void set(int side, std::string deck);
};
struct Limits {
    U64 softnodelimit = 0;
    U64 hardnodelimit = 0;
    int softtimelimit = 0;
    int hardtimelimit = 0;
    int maxdepth = MAX_PLY;
};
struct Options {
    bool suppressoutput = false;
};
struct TTentry {
    U64 data;
    void update(U64 hash, int depth, int ply, int score, int nodetype, int hashmove);
    U64 key();
    int hashmove();
    int depth();
    int score(int ply);
    int nodetype();
};
struct History {
    int mainhist[96];
    int conthist[96][96];
    constexpr static int limit = 32768;
    void update(int prev, int curr, int bonus);
};
struct Searcher {
    Board decks;
    Limits searchlimits;
    Options searchoptions;
    U64 nodecount = (U64)0;
    int pvtable[MAX_PLY + 1][MAX_PLY + 1];
    int lastmove;
    bool stopsearch;
    std::chrono::time_point<std::chrono::steady_clock> start;
    TTentry TT[TT_SIZE];
    History Histories;
    int alphabeta(int depth, int ply, int alpha, int beta, int play);
    int iterative(int play);
    void reset();
    void interface();
};
U64 Board::hash(int play) {
    U64 hash = deckhashes[0] ^ deckhashes[1] ^ movehashes[play];
    if (color) {
        hash ^= colorhash;
    }
    return hash;
}
U64 Board::hashafter(int play) {
    U64 hash = (rank(play) == 15) ? (cardhashes[color][14][1] ^ cardhashes[color][13][1])
                : (cardhashes[color][rank(play)][counts[color][rank(play)]] 
                ^ cardhashes[color][rank(play)][counts[color][rank(play)] - count(play)]);
    hash ^= (deckhashes[0] ^ deckhashes[1] ^ movehashes[play]);
    if (color) {
        hash ^= colorhash;
    }
    return hash;
}
bool Board::islegal(int curr, int next) {
    if (count(curr) == 0) {
        return true;
    }
    else {
        if (count(next) != count(curr)) {
            return false;
        }
        if (rank(next) <= rank(curr)) {
            return false;
        }
        if (counts[color][rank(next)] < count(next)) {
            return false;
        }
        return true;
    }
}
void Board::makemove(int play) {
    deckhashes[color] ^= cardhashes[color][rank(play)][counts[color][rank(play)]];
    counts[color][rank(play)] -= count(play);
    totals[color][0] -= count(play);
    totals[color][1] -= (128 * count(play) * rank(play));
    deckhashes[color] ^= cardhashes[color][rank(play)][counts[color][rank(play)]];
    if (rank(play) == 15) {
        counts[color][14]--;
        counts[color][13]--;
        deckhashes[color] ^= (cardhashes[color][14][1] ^ cardhashes[color][13][1]);
    }
    else if (rank(play) >= 13) {
        counts[color][15]--;
    }
    color ^= 1;
}
void Board::unmakemove(int play) {
    color ^= 1;
    deckhashes[color] ^= cardhashes[color][rank(play)][counts[color][rank(play)]];
    counts[color][rank(play)] += count(play);
    totals[color][0] += count(play);
    totals[color][1] += (128 * count(play) * rank(play));
    deckhashes[color] ^= cardhashes[color][rank(play)][counts[color][rank(play)]];
    if (rank(play) == 15) {
        counts[color][14]++;
        counts[color][13]++;
        deckhashes[color] ^= (cardhashes[color][14][1] ^ cardhashes[color][13][1]);
    }
    else if (rank(play) >= 13) {
        counts[color][15]++;
    }
}
int Board::generatemoves(int play, int *movelist) {
    int movecount = 0;
    if (count(play) == 0) {
        for (int i = 0; i < 15; i++) {
            for (int j = 1; j <= counts[color][i]; j++) {
                movelist[movecount] = move(i, j);
                movecount++;
            }
        }
    }
    else {
        for (int i = rank(play) + 1; i < 15; i++) {
            if (counts[color][i] >= count(play)) {
                movelist[movecount] = move(i, count(play));
                movecount++;
            }
        }
    }
    if ((count(play) == 2 || count(play) == 0) && counts[color][15] == 2) {
        movelist[movecount] = move(15, 2);
        movecount++;
    }
    movelist[movecount] = 0;
    return movecount + 1;
}
int Board::evaluate() {
    return (totals[color][1] / totals[color][0] - totals[color ^ 1][1] / totals[color ^ 1][0]);
}
void Board::set(int side, std::string deck) {
    totals[side][0] = 0;
    totals[side][1] = 0;
    int i = 0;
    int j = 0;
    deckhashes[side] = (U64)0;
    while (i < 15) {
        if (deck[j] >= '0' && deck[j] <= '4') {
            counts[side][i] = (deck[j] - '0');
            totals[side][0] += counts[side][i];
            totals[side][1] += 128 * counts[side][i] * i;
            deckhashes[side] ^= cardhashes[side][i][counts[side][i]];
            i++;
        }
        j++;
    }
    counts[side][15] = counts[side][13] + counts[side][14];
}
void TTentry::update(U64 hash, int depth, int ply, int score, int nodetype, int hashmove) {
  data = (hash >> 32);
  if (score > SCORE_MAX_EVAL) {
    score += ply;
  }
  if (score < -SCORE_MAX_EVAL) {
    score -= ply;
  }
  data |= ((U64)((unsigned short int)score) << 32);
  data |= (((U64)hashmove) << 43);
  data |= (((U64)nodetype) << 51);
  data |= (((U64)depth) << 53);
}
U64 TTentry::key() { return (data & 0xFFFFFFFF); }
int TTentry::hashmove() { return (int)(data >> 43) & 0xFF; }
int TTentry::depth() { return (int)(data >> 53) & 63; }
int TTentry::score(int ply) {
  int score = (int)(short int)((data >> 32) & 0x00000000000007FF);
  if (score > SCORE_MAX_EVAL) {
    return score - ply;
  }
  if (score < -SCORE_MAX_EVAL) {
    return score + ply;
  }
  return score;
}
int TTentry::nodetype() { return (int)(data >> 51) & 3; }
void History::update(int prev, int curr, int bonus) {
    mainhist[curr] += (bonus - bonus * mainhist[curr] / limit);
}
int Searcher::alphabeta(int depth, int ply, int alpha, int beta, int play) {
    pvtable[ply][0] = ply + 1;
    if (depth <= 0 || ply >= searchlimits.maxdepth) {
        return decks.evaluate();
    }
    int score = -SCORE_INF;
    int bestscore = -SCORE_INF;
    bool improvedalpha = false;
    U64 currhash = decks.hash(play);
    int index = decks.hash(play) % TT_SIZE;
    int ttmove = -1;
    TTentry &ttentry = TT[index];
    bool tthit = (ttentry.key() == (currhash >> 32));
    bool isPV = (beta - alpha) > 1;
    int ttdepth = ttentry.depth();
    bool update = (depth >= ttdepth || !tthit);
    if (tthit) {
        score = ttentry.score(ply);
        ttmove = ttentry.hashmove();
        int ttnodetype = ttentry.nodetype();
        if (!isPV && ttdepth == depth) {
            if (ttnodetype == EXPECTED_PV_NODE) {
                return score;
            }
            if ((ttnodetype & EXPECTED_CUT_NODE) && (score >= beta)) {
                return score;
            }
            if ((ttnodetype & EXPECTED_ALL_NODE) && (score <= alpha)) {
                return score;
            }
        }
    }
    int moves[MAX_MOVES];
    int movescore[MAX_MOVES];
    int movcount = decks.generatemoves(play, moves);
    for (int i = 0; i < movcount; i++) {
        if (moves[i] == ttmove) {
            movescore[i] = 131072;
        }
        else {
            movescore[i] = Histories.mainhist[moves[i]];
        }
    }
    /*for (int i = 0; i < movcount; i++) {
        if (moves[i] == ttmove) {
            std::swap(moves[i], moves[0]);
        }
    }*/
    for (int i = 0; i < movcount; i++) {
        bool nullwindow = (i > 0);
        int e = (movcount == 1);
        for (int j = i + 1; j < movcount; j++) {
            if (movescore[j] > movescore[i]) {
                std::swap(moves[j], moves[i]);
                std::swap(movescore[j], movescore[i]);
            }
        }
        int mov = moves[i];
        if (!stopsearch) {
            if (count(mov) == decks.totals[decks.color][0]) {
                score = SCORE_MATE - ply - 1;
            }
            else {
                decks.makemove(mov);
                nodecount++;
                if (nullwindow) {
                    score = -alphabeta(depth - 1, ply + 1, -alpha - 1, -alpha, mov);
                    if (score > alpha && score < beta) {
                        score = -alphabeta(depth - 1, ply + 1, -beta, -alpha, mov);
                    }
                } else {
                    score = -alphabeta(depth - 1 + e, ply + 1, -beta, -alpha, mov);
                }
                decks.unmakemove(mov);
            }
            if (score > bestscore) {
                if (score > alpha) {
                    if (score >= beta) {
                        if (!stopsearch) {
                            if (update) {
                                ttentry.update(currhash, depth, ply, score, EXPECTED_CUT_NODE, mov);
                            }
                            Histories.update(play, mov, 2 * depth * depth + 23 * depth - 19);
                            /*for (int j = 0; j < i; j++) {
                                Histories.update(play, moves[j], -depth);
                            }*/
                        }
                        return score;
                    }
                    alpha = score;
                    improvedalpha = true;
                }
                pvtable[ply][ply + 1] = mov;
                pvtable[ply][0] = pvtable[ply + 1][0] ? pvtable[ply + 1][0] : ply + 2;
                for (int j = ply + 2; j < pvtable[ply][0]; j++) {
                    pvtable[ply][j] = pvtable[ply + 1][j];
                }
                bestscore = score;
            }
            if (nodecount >= searchlimits.hardnodelimit && searchlimits.hardnodelimit > 0) {
                    stopsearch = true;
            }
            if ((nodecount & 1023) == 0) {
                auto now = std::chrono::steady_clock::now();
                auto timetaken = std::chrono::duration_cast<std::chrono::milliseconds>(now - start);
                if (timetaken.count() >= searchlimits.hardtimelimit && searchlimits.hardtimelimit > 0) {
                    stopsearch = true;
                }
            }
        }
    }
    int realnodetype = improvedalpha ? EXPECTED_PV_NODE : EXPECTED_ALL_NODE;
    int savedmove = improvedalpha ? pvtable[ply][ply + 1] : ttmove;
    if ((update || realnodetype == EXPECTED_PV_NODE) && !stopsearch) {
        ttentry.update(currhash, depth, ply, bestscore, realnodetype, savedmove);
    }
    return bestscore;
}
int Searcher::iterative(int play) {
    nodecount = (U64)0;
    start = std::chrono::steady_clock::now();
    stopsearch = false;
    int depth = 1;
    int bestmove1 = 0;
    int returnedscore;
    std::stringstream infoline;
    while (!stopsearch) {
        int score = alphabeta(depth, 0, -SCORE_INF, SCORE_INF, play);
        auto now = std::chrono::steady_clock::now();
        auto timetaken = std::chrono::duration_cast<std::chrono::milliseconds>(now - start);
        if ((nodecount < searchlimits.hardnodelimit || searchlimits.hardnodelimit <= 0)
        && (timetaken.count() < searchlimits.hardtimelimit || searchlimits.hardtimelimit <= 0)
        && depth < searchlimits.maxdepth) {
            returnedscore = score;
            if (!searchoptions.suppressoutput) {
                infoline << "info depth " << depth << " nodes " << nodecount
                << " time " << timetaken.count() << " score " << score << " pv ";
                for (int i = 1; i < pvtable[0][0]; i++) {
                    infoline << pvtable[0][i] << " ";
                }
            }
            std::cout << infoline.str() << std::endl;
            infoline.clear();
            infoline.str("");
            depth++;
            if (depth == searchlimits.maxdepth) {
                stopsearch = true;
            }
            bestmove1 = pvtable[0][1];
        } 
        else {
            stopsearch = true;
        }
        if ((timetaken.count() > searchlimits.softtimelimit && searchlimits.softtimelimit > 0)
        || (nodecount > searchlimits.softnodelimit && searchlimits.softnodelimit > 0)) {
            stopsearch = true;
        }
    }
    if (!searchoptions.suppressoutput) {
        std::cout << "bestmove " << bestmove1 << std::endl;
    }
    return returnedscore;
}
void Searcher::reset() {
    for (int i = 0; i < MAX_PLY+1; i++) {
        for (int j = 0; j < MAX_PLY+1; j++) {
            pvtable[i][j] = 0;
        }
    }
    lastmove = 0;
    for (int i = 0; i < TT_SIZE; i++) {
        TT[i].data = (U64)0;
    }
    for (int i = 0; i < 96; i++) {
        for (int j = 0; j < 96; j++) {
            Histories.conthist[i][j] = 0;
        }
        Histories.mainhist[i] = 0;
    }
    decks.color = 0;
}
void Searcher::interface() {
    std::string ucicommand;
    std::getline(std::cin, ucicommand);
    std::stringstream tokens(ucicommand);
    std::string token;
    tokens >> token;
    if (token == "quit") {
        exit(0);
    }
    if (token == "newgame") {
        reset();
    }
    if (token == "deck") {
        std::string cards;
        tokens >> token;
        std::streampos pos = tokens.tellg();
        cards = tokens.str().substr(pos);
        if (token == "engine") {
            decks.set(decks.color, cards);
        }
        if (token == "opponent") {
            decks.set(decks.color ^ 1, cards);
        }
    }
    if (token == "print") {
        std::cout << "Engine deck: ";
        for (int i = 0; i < 15; i++) {
            std::cout << decks.counts[decks.color][i];
        }
        std::cout << "\nOpponent deck: ";
        for (int i = 0; i < 15; i++) {
            std::cout << decks.counts[decks.color ^ 1][i];
        }
        std::cout << "\nLast move: " << lastmove << "\n";
    }
    if (token == "move") {
        tokens >> token;
        decks.makemove(std::stoi(token));
        lastmove = std::stoi(token);
    }
    if (token == "go") {
        int time = 0;
        int inc = 0;
        Limits infinitesearch = {0, 0, 0, 0, MAX_PLY};
        searchlimits = infinitesearch;
        while (tokens >> token) {
            if (token == "time") {
                tokens >> token;
                time = std::stoi(token);
            }
            if (token == "inc") {
                tokens >> token;
                inc = std::stoi(token);
            }
            if (token == "movetime") {
                tokens >> token;
                searchlimits.hardtimelimit = std::stoi(token);
            }
            if (token == "depth") {
                tokens >> token;
                searchlimits.maxdepth = 1 + std::stoi(token);
            }
            if (token == "nodes") {
                tokens >> token;
                searchlimits.hardnodelimit = std::stoull(token);
            }
        }
        if (time > 0) {
            searchlimits.softtimelimit = time / 40 + inc / 3;
            searchlimits.hardtimelimit = time / 10 + inc;
        }
        int score = iterative(lastmove);
    }
}
int main() {
    initializezobrist();
    Searcher engin;
    engin.reset();
    while (true) {
        engin.interface();
    }
    return 0;
}