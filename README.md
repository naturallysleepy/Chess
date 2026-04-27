# Command-Line Chess Game (Python)

This is a terminal-based chess game written in python

## Features 
- Full chess rules and move validation
- Runs in command-line interface
- Turn based gameplay
- Board rendering using unicode symbols
- FEN and PGN parsing (load board positions)
- FEN and PGN generation (export games and positions)

## How to Run
1. Make sure python is installed
2. In the terminal, run:
   python backend/main.py

## How to Use 
1. Run the program
2. When prompted, you can load a game by pasting a PGN string or FEN string into the terminal. For the default gamestate, you may ignore this prompt and press enter.
3. Once the game is loaded, the board should appear in the terminal. Play your turn by inputting a move in standard chess notation and press enter. (example: Nxf3+)
4. You may also run a command during the play phase of the program.
   Available commands include:
   - /help: lists all available commands
   - /exit: leave the program
   - /resign: resign the current game
   - /undo: undo last move
   - /revert: revert last undo
   - /restart: restart the game to its initial state

## Known Issues
- FEN and PGN parsing is fully supported for string input. File based parsing is partially implemented and requires further refinement

## Future Work
- Add graphical user interface 
- Expand command handling
- Refine game flow
- Implement chess bot 

## Notes
This project was built to explore programming logic, state management and problem solving. 
