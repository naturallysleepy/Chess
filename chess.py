import re
import itertools
import copy
import os

# Program which runs a CLI chess game
FILES = 'abcdefgh'
RANKS = '12345678'
PIECE_TYPES = ['p', 'N', 'B', 'R', 'Q', 'K']
CHESS_PIECES = {
    'white': {'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'p': '♙'},
    'black': {'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'p': '♟'}
}
PIECE_NAMES = {'K': 'king', 'Q': 'queen', 'R': 'rook', 'B': 'bishop', 'N': 'knight', 'p': 'pawn'}
COLOURS = ['black', 'white'] 
SEN_PATTERN = r'(?:[KQRBN]?[a-h1-8]?x?[a-h][1-8](?:=[KQRBN])?|O-O(?:-O)?)[+#]?'
PGN_PATTERN = rf'(\d+\.?\s?{SEN_PATTERN}\s)((?:\d+\.\.\.)?{SEN_PATTERN}\s)'
FEN_PATTERN = r'(?:[rnbqkpRNBQKP1-8]{1,8}/){7}[rnbqkpRNBQKP1-8]{1,8} [wb] (?:[KQkq]{1, 4}|-) (?:[a-h][1-8]|-) \d+ \d+'
FEN_INITIAL = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 0'

class Piece:
    def __init__(self, type, colour):
        if colour not in COLOURS + [None]:
            raise ValueError('Invalid piece colour')
        if type not in PIECE_TYPES + [None]:
            raise ValueError('Invalid piece type')
        self.type: str | None = type # Will contain either 'p', 'B', 'K', 'Q', or 'N'
        self.colour: str | None = colour # Black or White
        
    def __eq__(self, other):
        return isinstance(other, Piece) and self.type == other.type and self.colour == other.colour
    def __repr__(self):
        return f"Piece('{self.type}', '{self.colour}')"
    def __str__(self):
        return CHESS_PIECES[self.colour][self.type]
    
class Move:
    def __init__(self, origin, destination, piece):
        self.origin: str | None = origin
        self.destination: str | None = destination
        self.piece: Piece | None = piece
        self.special: str = None
        self.promote: str = None
        self.is_capture: bool = False
        self.check_str: str = ''
        self.disambiguation: str = None
    def __repr__(self):
        return f"Move('{self.origin}', '{self.destination}', '{self.piece}', special: {self.special}, promote: {self.promote})"
    def __str__(self):
        string = ''
        check_symbol = self.check_str
        if self.special == 'castling':
            string += 'O-O' if self.destination[0] == 'g' else 'O-O-O'
            string += check_symbol
            return string
            
        if self.piece.type == 'p':
            if self.is_capture:
                string += f'{self.origin[0]}x'
            string += self.destination
            if self.special == 'promotion':
                string += f'={self.promote}' 

            string += check_symbol  
            return string
        
        string += f'{self.piece.type}'
        if self.disambiguation:
            string += f'{self.disambiguation}'
        if self.is_capture:
            string += 'x'
            
        string += self.destination
        string += check_symbol
        return string

class CommandState:
    def __init__(self):
        self.command_name: str = None
        self.message: str = None
        self.data = None
        self.exit = False  
        self.expiry_clock = 0 
        
    def update_clock(self, ticks: int =  1):
        if self.expiry_clock < 0: # Undershoot
            self.expiry_clock = 0
            
        if self.expiry_clock > 0:
            self.expiry_clock -= ticks
        else:
            self.command_name = None
            self.message = None
            self.data = None
            

        
class GameState:
    def __init__(self):
        self.board: dict[str, Piece | None] = {} 
        self.turn: str = 'white'
        self.white_king_pos: str = 'e1'
        self.black_king_pos: str = 'e8'
        self.can_castle: dict[str, bool] = {
            'white_kingside': True,
            'white_queenside': True,
            'black_kingside': True,
            'black_queenside': True
        }
        self.in_check: dict[str, bool] = {
            'white': False,
            'black': False
        }
        self.en_passant_target: str = None
        self.is_end: bool = False
        self.end_state: str = None
        self.winner: str = None
        self.move_history: list[dict[str: Move]] = []
        self.position_history: dict[int: str] = {}
        self.position_count: dict[str: int] = {}
        self.halfmove_clock: int = 0
        self.fullmoves: int = 0     
        
    def __repr__(self):
        return vars(self)
    
    def __str__(self):
        string_list = []
        board_string = ''
        # Sum of material value on each side of initial position
        default_material_value = 39 
        material_captured = {
                'black': '♛♜♜♝♝♞♞♟♟♟♟♟♟♟♟',
                'white': '♕♖♖♗♗♘♘♙♙♙♙♙♙♙♙'}
        material_value = {
                'p': 1,
                'N': 3,
                'B': 3,
                'R': 5,
                'Q': 9}
        material_sums = {
                'black': default_material_value,
                'white': default_material_value
        }
        board_list = []
        for rank in range(len(RANKS) + 1):
            rank_flipped = 8 - rank
            rank_list = []
            
            rank_list.append(f'{rank_flipped}' if rank_flipped > 0 else ' ')
            for i, file in enumerate(FILES):
                if rank_flipped == 0:
                    rank_list.append(file)
                else:
                    position = f'{file}{rank_flipped}'
                    if self.board[position]:
                        
                        piece = self.board[position]
                        rank_list.append(str(piece))
                        player_pieces = material_captured[piece.colour]
                        
                        if str(piece) in player_pieces:
                            # Find index of first occurrence of char in string
                            idx = material_captured[piece.colour].find(str(piece))
                            
                            # Remove char
                            player_pieces = player_pieces[:idx] + player_pieces[idx+1:]     
                            material_captured[piece.colour] = player_pieces
                            
                            # Remove value
                            material_sums[opposite(piece.colour)] -= material_value[piece.type]   
                            
                        elif piece.type != 'K': # Promoted pieces   
                            material_sums[piece.colour] += material_value[piece.type]          
                    else:
                        if (i % 2 == 1) == (rank_flipped % 2 == 1):
                            rank_list.append('□')
                        else:
                            rank_list.append('■')
            board_list.append(' '.join(rank_list))
        board_string = '\n'.join(board_list)    
        material = {
            'black': '',
            'white': ''
        }
        
        # Calculate material advantage
        for colour in COLOURS:
            material[colour] = material_captured[opposite(colour)] 
            advantage = material_sums[colour] - material_sums[opposite(colour)]
            if advantage > 0:
                material[colour] += f' +{advantage}'
            
        # Add board
        string_list.append(material['black'])
        string_list.append(board_string)
        string_list.append(material['white'] + '\n')
        
        history_string = ''
        if self.move_history:
            history_string = self.generate_pgn() 
            string_list.append('Move history: ' + history_string)
            
        fen_position = self.generate_fen()
        string_list.append('FEN: ' + fen_position)
            
        # Add other info like check notification or turn    
        other_string = ''
        for colour, is_check in self.in_check.items():
            if is_check:
                other_string += f'{colour.capitalize()} is in check!\n'
        if not self.is_end:
            other_string += f"{self.turn.capitalize()} to move."
        string_list.append(other_string)
            
        return '\n'.join(string_list)
    
    def empty_board(self):
        for file, rank in itertools.product(FILES, RANKS):
            pos = f'{file}{rank}'
            self.board[pos] = None
        return self
             
    def generate_fen(self) -> str:
        fen_board = ''
        board = self.board
        board_list = []
        to_fen = {'white': lambda x: x.upper(), 'black': lambda x: x.lower()}
        
        for rank in reversed(RANKS):
            this_rank = ''
            space_counter = 0
            for file in FILES:
                pos = f'{file}{rank}'
                piece = board[pos]
                if not piece:
                    space_counter += 1
                    if file == 'h' and space_counter != 0:
                        this_rank += f'{space_counter}'
                    continue
                if space_counter != 0:
                    this_rank += f'{space_counter}'
                
                this_rank += to_fen[piece.colour](piece.type)
                space_counter = 0
            board_list.append(this_rank)
        fen_board += '/'.join(board_list)
        
        fen_turn = self.turn[0]
        
        fen_castling = ''
        for case, can_castle in self.can_castle.items():
            colour, side = case.split('_')
            if can_castle:
                fen_castling += to_fen[colour](side[0])
        if not fen_castling:
            fen_castling = '-'
                
                
        fen_passant_target = self.en_passant_target if self.en_passant_target else '-'
        fen_halfmoves = f'{self.halfmove_clock}'
        fen_fullmoves = f'{self.fullmoves}'
        fen_fields = [fen_board, fen_turn, fen_castling, fen_passant_target, fen_halfmoves, fen_fullmoves]
        
        fen = ' '.join(fen_fields)
        return fen
            
    def generate_pgn(self, start_move: int = None, end_move: int = None) -> str:
        pgn_string = ''
        error = 0 if 'black' in self.move_history[-1] else 1

        start_num = self.fullmoves - len(self.move_history) + error
        history_start = None
        if start_move:
            history_start = start_move - start_num 
        history_end = None
        if end_move:
            history_end = end_move - start_num
            
        for i, moves in enumerate(self.move_history[history_start:history_end], 1):
            pgn_string += f'{start_num + i}.'
            if len(self.move_history[0]) == 1 and 'black' in self.move_history[0] and i == 1:
                pgn_string += '..'
            pgn_string += ' '
             
            for move_turn in moves.values():
                pgn_string += f'{move_turn} '
                 
        return pgn_string
    
    def load_fen(self, fen: str, is_start=True):
        self.empty_board()
        fen_fields = fen.split() 
        board, turn, castling, en_passant_target, half_moves, full_moves = fen_fields
        if not re.match(r'^([rnbqkpRNBQKP1-8]{1,8}(/|\Z)){8}$', board):
            raise ValueError('FEN is not valid!', fen)
        
        # Convert board
        rank = 8
        findex = 0
        for char in board:
            if char == '/':
                rank -= 1
                findex = 0
                continue
            elif re.match(r'\d', char):
                spaces = int(char)
                findex += spaces
                continue
            
            file = FILES[findex]
            pos = f'{file}{rank}'
            piece = Piece(None, None)
            if char.lower() == 'p':
                piece.type = 'p'
            elif char.upper() in PIECE_TYPES:
                piece.type = char.upper()
            
            if char.isupper():
                piece.colour = 'white'
            else: 
                piece.colour = 'black'
                
            if char == 'k':
                self.black_king_pos = pos
            elif char == 'K':
                self.white_king_pos = pos
                
            if piece.type == None or piece.colour == None:
                findex += 1
                continue
            else: 
                self.board[pos] = piece
                
            findex += 1    
            
        self.turn = 'white' if turn == 'w' else 'black'
        
        to_fen = {'white': lambda x: x.upper(), 'black': lambda x: x.lower()}
        if castling != '-':
            for key in self.can_castle.keys():
                colour, side = key.split('_')
                self.can_castle[f'{colour}_{side}'] = to_fen[colour](side[0]) in castling
                king_pos = self.black_king_pos if colour == 'black' else self.white_king_pos
                self.in_check[colour] = square_is_attacked(king_pos, (self.board, colour))
                
        if en_passant_target != '-':
            self.en_passant_target = en_passant_target
        self.halfmove_clock = int(half_moves)
        
        self.fullmoves = int(full_moves) if (full_moves and full_moves != '-') else 0
        
        if is_start:
            self.position_history[0] = fen
        return self 
        
    def load_pgn(self, pgn: str):
        # Metadata headers 
        pgn = strip_brackets(pgn, '[', ']')
        
        # Comments {...} and ;... 
        pgn = strip_brackets(pgn, '{', '}')
        pgn = re.sub(r';[^\n]*\s*?', '', pgn)
        
        # Alt lines: (...)
        pgn = strip_brackets(pgn, '(', ')')
        
        pgn_tokens = pgn.split()
        num_pattern = r'\d+\.(?:\.\.)?'
        for token in pgn_tokens:
            if token in ['1-0', '0-1']:
                self.winner = 'white' if token == '1-0' else 'black'
                if not self.is_end:
                    self.is_end = True
                    self.end_state = 'resignation'
                break
            elif token == '1/2-1/2':
                self.winner = 'draw'
                if not self.is_end:
                    self.is_end = True
                    self.end_state = 'agreement'
                break
            elif not re.match(SEN_PATTERN, token):
                continue
                
            item = token
            num_match = re.match(num_pattern, item)
            if num_match:
                item = re.sub(num_pattern, '', item)
            if not item:
                continue 
            try:
                self.process_player_move(item)
            except Exception as e:
                print(f'Failed to process {item}. See:', e)
                break
            
            self.check_if_end()  
            
            # Add checkmate marker
            if self.end_state == 'checkmate':
                self.move_history[-1][self.winner].check_str = '#'
        return self  
      
    def undo(self, dest_move: int = None, colour: str = None):
        is_restart = dest_move == 0
        if dest_move is None:
            dest_move = self.fullmoves - 1
        elif dest_move < 0:
            dest_move = self.fullmoves + dest_move
        if colour is None:
            colour = self.turn
        
        first_move_num = abs(self.fullmoves - len(self.move_history))
        
        if (dest_move < first_move_num and dest_move != 0) or dest_move > self.fullmoves:
            raise ValueError(f'Cannot undo: move {dest_move} does not exist')
        elif dest_move == self.fullmoves:
            return self, None # Do literally nothing
        
        snapshot = copy.deepcopy(self) # Snapshot is held for one full move for option to revert
        
        new_game = GameState()
        new_game.load_fen(self.position_history[0])
        desired_pgn = None
        if not is_restart:
            desired_pgn = self.generate_pgn(end_move=dest_move)
            new_game.load_pgn(desired_pgn)
            if new_game.turn != colour :
                new_game.process_player_move(str(self.move_history[dest_move][opposite(colour)]))
        self = new_game
                    
        return self, snapshot 
    
    def process_player_move(self, player_move: str):
        last_passant = self.en_passant_target
        move_info = parse_move(player_move, re.IGNORECASE)
        validated = None
        
        if isinstance(move_info, list): # Ambiguous
            potential_moves = []
            conflicts = set()
            for move_dict in move_info:
                potential_move = validate_move(move_dict, self, self.turn)
                if isinstance(potential_move, Move):
                    potential_moves.append(potential_move)
                if isinstance(potential_move, list):
                    conflicts.add(potential_move)
            
            if len(potential_moves) == 1:
                validated = potential_moves[0]
            elif len(potential_moves) == 0 and conflicts:
                validated = conflicts
            else:
                raise Exception(f'Could not validate {player_move}')
        else: # Unambiguous
            validated = validate_move(move_info, self, self.turn)
            
        if isinstance(validated, set):
            raise Exception('Move is ambiguous', validated) 
        elif validated:
            last_turn = self.turn
            self = make_move(validated, self)[0]
                
            # Update king position
            if validated.piece == Piece('K', 'black'):
                self.black_king_pos = validated.destination
            elif validated.piece == Piece('K', 'white'):
                self.white_king_pos = validated.destination
                
            if last_passant == self.en_passant_target: # Only flags if no en_passant performed
                self.en_passant_target = None
            if validated.is_capture or validated.piece.type == 'p':
                self.halfmove_clock = 0
            else:
                self.halfmove_clock += 1
            
            # Update self history
            snapshot = self.generate_fen()
            if last_turn == 'black':
                if self.move_history:
                    self.move_history[-1][last_turn] = validated # PGN analog
                else:
                    self.move_history.append({last_turn: validated}) # If black is first move
                self.fullmoves += 1
            else:
                self.move_history.append({last_turn: validated}) # PGN analog
                self.position_history[self.fullmoves + 1] = snapshot # FEN analog
            snapshot_position = snapshot[:-4]
            if snapshot_position not in self.position_count:
                self.position_count[snapshot_position] = 0
            self.position_count[snapshot_position] += 1
            
            # Update check and last move notation
            self = update_check(self)
            if any(self.in_check.values()):
                self.move_history[-1][last_turn].check_str = '+'
                
        return self  
  
    def check_if_end(self):
        player = self.turn
        has_legal_moves = self.legal_moves(flag='any')
        last_position = self.generate_fen()
        
        if self.in_check[player] and not has_legal_moves:
            self.is_end = True
            self.end_state = 'checkmate'
            self.winner = opposite(player)
        elif not has_legal_moves:
            self.is_end = True
            self.end_state = 'stalemate'
            self.winner = 'draw'
        elif last_position[:-4] in self.position_count and self.position_count[last_position[:-4]] == 3:
            self.is_end = True
            self.end_state = 'threefold repetition'
            self.winner = 'draw'
        elif self.halfmove_clock >= 100:
            self.is_end = True
            self.end_state = '50 move rule'
            self.winner = 'draw'
                
        return self
       
    def legal_moves(self, flag=None):
        if flag not in ['any', None]:
            raise ValueError('Invalid flag for legal_moves()')
        
        legal_moves = []
        for square, piece in self.board.items():
            file, rank = [*square]
            rank = int(rank)
            if piece and piece.colour == self.turn:
                search_squares = []
                
                match piece.type:
                    case 'p': 
                        search_squares = find_pawn_attacks(file, rank, self.turn)
                        sign = 1 if self.turn == 'white' else -1
                        search_squares.append(f'{file}{rank + sign}')
                        if rank == (7 if self.turn == 'black' else 2):
                            search_squares.append(f'{file}{rank + 2 * sign}')
                    case 'N': search_squares = find_knight_attacks(file, rank)
                    case 'B': search_squares = find_bishop_attacks(file, rank, self.board)
                    case 'R': search_squares = find_rook_attacks(file, rank, self.board)
                    case 'Q': search_squares = find_bishop_attacks(file, rank, self.board) + find_rook_attacks(file, rank, self.board)
                    case 'K': 
                        search_squares = find_king_attacks(file, rank)
                        if square == ('e1' if self.turn == 'white' else 'e8'):
                            search_squares += [f'g{rank}', f'c{rank}']
                    
                # True if any moves exist
                if search_squares and flag == 'any':
                    for dest in search_squares:
                        move = Move(square, dest, piece)
                        if is_legal_move(move, self):
                            return True
                elif search_squares: # Collect all legal moves
                    for dest in search_squares:
                        move = Move(square, dest, piece)
                        if is_legal_move(move, self):
                            legal_moves.append(move)     
                            
        if flag == 'any':
            return False
        else:
            return legal_moves   
           
    def process_command(self, input, command_state: CommandState):
        command_state.message = None
        match_patterns = {'undo': r'(undo|back)\s*(-?\d+)?\s*(b(?:lack)?|w(?:hite)?)?',
                          'resign': r'(resign|q(?:uit)?|give up)',
                          'exit': r'(exit|close)',
                          'restart': r'(restart|reset)',
                          'revert': r'(revert)',
                          'help': r'([?]|help|(?:list )?(?:all )?commands)'}
        
        command = None
        params = None
        for name, pattern in match_patterns.items():
            command_match = re.fullmatch(pattern, input, flags=re.I)
            if command_match:
                command, *params = command_match.groups()
                command = name
                break
        else:
            command_state.message = f'The command "{input}" is not supported!'

        if command:
            command_state.command_name = command
        match command:
            case 'exit': command_state.exit = True
            
            case 'undo': 
                move_num = None
                colour = None
                if params[0]:
                    move_num = int(params[0])
                if params[1]:
                    colour = 'white' if params[1] in 'white' else 'black'
                self, command_state.data = self.undo(move_num, colour)
                command_state.expiry_clock = 3
                
            case 'restart': 
                self, command_state.data = self.undo(0)
                if command_state.data:
                    self.move_history = []
                    self.position_count = {}
                    self.position_history = {}
                else:
                    command_state.message = 'Cannot restart on the first move'
                
            case 'revert': 
                if isinstance(command_state.data, GameState):
                    self = command_state.data
                else:
                    command_state.message = 'Could not revert'
                    
            case 'resign':
                self.is_end = True
                self.winner = opposite(self.turn)
                self.end_state = 'resignation'
                
            case 'help':
                cmd_descs = {
                    'undo [n]th [colour] move (n < 0 goes back n moves, n = 0 identical to restart)': '"undo"/"back" +(optional: [n: default=-1] [colour: default=current turn])',
                    'revert to game state prior to last undo': '"revert"',
                    'reset game to 1st move': '"restart"/"reset"',
                    'resign current game': '"resign"/"quit"',
                    'exit program': '"exit"/"close"',
                    'display command descriptions and usage': '"?"/"help"'
                }
                command_state.message = ''
                for desc, usage in cmd_descs.items():
                    command_state.message += f'Description: {desc}\nUsage: {usage}\n\n'
                    
        return self, command_state
        
    
def main():
    clear_screen()
    cmd = CommandState()

    while not cmd.exit:
        # Make game
        game = GameState()
        game_to_load = ''
        content = None
        pgn = None
        fen = None
        
        prompt = "Please input a path of the game you'd like to load in FEN or PGN format, else press Enter to start from the default chess position. Optionally you may paste the FEN/PGN string into the terminal\n"
        while True:
            game_to_load = input(prompt).strip()
            if not game_to_load:
                break
            
            if any(extension == game_to_load[-4:] for extension in ['.pgn', '.fen', '.txt']):
                with open(game_to_load, "r") as file:
                    content = file.read()
                if '.pgn' in game_to_load:
                    pgn = content
                elif '.fen' in game_to_load:
                    fen = content
                    break
            else:
                content = game_to_load     
             
            move_tuples = re.findall(PGN_PATTERN, content)
            moves = ''
            for move in move_tuples:
                moves += ''.join(move)
                    
            pgn = moves
            fen = re.findall(FEN_PATTERN, content) 
            if fen:
                fen = fen[0]
                
            if fen or pgn:
                break
            else: 
                print('This notation/file is either invalid or not supported, please try again.')

        if not fen:
            fen = FEN_INITIAL 
        game.load_fen(fen)
        if pgn:
            game.load_pgn(pgn)   
               
        continue_game = not game.is_end
        while continue_game and not cmd.exit:   
            print(game) # Print board 
            player_move = input('Play a move! \n')
            clear_screen()
            
            # Non-move inputs
            if not re.fullmatch(SEN_PATTERN, player_move, re.I):
                try:
                    game, cmd = game.process_command(player_move, cmd)
                    if cmd.message:   
                        print(cmd.message)
                except Exception as e:
                    print('Something went wrong:', e)
                finally:
                    continue_game = not game.is_end
                    continue
            
            try:    
                game.process_player_move(player_move)
                cmd.update_clock()
            except Exception as e:
                print(e, '\nPlease try again!')
                
            game.check_if_end()  
            continue_game = not game.is_end
            
            # Add checkmate marker
            if game.end_state == 'checkmate':
                game.move_history[-1][game.winner].check_str = '#'
        if cmd.exit:
            break
        print(game) # Print board    
            
        if game.winner and game.winner != 'draw': # Win
            print(f'{game.winner.capitalize()} won by {game.end_state.capitalize()}!')
        elif game.winner: # Draw
            print(f'Draw by {game.end_state.capitalize()}!')
        else:
            print('Undefined game end state')
            
        while True:
            play_again = input('Would you like to play again? ')
            if re.fullmatch(r'n(?:o)?|q(?:uit)?|exit|bye', play_again, re.IGNORECASE):
                cmd.exit = True
                break
            elif re.fullmatch(r'play(?: again)?|y(?:es)?', play_again, re.IGNORECASE):
                continue_game = True
                print('Setting up new game...')
                break  
            else:
                print('Input not recognized. Try "no" to exit else "yes" to play again!')
    print('Thanks for playing!')
    return
                
def strip_brackets(text, open='(', close = ')'):
    result = []
    depth = 0
    for i, char in enumerate(text):
        if depth == 0 and char == close:
            print(f'Alert, mismatched {close} at', i)
            
        if char == open:
            depth += 1
        elif char == close:
            if depth > 0:
                depth -= 1
        elif depth == 0:
            result.append(char)
        
    return ''.join(result)

# Parse moves in chess notation
def parse_move(player_move, re_flags=0) -> list[dict] | dict: 
    # Finds and groups move data
    token_patterns = {
        'pawn':r'^((?P<origin>[a-h])(?P<capture>x))?(?P<destination>[a-h][2-7])(?P<check>\+|#)?$',
        'promotion': r'^((?P<origin>[a-h])(?P<capture>x))?(?P<destination>[a-h][18])(=(?P<promotion>[NBRQ]))(?P<check>\+|#)?$',
        'piece': r'^(?P<piece>[NBRQK])(?P<origin>[a-h1-8])?(?P<capture>x)?(?P<destination>[a-h][1-8])(?P<check>\+|#)?$',
        'castling': r'^(?P<side>O-O(-O)?)(?P<check>\+|#)?$'
    }
    move_type = None
    matches = []
    for label, pattern in token_patterns.items():
        # Use re_flags = re.IGNORECASE for case insensitivity
        matched = re.match(pattern, player_move, re_flags)
        groups = {}
        if matched:
            move_type = label
            groups = matched.groupdict()
            move_data = normalize_move_data({'move': player_move, 'type': move_type, 'details': groups})
            matches.append(move_data)
            
    if not matches:     
        raise ValueError('Invalid move')
    if len(matches) > 1:
        return matches # Ambiguous case
    
    # Others are false, there is only 1 match
    return matches[0] 

def normalize_move_data(move_data: dict):
    details: dict = move_data['details'] # Reference, not copy
    
    lower_flags = ['origin', 'capture', 'destination']
    for flag in lower_flags:
        if flag in details and details[flag]:
            details[flag] = details[flag].lower()
            
    upper_flags = ['piece', 'promotion', 'side']
    for flag in upper_flags:
        if flag in details and details[flag]:
            details[flag] = details[flag].upper()
        
    key_order = ['piece', 'origin', 'capture', 'destination', 'promotion', 'side', 'check'] # Preserve algebraic notation order
    normalized = ''
    for key in key_order:
        component = details.get(key, '')
        if component:
            if key == 'promotion':
                component = f'={component}'
            normalized += component # Rebuild normalized move

    move_data['move'] = normalized
    return move_data

def opposite(colour : str):
    if colour not in ['white', 'black']:
        raise ValueError('Invalid colour')
    return 'white' if colour == 'black' else 'black'
    
def validate_move(move_data : dict, game : GameState, player : str):
    board = game.board
    move_notation, move_type, move_details = move_data.values()
    
    destination = None
    is_capture = False
    if 'destination' in move_details:
        destination = move_details['destination']
        dest_file, dest_rank = [*destination]
        dest_rank = int(dest_rank)
        is_capture = (destination == game.en_passant_target and move_type == 'pawn') or board[destination] is not None

    
    # Capture exists, not in syntax
    if is_capture and 'capture' in move_details and move_details['capture'] is None: 
        print('Invalid syntax: Capture not specified')
        return None
    # Capture does not exist, exists in syntax
    elif not is_capture and 'capture' in move_details and move_details['capture'] is not None:
        print('Invalid syntax: This move is not a capture')
        return None
        
    match move_type:
        case 'pawn':
            '''Find pawn position'''
            sign = 1 if player == 'white' else -1
            
            # Files only change when pawn captures
            origin_file = move_details['origin'] if move_details['capture'] else dest_file
            origin_rank = dest_rank - sign
            double_rank = 4 if player == 'white' else 5
            if dest_rank == double_rank:
                potential_o_ranks = [dest_rank - 2 * sign, dest_rank - sign]
                for o_rank in potential_o_ranks.copy():
                    pos = f'{origin_file}{o_rank}'
                    if board[pos] != Piece('p', player):
                        potential_o_ranks.remove(o_rank)
                
                if len(potential_o_ranks) == 1:
                    origin_rank = potential_o_ranks[0]
                elif len(potential_o_ranks) == 2:
                    # The pawn closest to double rank should move
                    origin_rank =  min(potential_o_ranks, key = lambda r: abs(double_rank - r))
                else:
                    print(f'No {player} pawn that can move to {destination}.')
                    return None
            
            # Found coordinates
            pawn_origin = f'{origin_file}{origin_rank}'
            pawn = board[pawn_origin]
            is_double = (abs(origin_rank - dest_rank) == 2)
            is_en_passant = (destination == game.en_passant_target)
            
            move = Move(pawn_origin, destination, pawn)
            move.is_capture = is_en_passant or is_capture
            if is_en_passant:
                move.special = 'en passant'
            
            '''Check if pawn exists at location and move is legal'''
            if pawn == Piece('p', player) and is_legal_move(move, game):
                if is_double:
                    game.en_passant_target = f'{dest_file}{dest_rank - sign}'
                return move
            else:
                print(f'Cannot move pawn to {destination}')
                return None
            
        case 'promotion':
            '''Find pawn''' 
            origin_rank = '7' if player == 'white' else '2'
            origin_file = move_details['origin'] if move_details['capture'] else dest_file
            pawn_origin = f'{origin_file}{origin_rank}'
            pawn = board[pawn_origin]
            
            promote_type = move_details['promotion']
            move = Move(pawn_origin, destination, pawn)
            move.is_capture = is_capture
            move.special, move.promote = 'promotion', promote_type
            if pawn == Piece('p', player) and is_legal_move(move, game):
                return move
            else:
                print(f'{move_notation} is not a legal move.')
                return None
            
        case 'piece':
            piece_type = move_details['piece'] 
            piece_name = PIECE_NAMES[piece_type]
            
            origin_hint = move_details['origin'] # Sometimes None
            piece = Piece(type = piece_type, colour = player)
            
            # Find desired piece
            search_squares = None
            match piece_type:
                case 'N': search_squares = find_knight_attacks(dest_file, dest_rank)
                case 'B': search_squares = find_bishop_attacks(dest_file, dest_rank, game.board)
                case 'R': search_squares = find_rook_attacks(dest_file, dest_rank, game.board)
                case 'Q': search_squares = find_bishop_attacks(dest_file, dest_rank, game.board) + find_rook_attacks(dest_file, dest_rank, game.board)
                case 'K': search_squares = find_king_attacks(dest_file, dest_rank)
                
            origin = set()
            for square in search_squares:
                if board[square] == piece:
                    origin.add(square)
            if not origin:
                print(f'There is no {player} {piece_name} that can travel to {destination}')
                return None
                
            conflict = len(origin) > 1
            if conflict:
                for square in origin:
                    if origin_hint and origin_hint in square:
                        origin = square
                        break
                else:
                    print(f'There are multiple valid {piece_name}s which can move to {destination}.')
                    return origin
            else:
                origin = list(origin)[0]
            
            move = Move(origin, destination, piece)
            move.disambiguation = origin_hint
            move.is_capture = is_capture
            if is_legal_move(move, game):
                return move
                          
        case 'castling':
            # Castling only valid if king is on home square
            origin = 'e1' if player == 'white' else 'e8'
            king = board[origin] 
            file = 'g' if move_details['side'] == 'O-O' else 'c'
            rank = origin[-1]
            destination = f'{file}{rank}'
            
            move = Move(origin, destination, king)
            move.special = 'castling'
            if king == Piece(type='K', colour=player) and is_legal_move(move, game):
                return move
            else:
                print(f'{move_notation} is not a legal move.')
                return None
    print(f'{move_notation} is not a legal move.')
    return None

def is_legal_move(move: Move, game : GameState) -> bool | list[Move]:
    board = game.board
    piece = board[move.origin]
    king_pos = ''
    if move.piece.type == 'K':
        king_pos = move.destination
    else:
        king_pos = game.white_king_pos if piece.colour == 'white' else game.black_king_pos
        
    king_is_safe = square_remains_safe(king_pos, move, game, piece.colour)
    if not king_is_safe or is_friendly(move.destination, piece, board) or not piece == move.piece:
        return False
    opp_colour = opposite(move.piece.colour)
    
    if not board[move.destination] and move.is_capture and move.special != 'en passant':
        return False
    
    # Initial position
    init_file, init_rank = [*move.origin]
    init_rank = int(init_rank)
    init_findex = FILES.index(init_file)
    
    dest_file, dest_rank = [*move.destination]
    dest_rank = int(dest_rank)
    dest_findex = FILES.index(dest_file)
    match piece.type:
        case 'p':
            rank_steps = dest_rank - init_rank
            file_steps = dest_findex - init_findex
            factor = 1 if piece.colour == 'white' else -1
            
            if abs(file_steps) > 1:
                return False
            elif abs(file_steps) == 1 and rank_steps == factor: # Pawn capture 
                if board[move.destination]:
                    return board[move.destination].colour == opp_colour
                else:
                    return move.destination == game.en_passant_target
            else:
                if rank_steps == 2 * factor: # Double step
                    path_is_clear = all(not board[f'{init_file}{init_rank + i * factor}'] for i in [1, 2])
                    double_is_valid = init_rank == (2 if piece.colour == 'white' else 7)
                    
                    return path_is_clear and double_is_valid
                elif rank_steps == factor:
                    return not board[move.destination]
        case 'N':
            v_comps = {abs(init_findex - dest_findex), abs(init_rank - dest_rank)} # Vector components
            if v_comps == {1, 2}:
                return True 
        case 'B': 
            rank_steps = dest_rank - init_rank
            file_steps = dest_findex - init_findex
            if abs(rank_steps) != abs(file_steps):
                return False
            
            rsign = 1 if rank_steps > 0 else -1
            fsign = 1 if file_steps > 0 else -1
            
            for step in range(1, abs(file_steps)): # Squares in path except dest
                trace_rank = init_rank + rsign * step
                trace_findex = init_findex + fsign * step
                trace_file = FILES[trace_findex]
                trace_dest = f'{trace_file}{trace_rank}' 
                if board[trace_dest]:
                    return False
            return True
        case 'R':
            rank_steps = dest_rank - init_rank
            file_steps = dest_findex - init_findex
            if (rank_steps == 0) == (file_steps == 0): # XNOR pattern
                return False
            
            steps = rank_steps if rank_steps != 0 else file_steps
            sign = 1 if steps > 0 else -1
            
            for step in range(1, abs(steps)): 
                trace_findex = init_findex + step * sign if file_steps != 0 else init_findex
                trace_file = FILES[trace_findex]
                trace_rank = init_rank + step * sign if rank_steps != 0 else init_rank 
                trace_dest = f'{trace_file}{trace_rank}'
                if board[trace_dest]:
                    return False
            return True
        case 'Q':
            rank_steps = dest_rank - init_rank
            file_steps = dest_findex - init_findex
            if abs(rank_steps) == abs(file_steps): # Bishop pattern
                rsign = 1 if rank_steps > 0 else -1
                fsign = 1 if file_steps > 0 else -1
            
                for step in range(1, abs(file_steps)): 
                    trace_rank = init_rank + rsign * step
                    trace_findex = init_findex + fsign * step
                    trace_file = FILES[trace_findex]
                    trace_dest = f'{trace_file}{trace_rank}' 
                    if board[trace_dest]:
                        return False
                return True 
            elif (rank_steps == 0) != (file_steps == 0): # XOR pattern
                steps = rank_steps if rank_steps != 0 else file_steps
                sign = 1 if steps > 0 else -1
                
                for step in range(1, abs(steps)): # Rook pattern
                    trace_findex = init_findex + step * sign if file_steps != 0 else init_findex
                    trace_file = FILES[trace_findex]
                    trace_rank = init_rank + step * sign if rank_steps != 0 else init_rank 
                    trace_dest = f'{trace_file}{trace_rank}'
                    if board[trace_dest]:
                        return False
                return True
        case 'K':        
            '''Castling'''
            if move.special == 'castling':
                if can_castle_kingside(piece, game):
                    target = f'g{init_rank}'
                    if move.destination == target:
                        return True
                if can_castle_queenside(piece, game):
                    target = f'c{init_rank}'
                    if move.destination == target:
                        return True
            else:
                v_comps = [abs(init_findex - dest_findex), abs(init_rank - dest_rank)] # Vector components
                is_single_step = max(v_comps) == 1 and sum(v_comps) > 0
                is_safe = square_remains_safe(move.destination, move, game, move.piece.colour)
                if is_single_step and is_safe:
                    return True
    return False

def square_remains_safe(square: str, move: Move, game: GameState, colour: str):
    return not square_is_attacked(square, (simulate_move(move, game).board, colour))

def simulate_move(move : Move, game : GameState):
    clone_game = copy.deepcopy(game)
    clone_game = make_move(move, clone_game)[0]
    return clone_game
    
def make_move(move: Move, game : GameState):
    piece = game.board[move.origin]
    if piece and piece.colour == game.turn:
        back_rank = 1 if piece.colour == 'white' else 8
        if move.special == 'en passant':
            target_file, target_rank = [*game.en_passant_target]
            target_rank = int(target_rank)
            target_rank = target_rank + 1 if game.turn == 'black' else target_rank - 1
            target = f'{target_file}{target_rank}'
            
            game.board[target] = None # Delete target piece
            game.board.update({move.origin: None, move.destination: piece})
        elif move.special == 'castling':
            dest_file, dest_rank = [*move.destination]
            rook_origin = f'a{back_rank}' if dest_file == 'c' else f'h{back_rank}'
            rook_destination = f'd{back_rank}' if dest_file == 'c' else f'f{back_rank}'
            rook = game.board[rook_origin]
            game.board.update({move.origin: None, move.destination: piece, rook_origin: None, rook_destination: rook}) 
            
            # Update castling info 
            game.can_castle[f'{piece.colour}_kingside'] = False
            game.can_castle[f'{piece.colour}_queenside'] = False      
        elif move.special == 'promotion':
            promoted = Piece(type=move.promote, colour=piece.colour)
            game.board.update({move.origin: None, move.destination: promoted})
        else:
            game.board.update({move.origin: None, move.destination: piece})
            
        
        if piece.type == 'R' and move.origin in [f'a{back_rank}', f'h{back_rank}']:
            side = '_queenside' if move.origin[0] == 'a' else '_kingside'
            game.can_castle[f'{piece.colour}{side}'] == False
        if piece.type == 'K':
            game.can_castle[f'{piece.colour}_kingside'] = False
            game.can_castle[f'{piece.colour}_queenside'] = False
        
        # Update game data
        last_turn = game.turn
        game.turn = 'black' if last_turn == 'white' else 'white'
        if piece.type == 'K' and last_turn == 'white':
            game.white_king_pos = move.destination
        elif piece.type == 'K' and last_turn == 'black':
            game.black_king_pos = move.destination
        
    else:
        raise ValueError('Invalid Move: Piece does not exist')
    return game, piece

def is_friendly(target : str, piece : Piece, board : dict):
    return board[target] and board[target].colour == piece.colour

def can_castle_kingside(piece: Piece, game: GameState):
    r = '1' if piece.colour == 'white' else '8'
    return game.can_castle[f'{piece.colour}_kingside'] and area_is_empty([f'f{r}', f'g{r}'], game) and area_is_safe([f'e{r}', f'f{r}', f'g{r}'], game)

def can_castle_queenside(piece: Piece, game: GameState):
    r = '1' if piece.colour == 'white' else '8'
    return game.can_castle[f'{piece.colour}_queenside'] and area_is_empty([f'd{r}', f'c{r}'], game) and area_is_safe([f'e{r}', f'd{r}', f'c{r}'], game)

def area_is_safe(squares, game : GameState):
    return not any(square_is_attacked(square, game) for square in squares)

def area_is_empty(squares, game: GameState):
    return not any(game.board[square] for square in squares)

def square_is_attacked(square : str, game : GameState | tuple[dict[str : Piece | None], str]) -> bool: # Do not pass attacking colour
    if isinstance(game, GameState):
        board = game.board 
        colour = game.turn
    elif isinstance(game, tuple):
        board, colour = game 
    else:
        raise ValueError(f'Invalid argument supplied to square_is_attacked(). \n{game} is not a valid type.') 
    
    opp_colour = opposite(colour)
    file, rank= [*square]
    
    # Check for pawns
    pawn_attacks = find_pawn_attacks(file, rank, colour)
    if find_attacker(pawn_attacks, ['p', 'B', 'Q', 'K'], board, opp_colour):
        return True
    
    # Check for knights
    knight_attacks = find_knight_attacks(file, rank)
    if find_attacker(knight_attacks, ['N'], board, opp_colour):
        return True
    
    # Check for bishops and queens
    diagonal_attacks = find_bishop_attacks(file, rank, board)
    if find_attacker(diagonal_attacks, ['B', 'Q'], board, opp_colour):
        return True
    
    # Check for rooks and queens
    orthog_attacks = find_rook_attacks(file, rank, board)
    if find_attacker(orthog_attacks, ['R', 'Q'], board, opp_colour):
        return True
    
    # Check for king 
    king_attacks = find_king_attacks(file, rank)
    if find_attacker(king_attacks, ['K'], board, opp_colour):
        return True
    
    return False
    
def find_pawn_attacks(file, rank, colour : str, is_pawn=True) -> list[str]:
    attacks = []
    rank = int(rank)
    if is_pawn and (rank == 8 or rank == 1):
        return attacks
    for d in [-1, 1]:
        attack_rank = rank + 1 if colour == 'white' else rank - 1
        init_findex = FILES.index(file)
        # Avoid index issues
        if init_findex + d not in range(len(FILES)):
            continue
        attack_file = FILES[init_findex + d]
        attack_target = f'{attack_file}{attack_rank}'
        attacks.append(attack_target)
    return attacks
    
def find_knight_attacks(file, rank) -> list[str]:
    rank = int(rank)
    init_findex = FILES.index(file)
    attacks = []
    for f, r in itertools.product(range(-2, 2 + 1), range(-2, 2 + 1)):
        if abs(f) == abs(r) or init_findex + f not in range(len(FILES)) or str(rank + r) not in [*RANKS]:
            continue
        if {abs(f), abs(r)} != {1, 2}:
            continue
        target_file = FILES[init_findex + f]
        target_rank = rank + r
        target = f'{target_file}{target_rank}'
        attacks.append(target)
    return attacks

def find_bishop_attacks(file, rank, board : dict [str, None | Piece]):
    rank = int(rank)
    targets = []
    init_findex = FILES.index(file)
    for fsign, rsign in itertools.product([-1, 1], [-1, 1]):
        offset = 1 
        while str(rank + rsign * offset) in [*RANKS] and  init_findex + fsign * offset in range(len(FILES)):    
            target_rank = rank + rsign * offset
            target_findex = init_findex + fsign * offset
            target_file = FILES[target_findex]
            target = f'{target_file}{target_rank}'
            
            targets.append(target)
            if board[target]:
                # Blocking
                break
            offset += 1   
    return targets

def find_rook_attacks(file, rank, board : dict[str : Piece | None]):
    rank = int(rank)
    targets = []
    init_findex = FILES.index(file)
    for ffactor, rfactor in itertools.product(range(-1, 1 + 1), range(-1, 1 + 1)):
        # Logical XNOR so that exactly one factor is 0
        if (ffactor == 0) == (rfactor == 0):
            continue
        offset = 1 
        while str(rank + rfactor * offset) in [*RANKS] and init_findex + ffactor * offset in range(len(FILES)):    
            target_rank = rank + rfactor * offset
            target_findex = init_findex + ffactor * offset
            target_file = FILES[target_findex]
            target = f'{target_file}{target_rank}'
            
            targets.append(target)
            if board[target]:
                # Blocking
                break
            offset += 1 
    return targets

def find_king_attacks(file, rank):
    rank = int(rank)
    targets = []
    init_findex = FILES.index(file)
    
    for ffactor, rfactor in itertools.product(range(-1, 1 + 1), range(-1, 1 + 1)):
        if all([ffactor == 0, rfactor == 0]): # Prevent not moving
            continue
        offset = 1 
        if str(rank + rfactor * offset) in [*RANKS] and  init_findex + ffactor * offset in range(len(FILES)):    
            target_rank = rank + rfactor * offset
            target_findex = init_findex + ffactor * offset
            target_file = FILES[target_findex]
            target = f'{target_file}{target_rank}'
            targets.append(target)
    return targets
                       
def find_attacker(attacks : list, types : list, board : dict[str : Piece | None], opponent : str) -> bool:
    if not attacks:
        return False
    
    for attack in attacks:
        attacker = board[attack]
        if attacker and attacker.colour == opponent and attacker.type in types:
            return True
    return False
    
def update_check(game: GameState):
    for colour in COLOURS:
            king_pos = game.black_king_pos if colour == 'black' else game.white_king_pos
            game.in_check[colour] = square_is_attacked(king_pos, (game.board, colour))
    return game

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

if __name__ == '__main__':
    main()
