from .moves import Move 
from .moverules import is_pawn_move, is_knight_move, is_bishop_move, is_rook_move
from .parsing import parse_move, FEN_INITIAL

from .board import Board, FILES
from .pieces import Piece, PIECE_NAMES, COLOURS, is_friendly
from .board import find_pawn_attacks, find_knight_attacks, find_bishop_attacks
from .board import find_rook_attacks, find_king_attacks, find_attacker, possible_destinations

from .parsing import parse_initial_state, SAN_PATTERN
from .utils import opposite, strip_brackets

# Built ins
import re, copy

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
        self.end_state: str = None
        self.winner: str = None
        self.move_history: list[dict[str, Move]] = []
        self.position_history: dict[int, str] = {}
        self.position_count: dict[str, int] = {}
        self.halfmove_clock: int = 0
        self.fullmoves: int = 0  
        
        if fen:
            self.load_fen(fen) 
        else:
            self.load_fen(FEN_INITIAL)  
            
        if pgn:
            self.load_pgn(pgn)
        
    def __repr__(self):
        return vars(self)
    
    def __str__(self):
        string_list = []
        board_string = self.board.render(self.turn)  
        
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
            
        return '\n'.join(string_list)
                
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
                king_pos = self.board.black_king_pos if colour == 'black' else self.board.white_king_pos
                self.in_check[colour] = square_is_attacked(king_pos, (self.board, colour))
                
        if en_passant_target != '-':
            self.board.en_passant_target = en_passant_target
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
                self.move_history[-1][self.winner].check_str = '#'
        return self  
    
    def make_move(self, move: Move):
        piece = self.board[move.origin]

        back_rank = 1 if piece.colour == 'white' else 8
        if move.special == 'en passant':
            target_file, target_rank = [*self.board.en_passant_target]
            target_rank = int(target_rank)
            target_rank = target_rank + 1 if self.turn == 'black' else target_rank - 1
            target = f'{target_file}{target_rank}'
            
            del self.board[target] # Delete target pawn
        
        elif move.special == 'castling':
            dest_file = move.destination[0]
            rook_origin = f'a{back_rank}' if dest_file == 'c' else f'h{back_rank}'
            rook_destination = f'd{back_rank}' if dest_file == 'c' else f'f{back_rank}'
            rook = self.board[rook_origin]
            
            # Move the rook
            del self.board[rook_origin]
            self.board[rook_destination] = rook      
        elif move.special == 'promotion':
            piece = Piece(type=move.promote, colour=piece.colour)
        
        # Update dest and origin squares  
        self.board[move.destination] = piece
        del self.board[move.origin]
        
        if piece.type == 'R' and move.origin in [f'a{back_rank}', f'h{back_rank}']:
            side = '_queenside' if move.origin[0] == 'a' else '_kingside'
            self.can_castle[f'{piece.colour}{side}'] == False
        if piece.type == 'K':
            self.can_castle[f'{piece.colour}_kingside'] = False
            self.can_castle[f'{piece.colour}_queenside'] = False
        
        # Update self data
        last_turn = self.turn
        self.turn = opposite(self.turn)
        if piece.type == 'K' and last_turn == 'white':
            self.board.white_king_pos = move.destination
        elif piece.type == 'K' and last_turn == 'black':
            self.board.black_king_pos = move.destination
            
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
        last_passant = self.board.en_passant_target
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
            self.make_move(validated)
                
            # Update king position
            if validated.piece == Piece('K', 'black'):
                self.board.black_king_pos = validated.destination
            elif validated.piece == Piece('K', 'white'):
                self.board.white_king_pos = validated.destination
                
            if last_passant == self.board.en_passant_target: # Only flags if no en_passant performed
                self.board.en_passant_target = None
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
                
            # Remove halfmove and fullmove counts to store positional data only
            snapshot_position = snapshot[:-4]
            if snapshot_position not in self.position_count:
                self.position_count[snapshot_position] = 0
            self.position_count[snapshot_position] += 1
            
            # Update check and last move notation
            self.update_check()
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
            
            if piece.colour == self.turn:
                search_squares = possible_destinations(piece, square, self.board)
                    
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
             
    def update_check(self):
        for colour in COLOURS:
                king_pos = self.board.black_king_pos if colour == 'black' else self.board.white_king_pos
                self.in_check[colour] = square_is_attacked(king_pos, (self.board, colour))
        return self
 
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

def validate_move(move_data : dict, game : GameState, player : str):
    board = game.board
    move_notation, move_type, move_details = move_data.values()
    
    destination = None
    is_capture = False
    if 'destination' in move_details:
        destination = move_details['destination']
        dest_file, dest_rank = [*destination]
        dest_rank = int(dest_rank)
        is_capture = (destination == game.board.en_passant_target and move_type == 'pawn') or destination in board

    
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
                    if pos not in board or board[pos] != Piece('p', player):
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
            pawn = game.board[pawn_origin]
            is_double = (abs(origin_rank - dest_rank) == 2)
            is_en_passant = (destination == game.board.en_passant_target)
            
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
            pawn = game.board[pawn_origin]
            
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
            
            # Find origin square by tracing backwards
            search_squares = possible_destinations(piece, destination, game.board, attacks_only=True)
                
            origin = set()
            for square in search_squares:
                if square in board and board[square] == piece:
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
            king = game.board[origin]
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
    piece = game.board[move.origin]
    king_pos = ''
    if move.piece.type == 'K':
        king_pos = move.destination
    else:
        king_pos = game.board.white_king_pos if piece.colour == 'white' else game.board.black_king_pos
        
    king_is_safe = square_remains_safe(king_pos, move, game, piece.colour)
    if not king_is_safe or is_friendly(move.destination, piece, board) or not piece == move.piece:
        return False
    opp_colour = opposite(move.piece.colour)
    
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
        case 'p':
            rank_steps = dest_rank - init_rank
            file_steps = dest_findex - init_findex
            factor = 1 if piece.colour == 'white' else -1
            
            if abs(file_steps) > 1:
                return False
            elif abs(file_steps) == 1 and rank_steps == factor: # Pawn capture 
                if move.destination in board:
                    return board[move.destination].colour == opp_colour
                else:
                    return move.destination == game.board.en_passant_target
            else:
                return is_pawn_move(move.origin, move.destination, board, piece.colour)
        case 'N': return is_knight_move(move.origin, move.destination)
        case 'B': return is_bishop_move(move.origin, move.destination, board)
        case 'R': return is_rook_move(move.origin, move.destination, board)
        case 'Q': return is_bishop_move(move.origin, move.destination, board) or is_rook_move(move.origin, move.destination, board)
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
    clone_game.make_move(move)
    return clone_game

def can_castle_kingside(piece: Piece, game):
    r = '1' if piece.colour == 'white' else '8'
    return game.can_castle[f'{piece.colour}_kingside'] and area_is_empty([f'f{r}', f'g{r}'], game) and area_is_safe([f'e{r}', f'f{r}', f'g{r}'], game)

def can_castle_queenside(piece: Piece, game):
    r = '1' if piece.colour == 'white' else '8'
    return game.can_castle[f'{piece.colour}_queenside'] and area_is_empty([f'd{r}', f'c{r}'], game) and area_is_safe([f'e{r}', f'd{r}', f'c{r}'], game)