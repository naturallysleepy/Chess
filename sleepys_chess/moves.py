from .pieces import Piece

class Move:
    def __init__(self, origin, destination, piece):
        self.origin: str = origin
        self.destination: str = destination
        self.piece: Piece = piece
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

