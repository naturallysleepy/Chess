# Module to handle rendering of the board
from .pieces import Piece, COLOURS, PIECE_TYPES
from .utils import opposite

import itertools
import re
FILES = 'abcdefgh'
RANKS = '12345678'

class Board:
    def __init__(self):
        self.squares: dict[str, Piece] = {}
        self.white_king_pos: str = 'e1'
        self.black_king_pos: str = 'e8'
        self.en_passant_target: str = None
       
    def __repr__(self):
        return vars(self.squares) 
    
    def __str__(self):
        return self.render('white')
    
    def render(self, pov='white'):
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
            
        if pov not in COLOURS:
            raise ValueError('Invalid board perspective')
        
        # Draw board
        board_list = []
        for r in range(len(RANKS) + 1):
            rank = len(RANKS) - r if pov == 'white' else r
            rank_list = []
            
            rank_list.append(f'{rank}' if rank > 0 else ' ')
            for i, file in enumerate(FILES):
                if rank == 0:
                    rank_list.append(file)
                else:
                    position = f'{file}{rank}'
                    
                    if position in self.squares:
                        piece = self[position]
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
                        if (i % 2 == 1) == (rank % 2 == 1):
                            rank_list.append('□')
                        else:
                            rank_list.append('■')
            board_list.append(' '.join(rank_list))
                
        
        # Calculate material advantage
        material = {}
        for colour in COLOURS:
            material[colour] = material_captured[opposite(colour)] 
            advantage = material_sums[colour] - material_sums[opposite(colour)]
            if advantage > 0:
                material[colour] += f' +{advantage}'
        
        full_board = [material[pov]] + board_list + [material[opposite(pov)]]
        return '\n'.join(full_board)
        
    def __getitem__(self, pos: str):
        if pos in self.squares:
            return self.squares[pos]
        else:
            return None
    
    def __setitem__(self, pos, piece: Piece):
        self.squares[pos] = piece
    
    def __delitem__(self, pos):
        del self.squares[pos]
        
    def items(self):
        return self.squares.items() 
    
    def __contains__(self, square):
        return square in self.squares  
        
    def fen_to_board(self, fen_board):
        # Convert board
        rank = 8
        findex = 0
        for char in fen_board:
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
                self[pos] = piece
                
            findex += 1 
        return self
    
    def board_to_fen(self): 
        board_list = []
        to_fen = {'white': lambda x: x.upper(), 'black': lambda x: x.lower()}
          
        for rank in reversed(RANKS):
            this_rank = ''
            space_counter = 0
            for file in FILES:
                pos = f'{file}{rank}'
                if pos not in self.squares:
                    space_counter += 1
                    if file == 'h' and space_counter != 0:
                        this_rank += f'{space_counter}'
                    continue
                
                piece = self[pos]
                if space_counter != 0:
                    this_rank += f'{space_counter}'
                this_rank += to_fen[piece.colour](piece.type)
                space_counter = 0
            board_list.append(this_rank)
        fen_board = '/'.join(board_list)
        
        return fen_board
          
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

