from sleepys_chess import ChessEngine

def main():
    game_load = input('Load a game or press enter to load into default board!').strip()
    chess_game = ChessEngine()
    chess_game.run(game_load)

    # Debug info
    game_info = (chess_game.command_log, chess_game.game.position_history, 
                 chess_game.game.move_history)
    for info in game_info:
        items = None
        if isinstance(info, dict):
            items = info.items()
        else: 
            items = info
        for i, entry in enumerate(items):
            print(f'{i}: {entry}')
        print() 
    print(chess_game.game.generate_pgn())

if __name__ == '__main__':
    main()