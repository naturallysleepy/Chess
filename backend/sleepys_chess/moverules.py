from .board import Board, FILES, RANKS
from .pieces import Piece, PIECE_NAMES
from .moves import Move
from .utils import opposite

import itertools

class InvalidMove(Exception):
    pass 

def validate_move(move_data : dict, board: Board, player : str) -> Move | set[Move]:
    move_notation, move_type, move_details = move_data.values()
    
    destination = None
    is_capture = False
    if 'destination' in move_details:
        destination = move_details['destination']
        dest_file, dest_rank = [*destination]
        dest_rank = int(dest_rank)
        is_capture = (destination == board.en_passant_target and move_type == 'pawn') or destination in board

    
    # Capture exists, not in syntax
    if is_capture and 'capture' in move_details and move_details['capture'] is None: 
        raise InvalidMove('Invalid syntax: Capture not specified')
    
    # Capture does not exist, exists in syntax
    elif not is_capture and 'capture' in move_details and move_details['capture'] is not None:
        raise InvalidMove('Invalid syntax: This move is not a capture')
        
        
    match move_type:
        case 'pawn':
            '''Find pawn position'''
            sign = 1 if player == 'white' else -1
            
            # Files only change when pawn captures
            origin_file = move_details['origin'] if move_details['capture'] else dest_file
            pawn_origin = None

            for i in (sign, 2 * sign): 
                potential_rank = dest_rank - i # Look behind pawn destination
                potential_origin = f'{origin_file}{potential_rank}'
                potential_pawn = board[potential_origin]

                if potential_pawn == Piece('p', player) and is_pawn_move(potential_origin, destination, board, player):
                    pawn_origin = potential_origin
                    break
            else:
                raise InvalidMove(f'No {player} pawn that can move to {destination}.')
                    
            # Found coordinates
            origin_rank = int(pawn_origin[-1])
            pawn = board[pawn_origin]
            is_double = (abs(origin_rank - dest_rank) == 2)
            is_en_passant = (destination == board.en_passant_target)
            
            move = Move(pawn_origin, destination, pawn)
            move.is_capture = is_en_passant or is_capture
            if is_en_passant:
                move.special = 'en passant'
            
            if is_double:
                board.en_passant_target = f'{dest_file}{dest_rank - sign}'
            return move
            
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
            if pawn == Piece('p', player) and is_pawn_move(pawn_origin, destination, board, player):
                return move
            else:
                raise InvalidMove(f'{move_notation} is not a valid move.')
            
        case 'piece':
            piece_type = move_details['piece'] 
            piece_name = PIECE_NAMES[piece_type]
            
            origin_hint = move_details['origin'] # Sometimes None
            piece = Piece(type = piece_type, colour = player)
            
            # Find origin square by tracing backwards
            search_squares = possible_destinations(piece, destination, board, attacks_only=True)
                
            origin = set()
            for square in search_squares:
                if square in board and board[square] == piece:
                    origin.add(square)
            if not origin:
                raise InvalidMove(f'There is no {player} {piece_name} that can travel to {destination}')
                
            conflict = len(origin) > 1
            conflict_set = set()
            if conflict:
                if not origin_hint: 
                    possible_moves = set()
                    for square in origin:
                        move_candidate = Move(square, destination, piece)
                        move_candidate.is_capture = is_capture
                        possible_moves.add(move_candidate)
                    return possible_moves
                
                origin_resolved = set()
                conflict_set = origin.copy() 

                for square in conflict_set:
                    if origin_hint in square:
                        origin_resolved.add(square)

                if not origin_resolved:
                    raise InvalidMove(f"{move_notation} is not a valid move.")
    
                # Disambiguation present, but not sufficient 
                elif len(origin_resolved) > 1:
                    possible_moves = set()
                    for square in origin_resolved:
                        move_candidate = Move(square, destination, piece)
                        move_candidate.is_capture = is_capture
                    
                        if conflict_set != origin_resolved: # Any elements were removed from conflict set
                            move.disambiguation = origin_hint 

                        possible_moves.add(move_candidate)
                    return possible_moves # Not ambiguity error because move legality may remove candidates
                else: 
                    (origin,) = origin_resolved 

            else:
                (origin,) = origin # Unpack set
            
            move = Move(origin, destination, piece)

            if not conflict:
                move.disambiguation = None # Prevent unnecessary disambiguation

            elif len(origin_hint) == 1: # 1 disambiguation character
                move.disambiguation = origin_hint 
                
            else: # Only case of length 2 remains, else handled in parsing phase
                hint_file, hint_rank = [*origin_hint]

                shared_file = 0
                shared_rank = 0
                for square in conflict_set:
                    file, rank = [*square]

                    if file == hint_file:
                        shared_file += 1
                    if rank == hint_rank:
                        shared_rank += 1

                if shared_file == 1:
                    # Only file disambiguation needed
                    move.disambiguation = hint_file
                elif shared_rank == 1:
                    # Only rank disambiguation needed
                    move.disambiguation = hint_rank
                else:
                    # Both file and rank disambiguation is necessary
                    move.disambiguation = origin_hint 
    
            move.is_capture = is_capture
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
            if king == Piece(type='K', colour=player):
                return move
            else:
                raise InvalidMove(f'{move_notation} is not a valid move.')
    raise InvalidMove(f'{move_notation} is not a valid move.')

