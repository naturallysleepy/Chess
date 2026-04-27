import os

def opposite(colour : str):
    if colour not in ['white', 'black']:
        raise ValueError('Invalid colour')
    return 'white' if colour == 'black' else 'black'

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

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')