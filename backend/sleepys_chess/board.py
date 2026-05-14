# Module to handle rendering of the board
from .moves import Move
from .pieces import Piece, PIECE_TYPES
from .utils import opposite, COLOURS, is_colour

import re
FILES = 'abcdefgh'
RANKS = '12345678'

class Board:
    def __init__(self):
        self.squares: dict[str, Piece] = {}
        self.king_positions: dict[str: str] = {'white': 'e1', 'black': 'e8'}
        self.en_passant_target: str | None = None
        self.perspective: str | None = None
       
    def __repr__(self):
        return vars(self.squares) 
    
    def __str__(self):
        return self.render(self.perspective)
    
    def render(self, pov: str | None ='white'): 
        # Sum of material value on each side of initial position
        default_material_value = 39 
        material_captured = {
                'black': '♛♜♜♝♝♞♞♟♟♟♟♟♟♟♟',
                'white': '♕♖♖♗♗♘♘♙♙♙♙♙♙♙♙' }
        material_value = {
                'p': 1,
                'N': 3,
                'B': 3,
                'R': 5,
                'Q': 9 }
        material_sums = {
                'black': default_material_value,
                'white': default_material_value
        }
        if pov is None: 
            pov = 'white'
            
        if not is_colour(pov):
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
        
        full_board = [material[opposite(pov)]] + board_list + [material[pov]]
        return '\n'.join(full_board)
    
    def flip(self, colour = None):
        if self.perspective:
            self.perspective = opposite(self.perspective)
        elif colour:
            self.perspective = opposite(colour)
        return self
        
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
    
    def make_move(self, move: Move):
        piece = self[move.origin]
        back_rank = 1 if piece.colour == 'white' else 8

        if move.special == 'en passant':
            target_file, target_rank = [*self.en_passant_target]
            target_rank = int(target_rank)
            target_rank = target_rank + 1 if piece.colour == 'black' else target_rank - 1 # Target pawn one sq ahead of e.p. target
            target = f'{target_file}{target_rank}'
            
            del self[target] # Delete target pawn
        
        elif move.special == 'castling':
            dest_file = move.destination[0]
            rook_origin = f'a{back_rank}' if dest_file == 'c' else f'h{back_rank}'
            rook_destination = f'd{back_rank}' if dest_file == 'c' else f'f{back_rank}'
            rook = self[rook_origin]
            
            # Move the rook
            del self[rook_origin]
            self[rook_destination] = rook      
        elif move.special == 'promotion':
            piece = Piece(type=move.promote, colour=piece.colour)
        
        # Update dest and origin squares  
        self[move.destination] = piece
        del self[move.origin]

        return self
        
    def fen_to_board(self, fen_board):
        # Convert board
        rank = 8
        findex = 0
        for char in fen_board:
            if char == ' ':
                break
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
                self.king_positions['black'] = pos
            elif char == 'K':
                self.king_positions['white'] = pos
                
            if piece.type is None or piece.colour is None:
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
          