def is_pawn_move(origin, destination, board, colour) -> bool:
    init_file, init_rank = [*origin]
    dest_file, dest_rank = [*destination]
    init_findex = FILES.index(init_file)
    dest_findex = FILES.index(dest_file)
    init_rank, dest_rank = int(init_rank), int(dest_rank)
    
    rank_steps = dest_rank - init_rank
    file_steps = dest_findex - init_findex
    factor = 1 if colour == 'white' else -1

    if abs(file_steps) > 1:
        return False
    elif abs(file_steps) == 1 and rank_steps == factor: # Pawn capture 
        if destination in board:
            return board[destination].colour == opposite(colour)
        else:
            return destination == board.en_passant_target
    elif abs(file_steps) == 0 and rank_steps == 2 * factor: # Double step
        path_is_clear = all(f'{init_file}{init_rank + i * factor}' not in board for i in [1, 2])
        double_is_valid = init_rank == (2 if colour == 'white' else 7)
        
        return path_is_clear and double_is_valid
    elif abs(file_steps) == 0 and rank_steps == factor: # Single step
        return destination not in board
    else: 
        return False

def is_knight_move(origin, destination):
    init_file, init_rank = [*origin]
    dest_file, dest_rank = [*destination]
    init_findex = FILES.index(init_file)
    dest_findex = FILES.index(dest_file)
    init_rank, dest_rank = int(init_rank), int(dest_rank)
    
    v_comps = {abs(init_findex - dest_findex), abs(init_rank - dest_rank)} # Vector components
    return v_comps == {1, 2}
    
def is_bishop_move(origin, destination, board):
    init_file, init_rank = [*origin]
    dest_file, dest_rank = [*destination]
    init_findex = FILES.index(init_file)
    dest_findex = FILES.index(dest_file)
    init_rank, dest_rank = int(init_rank), int(dest_rank)
    
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
        if trace_dest in board:
            return False
    return True

def is_rook_move(origin, destination, board):
    init_file, init_rank = [*origin]
    dest_file, dest_rank = [*destination]
    init_findex = FILES.index(init_file)
    dest_findex = FILES.index(dest_file)
    init_rank, dest_rank = int(init_rank), int(dest_rank)
    
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
        if trace_dest in board:
            return False
    return True

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

def find_bishop_attacks(file, rank, board : Board):
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
            if target in board:
                # Blocking
                break
            offset += 1   
    return targets

def find_rook_attacks(file, rank, board : Board):
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
            if target in board:
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
                       
def find_attacker(attacks : list, types : list, board: Board, opponent : str) -> bool:
    if not attacks:
        return False
    
    for attack in attacks:
        if attack not in board:
            continue
        attacker = board[attack]
        if attacker.colour == opponent and attacker.type in types:
            return True
    return False

def possible_destinations(piece: Piece, square: str, board: Board, colour=None, attacks_only=False):
    file, rank = [*square]
    rank = int(rank)
    if not colour:
        colour = piece.colour
    
    match piece.type:
        case 'p': 
            search_squares = find_pawn_attacks(file, rank, piece.colour)
            if not attacks_only:
                sign = 1 if colour == 'white' else -1
                search_squares.append(f'{file}{rank + sign}')
                if rank == (7 if colour == 'black' else 2):
                    search_squares.append(f'{file}{rank + 2 * sign}')
        case 'N': search_squares = find_knight_attacks(file, rank)
        case 'B': search_squares = find_bishop_attacks(file, rank, board)
        case 'R': search_squares = find_rook_attacks(file, rank, board)
        case 'Q': search_squares = find_bishop_attacks(file, rank, board) + find_rook_attacks(file, rank, board)
        case 'K': 
            search_squares = find_king_attacks(file, rank)
            if square == ('e1' if colour == 'white' else 'e8') and not attacks_only:
                search_squares += [f'g{rank}', f'c{rank}']
                
    return search_squares

def square_is_attacked(square : str, board: Board, colour: str) -> bool: # Do not pass attacking colour
    opp_colour = opposite(colour)
    file, rank= [*square]
    
    # Check for pawns
    pawn_attacks = find_pawn_attacks(file, rank, colour, False)
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