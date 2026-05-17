# Built ins
from __future__ import annotations
import re, copy

from .moves import Move 
from . import moverules as mr
from .parsing import parse_move, FEN_INITIAL

from .board import Board, FILES
from .pieces import Piece, is_friendly

from .parsing import parse_initial_state, SAN_PATTERN
from .utils import opposite, strip_brackets, is_colour

HALFMOVE_LIMIT = 100
REP_LIMIT = 3

class IllegalMove(Exception):
    pass

class AmbiguityError(Exception):
    pass

class IllegalState(Exception):
    pass

class GameState:
    def __init__(self, fen=None, pgn=None):
        self.board = Board()
        self.turn: str = 'white'
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
        self.is_end: bool = False
        self.end_state: str | None = None
        self.winner: str | None = None
        self.move_history: list[tuple[str, Move]] = [] # Last index = ply - 1
        self.position_history: dict[int, str] = {} # Ply-based
        self.position_count: dict[str, int] = {}
        self.halfmove_clock: int = 0
        self.fullmoves: int = 1 
        self.ply: int = 0 
        
        if fen is None:
            self.load_fen(FEN_INITIAL) 
        else:
            self.load_fen(fen)  
            
        if pgn:
            self.load_pgn(pgn)
        
    def __repr__(self):
        return vars(self)
    
    def get_info(self, perspec: str | None = None) -> list[str]:
        if not perspec and not self.board.perspective:
            perspec = self.turn
        elif not perspec:
            perspec = self.board.perspective

        if not is_colour(perspec):
            raise ValueError('Invalid perspec passed to .get_info()')

        string_list = []
        board_string = self.board.render(perspec)  
        
        # Add board
        string_list.append(board_string + '\n')
        
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
            
        return string_list

    def __str__(self):
        return '\n'.join(self.get_info())
                
    def generate_fen(self) -> str:
        to_fen = {'white': lambda x: x.upper(), 'black': lambda x: x.lower()}
        
        fen_board = self.board.board_to_fen()
        
        fen_turn = self.turn[0]
        
        fen_castling = ''
        for case, can_castle in self.can_castle.items():
            colour, side = case.split('_')
            if can_castle:
                fen_castling += to_fen[colour](side[0])
        if not fen_castling:
            fen_castling = '-'
                
                
        fen_passant_target = self.board.en_passant_target if self.board.en_passant_target else '-'
        fen_halfmoves = f'{self.halfmove_clock}'
        fen_fullmoves = f'{self.fullmoves}'
        fen_fields = [fen_board, fen_turn, fen_castling, fen_passant_target, fen_halfmoves, fen_fullmoves]
        
        fen = ' '.join(fen_fields)
        return fen
            
    def generate_pgn(self, start_move: int | None = None, end_move: int | None = None) -> str:
        pgn_string = ''

        start_num = self.get_start_move()
        history_start = None
        if start_move:
            history_start = start_move - start_num 
        history_end = None
        if end_move:
            history_end = end_move - start_num
            
        fullmove_num = start_num
        for colour, move in self.move_history[history_start:history_end]: 
            if 'black' in self.move_history[0] and fullmove_num == start_num:
                pgn_string += f'{fullmove_num}... '

            if colour == 'white':
                pgn_string += f'{fullmove_num}. '
            else: 
                fullmove_num += 1 
            
            pgn_string += f'{move} '
                 
        return pgn_string
    
    def load_fen(self, fen: str, is_start=True):
        if not fen:
            return self
        
        fen_fields = fen.split() 
        board, turn, castling, en_passant_target, half_moves, full_moves = fen_fields
        if not re.match(r'^([rnbqkpRNBQKP1-8]{1,8}(/|\Z)){8}$', board):
            raise ValueError('FEN is not valid!', fen)

        self.board.fen_to_board(board)
            
        self.turn = 'white' if turn == 'w' else 'black'
        
        to_fen = {'white': lambda x: x.upper(), 'black': lambda x: x.lower()}
        if castling != '-':
            for key in self.can_castle.keys():
                colour, side = key.split('_')
                self.can_castle[f'{colour}_{side}'] = to_fen[colour](side[0]) in castling
                king_pos = self.board.king_positions[colour]
                self.in_check[colour] = square_is_attacked(king_pos, (self.board, colour))
                
        if en_passant_target != '-':
            self.board.en_passant_target = en_passant_target
        self.halfmove_clock = int(half_moves)
        
        self.fullmoves = int(full_moves) if (full_moves and full_moves != '-') else 0
        
        if is_start:
            self.position_history[0] = fen
            self.position_count[fen[:-4]] = 1
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
            elif not re.match(SAN_PATTERN, token):
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
                self.move_history[-1][1].check_str = '#'
        return self  
    
    def play_move(self, move: Move):
        piece = self.board[move.origin]
        back_rank = 1 if piece.colour == 'white' else 8
        self.board.make_move(move)
        
        if piece.type == 'R' and move.origin in [f'a{back_rank}', f'h{back_rank}']:
            side = '_queenside' if move.origin[0] == 'a' else '_kingside'
            self.can_castle[f'{piece.colour}{side}'] == False
        if piece.type == 'K':
            self.can_castle[f'{piece.colour}_kingside'] = False
            self.can_castle[f'{piece.colour}_queenside'] = False
        
        # Update self data
        last_turn = self.turn
        self.turn = opposite(self.turn)
        if piece.type == 'K':
            self.board.king_positions[last_turn] = move.destination
            
        return self
      
    def go_to_move(self, dest_move: int , colour: str | None = None) -> tuple[GameState, GameState]:
        if dest_move < 0:
            dest_move += self.fullmoves
        if colour is None:
            colour = self.turn

        dest_ply = self.convert_to_ply(dest_move, colour)
        is_restart = dest_ply == 0
        
        if (dest_move < self.get_start_move() and not is_restart) or dest_move > self.fullmoves:
            raise ValueError(f'Cannot undo: move {dest_move} does not exist' )
        
        return self.go_to_ply(dest_ply)
        
    def go_to_ply(self, dest_ply: int) -> tuple[GameState, GameState]:
        snapshot = copy.deepcopy(self) # Snapshot is held for one full move for option to revert
        
        new_game = GameState(fen='')
        if dest_ply == 0:
            new_game.load_fen(self.position_history[0])
        else:
            new_game.load_from_history(self, dest_ply - 1)
        
        self = new_game
        return self, snapshot

    # Load to ply AFTER move is made (turn after this ply)
    def load_from_history(self, other: GameState, dest_ply: int):
        if dest_ply < 0 or dest_ply > len(other.move_history):
            raise ValueError(f'Cannot load history at ply {dest_ply}')
        elif dest_ply == 0:
            self.position_history[0] = other.position_history[0]
            return self
        
        for ply_num, pos in other.position_history.items():
            if ply_num > dest_ply:
                break
            self.position_history[ply_num] = pos
            only_pos = pos[:-4] # Remove halfmove and fullmove counts 
            if only_pos in self.position_count:
                self.position_count[only_pos] += 1
            else:
                self.position_count[only_pos] = 1

        if dest_ply in self.position_history:
            self.move_history = other.move_history[:dest_ply] 
            self.load_fen(self.position_history[dest_ply], False) # White's move at dest
        elif dest_ply - 1 in self.position_history:
            self.move_history = other.move_history[:dest_ply - 1] 
            self.load_fen(self.position_history[dest_ply - 1], False)
            self.process_player_move(other.move_history[dest_ply - 1][1]) # Move at dest
        else:
            raise IllegalState('Failed to load history')
        self.ply = len(self.move_history)
        self.board.perspective = other.board.perspective
        
        return self

    def process_player_move(self, player_move: str | Move):
        last_passant = self.board.en_passant_target
        move_info = ''

        if isinstance(player_move, Move): # Convert to str to validate
            player_move = str(player_move)
        move_info = parse_move(player_move, re.IGNORECASE)    
        validated = None
        
        # Validate move
        if isinstance(move_info, list): # Parsing ambiguity
            potential_moves = [] 
            conflicts = set()
            for move_dict in move_info:
                try:    
                    potential_move = mr.validate_move(move_dict, self.board, self.turn)
                except:
                    continue
                if isinstance(potential_move, Move):
                    potential_moves.append(potential_move)
                if isinstance(potential_move, set):
                    conflicts.update(potential_move)
            
            if len(potential_moves) == 1:
                validated = potential_moves[0]
            elif len(potential_moves) == 0 and conflicts:
                validated = conflicts
            else:
                raise AmbiguityError(f'Could not validate {player_move}', potential_moves)
        else: # Unambiguous
            validated = mr.validate_move(move_info, self.board, self.turn)
            
        if isinstance(validated, set): # Multiple possible moves
            potential_moves = validated.copy()
            for potential_move in potential_moves:
                if not self.is_legal_move(potential_move):
                    validated.remove(potential_move)
            
            if len(validated) > 1:
                raise AmbiguityError(f'{player_move} is ambiguous', validated) 
            elif len(validated) < 1: 
                raise IllegalMove(f'{player_move} is not a legal move')
            else:
                (validated,) = validated # Unpack value
        else:
            if not self.is_legal_move(validated):
                raise IllegalMove(f'{player_move} is not a legal move')
            
        last_turn = self.turn
        self.play_move(validated) # Turn and other self data is updated here
            
        # Update king position
        if validated.piece.type == 'K':
            self.board.king_positions[validated.piece.colour] = validated.destination
            
        if last_passant == self.board.en_passant_target: # Only flags if no en_passant performed
            self.board.en_passant_target = None
        if validated.is_capture or validated.piece.type == 'p':
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1
        
        # Update self history
        snapshot = self.generate_fen()
        self.move_history.append((last_turn, validated))
        self.ply += 1
        if last_turn == 'black':
            self.fullmoves += 1
        else: 
            self.position_history[self.ply] = snapshot # Updates on whites move ONLY

        # Remove halfmove and fullmove counts to store positional data only
        snapshot_position = snapshot[:-4]
        if snapshot_position not in self.position_count:
            self.position_count[snapshot_position] = 0
        self.position_count[snapshot_position] += 1
        
        # Update check and last move notation
        self.update_check()
        if any(self.in_check.values()):
            self.move_history[-1][1].check_str = '+'
                
        return self  
  
    def is_legal_move(self, move: Move) -> bool | list[Move]:
        board = self.board
        piece = self.board[move.origin]
        king_pos = ''

        if move.piece.type == 'K':
            king_pos = move.destination
        else:
            king_pos = self.board.king_positions[piece.colour]
            
        king_is_safe = square_remains_safe(king_pos, move, self, piece.colour)
        if not king_is_safe or is_friendly(move.destination, piece, board) or not piece == move.piece:
            return False
        
        if move.origin not in board or board[move.origin].colour != move.piece.colour:
            return False
        
        # Initial position
        init_file, init_rank = [*move.origin]
        init_rank = int(init_rank)
        init_findex = FILES.index(init_file)
        
        dest_file, dest_rank = [*move.destination]
        dest_rank = int(dest_rank)
        dest_findex = FILES.index(dest_file)
        match piece.type:
            case 'p': return mr.is_pawn_move(move.origin, move.destination, board, piece.colour)
            case 'N': return mr.is_knight_move(move.origin, move.destination)
            case 'B': return mr.is_bishop_move(move.origin, move.destination, board)
            case 'R': return mr.is_rook_move(move.origin, move.destination, board)
            case 'Q': return mr.is_bishop_move(move.origin, move.destination, board) or mr.is_rook_move(move.origin, move.destination, board)
            case 'K':        
                '''Castling'''
                if move.special == 'castling':
                    if can_castle_kingside(piece, self):
                        target = f'g{init_rank}'
                        if move.destination == target:
                            return True
                    if can_castle_queenside(piece, self):
                        target = f'c{init_rank}'
                        if move.destination == target:
                            return True
                else:
                    v_comps = [abs(init_findex - dest_findex), abs(init_rank - dest_rank)] # Vector components
                    is_single_step = max(v_comps) == 1 and sum(v_comps) > 0
                    is_safe = square_remains_safe(move.destination, move, self, move.piece.colour)
                    if is_single_step and is_safe:
                        return True
        return False

    def check_if_end(self):
        player = self.turn
        has_legal_moves = self.legal_moves(flag='any')
        position_snapshot = self.generate_fen()[:-4] # Parts of FEN string that determine threefold rep
        
        if self.in_check[player] and not has_legal_moves:
            self.is_end = True
            self.end_state = 'checkmate'
            self.winner = opposite(player)
        elif not has_legal_moves:
            self.is_end = True
            self.end_state = 'stalemate'
            self.winner = 'draw'
        elif position_snapshot in self.position_count and self.position_count[position_snapshot] == REP_LIMIT:
            self.is_end = True
            self.end_state = 'threefold repetition'
            self.winner = 'draw'
        elif self.halfmove_clock >= HALFMOVE_LIMIT:
            self.is_end = True
            self.end_state = '50 move rule'
            self.winner = 'draw'
           
        return self

    # Check if there is sufficient material for checkmate
    def sufficient_material(self):
        pass

    def legal_moves(self, flag=None):
        if flag not in ['any', None]:
            raise ValueError('Invalid flag for legal_moves()')
        
        legal_moves = []
        for square, piece in self.board.items():
            
            if piece.colour == self.turn:
                search_squares = mr.possible_destinations(piece, square, self.board)
                    
                # True if any moves exist
                if search_squares and flag == 'any':
                    for dest in search_squares:
                        move = Move(square, dest, piece)
                        if self.is_legal_move(move):
                            return True
                elif search_squares: # Collect all legal moves
                    for dest in search_squares:
                        move = Move(square, dest, piece)
                        if self.is_legal_move(move):
                            legal_moves.append(move)     
                            
        if flag == 'any':
            return False
        else:
            return legal_moves   
             
    def update_check(self):
        for colour, king_pos in self.board.king_positions.items():
            self.in_check[colour] = square_is_attacked(king_pos, (self.board, colour))
        return self

    def get_start_move(self):
        initial_state = self.position_history[0] # Initial FEN
        move_num = initial_state.split()[-1] # Split FEN string into fields, last field is fullmove num
        return int(move_num)
    
    def convert_to_ply(self, move_num: int, colour: str):
        if move_num == 0:
            return 0
        first_move_num = self.get_start_move()
        if not is_colour(colour):
            raise ValueError('Invalid colour provided')
        elif move_num < first_move_num or move_num > self.fullmoves:
            raise ValueError('Invalid move num')

        # Find dest ply
        first_colour = self.move_history[0][0] # Colour of first move
        moves_completed = move_num - self.get_start_move()
        if colour == first_colour: 
            '''2 * fullmoves in between and then black plays'''
            return 2 * (moves_completed) + 1 
        else:
            '''Black has even plies''' 
            return 2 * (moves_completed + 1)

