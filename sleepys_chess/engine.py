import re
from .parsing import move_or_command
from .gamerules import GameState, create_game
from .utils import opposite, clear_screen

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
        
        self.command_log: list[str] = []
        self.message: str = ''
        
        self.checkpoint: GameState = None
        self.expiry_clock = 0 
        
    def update_clock(self, ticks: int =  1):
        self.message = None
        
        if self.expiry_clock < 0: # Undershoot
            self.expiry_clock = 0
            
        if self.expiry_clock > 0:
            self.expiry_clock -= ticks
        else:
            self.checkpoint = None
 
    def process_command(self, command_str):
            command_map = {
                r'/(undo|back)\s*(-?\d+)?\s*(b(?:lack)?|w(?:hite)?)?': self.game.undo,
                r'/?(resign|q(?:uit)?|give up)': self.resign,
                r'/?(exit|close)': self.exit_game,
                r'/(restart|reset)': self.restart,
                r'/(revert)': self.revert_undo,
                r'/?([?]|help|(?:list )?(?:all )?commands)': self.commands_help
            }
            
            for pattern, command in command_map.items():
                command_match = re.fullmatch(pattern, command_str, flags=re.I)
                if command_match:
                    command_name, *params = command_match.groups()
                    self.command_log.append(command_name)
                    if params:
                        command(*params)
                    else:
                        command()
                    break       
            else:
                self.message = f'The command "{command_str}" is not supported!'           
            return self
    
    def execute_undo(self, move_num=None, colour=None):
        self.game, self.checkpoint = self.game.undo(int(move_num), str(colour))
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
        self.game, self.checkpoint = self.game.undo(0) # undo(0) is analogous to restart
        if self.checkpoint: # Will be None if attempted on 1st move
            self.game.move_history = []
            self.game.position_count = {}
            self.game.position_history = {}
        else:
            self.message = 'Cannot restart on the first move'
        return self
        
    def revert_undo(self):
        if self.checkpoint:
            self.game = self.checkpoint
            self.checkpoint = None
        else:
            self.message = 'Could not revert'
        return self
    
    def commands_help(self):
        cmd_descs = {
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
    def run(self, fen_or_pgn: str=None, config=None):
        self.game = create_game(fen_or_pgn)
        while not self.exit:
            print(self.game) 
            player_move = input('Make a move! ')
            clear_screen() 
            try:
                self.handle_user_input(player_move)
                if self.message:
                    print(self.message)
                if self.exit:
                    break
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(e,'\nPlease try again.' )
                continue
            self.update_clock()
            self.game.check_if_end()
            
            if self.game.end_state == 'checkmate':
                # Update the representation of the winning player's last move
                self.game.move_history[-1][self.game.winner].check_str = '#'  
                
            if self.game.is_end:
                print(self.game)
                if self.game.winner == 'draw':
                    print(f'Draw by {self.game.end_state}')
                else:
                    print(f'{self.game.winner.capitalize()} won by {self.game.end_state}')
                    
                while True:
                    play_again = input('Would you like to play again? (Y/N) ')
                    if play_again.upper() in ['YES', 'Y']:
                        self.game = create_game(fen_or_pgn)
                        break
                    elif play_again.upper() in ['NO', 'N']:
                        self.exit = True
                        break  
                    else: 
                        print('Please answer only "yes" or "no"!')      
        print('Thanks for playing!')
        return
                