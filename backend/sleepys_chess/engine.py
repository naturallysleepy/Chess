from __future__ import annotations
from typing import Callable

from .parsing import move_or_command
from .gamerules import GameState, create_game
from .utils import opposite, clear_screen, unabbreviate, is_colour
from .board import Board

import re

class UserExit(Exception):
    # Exit from anywhere in call stack
    pass

class ChessEngine:
    def __init__(self, game=None):
        if not game:
            game = create_game()
        self.game: GameState = game
        self.exit = False
        self.points: int = 0
        
        self.command_log: list[tuple] = []
        self.message: str = ''
        
        self.checkpoint: GameState | None = None
        self.expiry_clock = 0 

        self.is_viewing: bool = False
        self.view_target: int = 0
        self.view_perspective: str = ''
        
    def update_clock(self, ticks: int =  1):
        self.message = ''
        
        if self.expiry_clock < 0: # Undershoot
            self.expiry_clock = 0
            
        if self.expiry_clock > 0:
            self.expiry_clock -= ticks
        else:
            self.checkpoint = None
 
    def process_command(self, command_str):
            command_map = {
                r'/(view(?: move)?)\s*(-?\d+|back|forward|<|>)?\s*(b(?:lack)?|w(?:hite)?)?\s*(b(?:lack)?|w(?:hite)?)?': self.view_move, 
                r'/(undo|back)\s*(-?\d+)?\s*(b(?:lack)?|w(?:hite)?)?': self.execute_undo,
                r'/?(resign|q(?:uit)?|give up)': self.resign,
                r'/?(exit|close)': self.exit_game,
                r'/(restart|reset)': self.restart,
                r'/(revert)': self.revert_undo,
                r'/(flip(?: board)?)': self.flip_board,
                r'/(set perspec(?:tive)?)\s*(b(?:lack)?|w(?:hite)?)?': self.set_perspec, 
                r'/?([?]|help|(?:list )?(?:all )?commands)': self.commands_help
                
            }
            
            for pattern, command in command_map.items():
                command_match = re.fullmatch(pattern, command_str, flags=re.I)
                if command_match:
                    command_name, *params = command_match.groups()
                    if params:
                        command(*params)
                    else:
                        command()
                    self.command_log.append((command_name, *params))
                    break       
            else:
                self.message = f'The command "{command_str}" does not exist'           
            return self
    
    def execute_undo(self, move_num: int | str | None=None, colour=None):
        if isinstance(move_num, str):
            move_num = int(move_num)

        colour = unabbreviate(colour)
        self.game, self.checkpoint = self.game.undo(move_num, colour)
        return self
        
    def exit_game(self):
        self.game.is_end = True
        self.exit = True
        self.message = 'Exiting program...'
        return self

    def resign(self):
        self.game.is_end = True
        self.game.winner = opposite(self.game.turn)
        self.game.end_state = 'resignation'
        return self
        
    def restart(self):
        self.game, self.checkpoint = self.game.undo(0, 'white') # Analogous to restart
        return self
        
    def revert_undo(self):
        if self.checkpoint:
            self.game = self.checkpoint
            self.checkpoint = None
        else:
            self.message = 'Could not revert'
        return self
      
    # View board at move_num
    def view_move(self, move_num: int | str | None = None, move_colour: str | None = None, perspective: str | None = None):
        first_move = self.game.get_start_move() 
        
        params = (move_num, move_colour, perspective)
        if all(param is None for param in params):
            last_move = self.game.move_history[-1]
            move_colour = 'black' if len(last_move) == 1 else 'white'

        if move_num is None:
            move_num = self.game.fullmoves 
        elif isinstance(move_num, str):
            if move_num in ('back', '<'):
                move_num = self.view_target - 1
            elif move_num in ('forward', '>'):
                move_num = self.view_target + 1
            else:
                move_num = int(move_num)

        if move_num < 0:
            move_num = self.game.fullmoves + move_num 
        if move_num < first_move:
            raise ValueError(f'Unable to go to move {move_num}, move cannot be less than {first_move}')
        if move_num > self.game.fullmoves:
            raise ValueError(f'Unable to go to move {move_num}, move cannot be greater than {self.game.fullmoves}')
        
        move_colour = unabbreviate(move_colour)
        perspective = unabbreviate(perspective)
        if not perspective:
            perspective = self.game.board.perspective
        if not move_colour:
            move_colour = self.game.turn
        is_current_move = move_num == self.game.fullmoves and move_colour == self.game.turn

        board_str, *game_info = self.game.get_info(perspective)
        view_board = None
        if is_current_move:
            view_board = self.game.board
        else:
            # Make board at move num
            view_board = Board()
            desired_fen = self.game.position_history[move_num]
            view_board.fen_to_board(desired_fen)

            # Position history is only updated per white move
            if move_colour == 'black':
                black_move = self.game.move_history[move_num - first_move].get('black', None) # None is default value
                if black_move:
                    view_board.make_move(black_move)

        # Render board
        self.is_viewing = True
        self.view_target = move_num
        board_str = view_board.render(perspective) 
        clear_screen()
        self.message = f'Viewing move {move_num} ({move_colour})' if not is_current_move else ''
        print('\n'.join([board_str, *game_info]))

    def set_perspec(self, colour: str | None = None):
        colour = unabbreviate(colour)
        if colour is not None and not is_colour(colour):
            raise ValueError('Invalid colour')
        self.game.board.perspective = colour

    def flip_board(self):
        self.game.board.flip(self.game.turn)
        return self

    def commands_help(self):
        cmd_descs = {
            'view [n]th [colour] move from [side]' :
              '"/view [n]" +(optional: [colour: default=current turn] [side: default=current perspective])',

            'flip the board to show the opposite colour\'s perspective' : 
            '"/flip"',

            'undo [n]th [colour] move (n < 0 goes back n moves, n = 0 identical to restart)': 
                '"/undo" or "/back" +(optional: [n: default=-1] [colour: default=current turn])',
                
            'revert to game state prior to last undo': 
                '"/revert"',
                
            'reset game to 1st move': 
                '"/restart" or "/reset"',
                
            'resign current game': 
                '"/resign" or "/quit"',
                
            'exit program': 
                '"/exit" or "/close"',
                
            'display command descriptions and usage': 
                '"?" or "help"'
        }
        self.message = ''
        for desc, usage in cmd_descs.items():
            self.message += f'Description: {desc}\nUsage: {usage}\n\n'
        return self
        
    def handle_user_input(self, input):
        response_map = {
            'cmd': self.process_command,
            'move': self.game.process_player_move
        }
        response_map[move_or_command(input)](input)
        
    # TODO: Config compatibility
    def run(self, fen_or_pgn: str | None=None, config=None):
        self.game = create_game(fen_or_pgn)
        while not self.exit:  
            if not self.game.is_end:
                # View func not running
                if not self.is_viewing: 
                    print(self.game) 
                    self.view_target = self.game.fullmoves
                self.is_viewing = False 

                player_move = input('Make a move! ')
                clear_screen()
                loop_action = self.try_func(self.handle_user_input, player_move) # try-except the function
                if loop_action == 'break' or self.exit:
                    break
                elif loop_action == 'continue':
                    continue

                if move_or_command(player_move) == 'move':
                    self.update_clock()
                    self.game.check_if_end() 

            else:    
                if self.game.end_state == 'checkmate':
                    # Update the representation of the winning player's last move
                    self.game.move_history[-1][self.game.winner].check_str = '#'
                print(self.game)
                if self.game.winner == 'draw':
                    print(f'Draw by {self.game.end_state}')
                else:
                    print(f'{self.game.winner.capitalize()} won by {self.game.end_state}!')
                    
                # Prompt until game is playable again
                while True:
                    post_game = input('Type "/restart" to play again! Else type a command ')
                    clear_screen()
                    loop_action = self.try_func(self.process_command, post_game)
                    if loop_action == 'break' or self.exit or not self.game.is_end:
                        break
                    elif loop_action == 'continue':
                        continue
                    if not self.is_viewing:
                        print(self.game)
                        self.view_target = self.game.fullmoves
                    self.is_viewing = False

        print('Thanks for playing!') # Bye bye
        return 
                
    def try_func(self, function: Callable[[str], None], user_input: str) -> str:
        try:
            function(user_input)
            if self.message:
                print(self.message)
                self.message = ''
        except KeyboardInterrupt:
            self.exit = True
            return 'break'
        except Exception as e:
            print('Something went wrong: ', e)
            return 'continue'
        return ''