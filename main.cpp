#include <chrono>
#include <iostream>
#include <sstream>
#include <string>

using U64 = uint64_t;

constexpr int SCORE_INF = 2000;
constexpr int SCORE_MATE = 1900;
constexpr int MAX_PLY = 64;
constexpr int MAX_MOVES = 64;

int move(int rank, int count) {
    return 16 * count + rank;
}
int rank(int play) {
    return play % 16;
}
int count(int play) {
    return play / 16;
}

struct Board {
    int totals[2][2];
    int counts[2][16];
    int color = 0;
    void makemove(int play);
    void unmakemove(int play);
    int generatemoves(int play, int *movelist);
    int evaluate();
    void set(int side, std::string deck);
};
struct Limits {
    int softnodelimit = 0;
    int hardnodelimit = 0;
    int softtimelimit = 0;
    int hardtimelimit = 0;
    int maxdepth = MAX_PLY;
};
struct Options {
    bool suppressoutput = false;
};
struct Searcher {
    Board decks;
    Limits searchlimits;
    Options searchoptions;
    U64 nodecount = (U64)0;
    int pvtable[MAX_PLY + 1][MAX_PLY + 1];
    bool stopsearch;
    std::chrono::time_point<std::chrono::steady_clock> start;
    int alphabeta(int depth, int ply, int alpha, int beta, int play);
    int iterative(int play);
    void reset();
    void uci();
};
void Board::makemove(int play) {
    totals[color][0] -= count(play);
    totals[color][1] -= (128 * count(play) * rank(play));
    counts[color][rank(play)] -= count(play);
    if (rank(play) == 15) {
        counts[color][14]--;
        counts[color][13]--;
    }
    else if (rank(play) >= 13) {
        counts[color][15]--;
    }
    color ^= 1;
}
void Board::unmakemove(int play) {
    color ^= 1;
    totals[color][0] += count(play);
    totals[color][1] += (128 * count(play) * rank(play));
    counts[color][rank(play)] += count(play);
    if (rank(play) == 15) {
        counts[color][14]++;
        counts[color][13]++;
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
    for (int i = 0; i < 15; i++) {
        counts[side][i] = (deck[i] - '0');
        totals[side][0] += counts[side][i];
        totals[side][1] += 128 * counts[side][i] * i;
    }
    counts[side][15] = counts[side][13] + counts[side][14];
}
int Searcher::alphabeta(int depth, int ply, int alpha, int beta, int play) {
    pvtable[ply][0] = ply + 1;
    if (depth <= 0 || ply >= searchlimits.maxdepth) {
        return decks.evaluate();
    }
    int score = -SCORE_INF;
    int bestscore = -SCORE_INF;
    int moves[MAX_MOVES];
    int movcount = decks.generatemoves(play, moves);
    for (int i = 0; i < movcount; i++) {
        bool nullwindow = (i > 0);
        int e = (movcount == 1);
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
                        return score;
                    }
                    alpha = score;
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
}

int main() {
    Searcher engin;
    engin.reset();
    //engin.searchlimits.hardtimelimit = 60000;
    engin.decks.color = 0;
    engin.decks.set(0, "101113000020300");
    engin.decks.set(1, "211020102101010");
    engin.iterative(0);
    return 0;
}