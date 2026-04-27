from .board import FILES
def is_pawn_move(origin, destination, board, colour):
    init_file, init_rank = [*origin]
    dest_file, dest_rank = [*destination]
    init_findex = FILES.index(init_file)
    dest_findex = FILES.index(dest_file)
    init_rank, dest_rank = int(init_rank), int(dest_rank)
    
    rank_steps = dest_rank - init_rank
    file_steps = dest_findex - init_findex
    factor = 1 if colour == 'white' else -1
    
    if rank_steps == 2 * factor: # Double step
        path_is_clear = all(f'{init_file}{init_rank + i * factor}' not in board for i in [1, 2])
        double_is_valid = init_rank == (2 if colour == 'white' else 7)
        
        return path_is_clear and double_is_valid
    elif rank_steps == factor:
        return destination not in board

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