def create_game(input=None) -> GameState:
    fen, pgn = parse_initial_state(input)
    new_game = GameState(fen, pgn)
    
    return new_game

def area_is_safe(squares, game : GameState):
    return not any(square_is_attacked(square, game) for square in squares)

def area_is_empty(squares, game: GameState):
    return not any(square in game.board for square in squares)

def square_is_attacked(square : str, game : GameState | tuple[Board, str]) -> bool: # Do not pass attacking colour
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
    pawn_attacks = mr.find_pawn_attacks(file, rank, colour, False)
    if mr.find_attacker(pawn_attacks, ['p', 'B', 'Q', 'K'], board, opp_colour):
        return True
    
    # Check for knights
    knight_attacks = mr.find_knight_attacks(file, rank)
    if mr.find_attacker(knight_attacks, ['N'], board, opp_colour):
        return True
    
    # Check for bishops and queens
    diagonal_attacks = mr.find_bishop_attacks(file, rank, board)
    if mr.find_attacker(diagonal_attacks, ['B', 'Q'], board, opp_colour):
        return True
    
    # Check for rooks and queens
    orthog_attacks = mr.find_rook_attacks(file, rank, board)
    if mr.find_attacker(orthog_attacks, ['R', 'Q'], board, opp_colour):
        return True
    
    # Check for king 
    king_attacks = mr.find_king_attacks(file, rank)
    if mr.find_attacker(king_attacks, ['K'], board, opp_colour):
        return True
    
    return False

def square_remains_safe(square: str, move: Move, game: GameState, colour: str):
    return not square_is_attacked(square, (simulate_move(move, game).board, colour))

def simulate_move(move : Move, game : GameState):
    clone_game = copy.deepcopy(game)
    clone_game.play_move(move)
    return clone_game

def can_castle_kingside(piece: Piece, game):
    r = '1' if piece.colour == 'white' else '8'
    return game.can_castle[f'{piece.colour}_kingside'] and area_is_empty([f'f{r}', f'g{r}'], game) and area_is_safe([f'e{r}', f'f{r}', f'g{r}'], game)

def can_castle_queenside(piece: Piece, game):
    r = '1' if piece.colour == 'white' else '8'
    return game.can_castle[f'{piece.colour}_queenside'] and area_is_empty([f'd{r}', f'c{r}'], game) and area_is_safe([f'e{r}', f'd{r}', f'c{r}'], game)