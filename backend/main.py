from sleepys_chess import ChessEngine, parse_initial_state

def main():
    game_load = input('Load a game or press enter to load into default board!').strip()
    chess_game = ChessEngine()
    chess_game.run(game_load)

if __name__ == '__main__':
    main()