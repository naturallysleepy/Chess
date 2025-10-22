import re

SAN_PATTERN = r'(?:[KQRBN]?[a-h1-8]?x?[a-h][1-8](?:=[KQRBN])?|O-O(?:-O)?)[+#]?' # SAN: Standard Algebraic Notation
PGN_PATTERN = rf'(\d+\.?\s?{SAN_PATTERN}\s)((?:\d+\.\.\.)?{SAN_PATTERN}\s)'
FEN_PATTERN = r'(?:[rnbqkpRNBQKP1-8]{1,8}/){7}[rnbqkpRNBQKP1-8]{1,8} [wb] (?:[KQkq]{1, 4}|-) (?:[a-h][1-8]|-) \d+ \d+'
CMD_PATTERN =  r'(/.*|resign|q(?:uit)?|exit|[?]|help)'
FEN_INITIAL = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 0'

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

def parse_initial_state(input: str):
    if not input:
        return None, None
    fen = ''
    pgn = ''
    content = ''
    if any(extension == input[-4:] for extension in ['.pgn', '.fen', '.txt', '.csv']):
        with open(input, "r") as file:
            content = file.read()
        if '.pgn' in input:
            pgn = content
        elif '.fen' in input:
            fen = content
    else:
        content = input     
       
    # Groups each match into a tuple (white turn, black turn) 
    move_tuples = re.findall(PGN_PATTERN, content)
    moves = ''
    for turn in move_tuples:
        moves += ''.join(turn)
          
    pgn = moves
    fen = re.findall(FEN_PATTERN, content) 
    # If there's at least one fen, match only the first (add selection later)
    if fen:
        fen: str = fen[0]
    else: 
        fen = FEN_INITIAL  
        
    return fen, pgn  
    
def move_or_command(player_input):
    if re.search(CMD_PATTERN, player_input, re.I):
        return 'cmd'
    if re.search(SAN_PATTERN, player_input, re.I):
        return 'move'
    raise ValueError('Input is not a move or supported command')
                