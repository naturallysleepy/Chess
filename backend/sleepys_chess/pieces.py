

PIECE_TYPES = ['p', 'N', 'B', 'R', 'Q', 'K']
CHESS_PIECES = {
    'white': {'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'p': '♙'},
    'black': {'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'p': '♟'}
}
PIECE_NAMES = {'K': 'king', 'Q': 'queen', 'R': 'rook', 'B': 'bishop', 'N': 'knight', 'p': 'pawn'}
COLOURS = ['black', 'white'] 

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

def is_friendly(target : str, piece : Piece, board):
    return target in board and board[target].colour == piece.colour

