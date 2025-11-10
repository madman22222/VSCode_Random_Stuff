"""Unit tests for GameController with mocked dependencies."""

import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import chess library before local modules to avoid conflicts
import chess
import chess.pgn

from game_controller import GameController, SimpleAI


class TestSimpleAI(unittest.TestCase):
    """Test SimpleAI move selection and scoring."""

    def test_ai_initialization(self):
        """Test SimpleAI initializes with correct depth."""
        ai = SimpleAI(depth=2)
        self.assertEqual(ai.depth, 2)

    def test_ai_chooses_legal_move(self):
        """Test that AI chooses a legal move."""
        board = chess.Board()
        ai = SimpleAI(depth=1)
        move = ai.choose_move(board)
        self.assertIsNotNone(move)
        self.assertIn(move, list(board.legal_moves))

    def test_move_score_promotion(self):
        """Test that AI gives high score to promotion moves."""
        ai = SimpleAI(depth=1)
        board = chess.Board("8/P7/8/8/8/8/8/8 w - - 0 1")  # white pawn about to promote
        moves = list(board.legal_moves)
        queen_promo = None
        for m in moves:
            if m.promotion == chess.QUEEN:
                queen_promo = m
                break
        if queen_promo is None:
            self.skipTest("No queen promotion move found")
        score = ai._move_score(board, queen_promo)
        self.assertGreater(score, 0)

    def test_move_score_capture(self):
        """Test that AI gives bonus to capture moves."""
        ai = SimpleAI(depth=1)
        board = chess.Board("8/8/8/4p3/3P4/8/8/8 w - - 0 1")
        capture_move = chess.Move.from_uci("d4e5")
        score = ai._move_score(board, capture_move)
        self.assertGreater(score, 0)


class TestGameControllerMocked(unittest.TestCase):
    """Test GameController with fully mocked tkinter dependencies."""

    def setUp(self):
        """Set up mocks for tkinter widgets."""
        # Mock tkinter components
        self.mock_root = MagicMock()
        self.mock_root.title = MagicMock()
        self.mock_root.resizable = MagicMock()
        
        # Patch tkinter module
        self.patcher_tk = patch('game_controller.tk')
        self.mock_tk = self.patcher_tk.start()
        
        # Mock tk widgets
        self.mock_tk.Frame = MagicMock(return_value=MagicMock())
        self.mock_tk.Label = MagicMock(return_value=MagicMock())
        self.mock_tk.Button = MagicMock(return_value=MagicMock())
        self.mock_tk.Listbox = MagicMock(return_value=MagicMock())
        self.mock_tk.Scrollbar = MagicMock(return_value=MagicMock())
        self.mock_tk.messagebox = MagicMock()
        self.mock_tk.filedialog = MagicMock()
        self.mock_tk.END = 'end'
        self.mock_tk.SINGLE = 'single'
        self.mock_tk.VERTICAL = 'vertical'
        self.mock_tk.LEFT = 'left'
        self.mock_tk.RIGHT = 'right'
        self.mock_tk.BOTH = 'both'
        self.mock_tk.Y = 'y'
        
        # Mock BoardView
        self.patcher_boardview = patch('game_controller.BoardView')
        self.mock_boardview_class = self.patcher_boardview.start()
        self.mock_boardview = MagicMock()
        self.mock_boardview_class.return_value = self.mock_boardview
        
        # Mock EngineManager
        self.patcher_engine = patch('game_controller.EngineManager')
        self.mock_engine_class = self.patcher_engine.start()
        self.mock_engine = MagicMock()
        self.mock_engine_class.return_value = self.mock_engine
        
        # Mock image loading
        self.patcher_image = patch('game_controller.Image')
        self.mock_image = self.patcher_image.start()
        
        self.patcher_imagetk = patch('game_controller.ImageTk')
        self.mock_imagetk = self.patcher_imagetk.start()

    def tearDown(self):
        """Stop all patchers."""
        self.patcher_tk.stop()
        self.patcher_boardview.stop()
        self.patcher_engine.stop()
        self.patcher_image.stop()
        self.patcher_imagetk.stop()

    def test_initialization(self):
        """Test GameController initializes with correct initial state."""
        controller = GameController(self.mock_root)
        self.assertIsInstance(controller.board, chess.Board)
        self.assertIsNone(controller.selected)
        self.assertFalse(controller.engine_enabled)

    def test_board_reset_via_new_game(self):
        """Test that board can be reset by creating new Board instance."""
        controller = GameController(self.mock_root)
        # Make a move
        move = chess.Move.from_uci("e2e4")
        controller.board.push(move)
        self.assertEqual(len(controller.board.move_stack), 1)
        
        # Reset by replacing board
        controller.board = chess.Board()
        self.assertEqual(len(controller.board.move_stack), 0)
        self.assertTrue(controller.board.turn == chess.WHITE)

    def test_on_click_select_piece(self):
        """Test clicking on own piece selects it."""
        controller = GameController(self.mock_root)
        
        # Click on white pawn at e2 (square 12)
        controller.on_click(chess.E2)
        self.assertIsNotNone(controller.selected)
        self.assertEqual(controller.selected, chess.E2)

    def test_on_click_make_move(self):
        """Test clicking destination after selecting piece makes move."""
        controller = GameController(self.mock_root)
        
        # Select e2 pawn
        controller.selected = chess.E2
        
        # Click on e4 to move
        initial_moves = len(controller.board.move_stack)
        controller.on_click(chess.E4)
        
        # Verify move was made
        self.assertEqual(len(controller.board.move_stack), initial_moves + 1)
        self.assertIsNone(controller.selected)

    def test_undo_move(self):
        """Test undo_move pops last move from stack."""
        controller = GameController(self.mock_root)
        
        # Make a move
        move = chess.Move.from_uci("e2e4")
        controller.board.push(move)
        self.assertEqual(len(controller.board.move_stack), 1)
        
        # Undo
        controller.undo_move()
        self.assertEqual(len(controller.board.move_stack), 0)

    @patch('builtins.open', new_callable=mock_open, read_data='[Event "Test"]\n\n1. e4 e5')
    def test_load_pgn(self, mock_file):
        """Test loading PGN file."""
        controller = GameController(self.mock_root)
        self.mock_tk.filedialog.askopenfilename.return_value = "test.pgn"
        
        controller.load_pgn()
        
        # Verify board has moves
        self.assertGreater(len(controller.board.move_stack), 0)

    def test_save_pgn(self):
        """Test saving PGN file."""
        controller = GameController(self.mock_root)
        self.mock_tk.filedialog.asksaveasfilename.return_value = "test.pgn"
        
        with patch('builtins.open', mock_open()) as m:
            controller.save_pgn()
            m.assert_called_once()

    def test_toggle_engine(self):
        """Test toggling engine enables/disables AI."""
        controller = GameController(self.mock_root)
        self.assertFalse(controller.engine_enabled)
        
        controller.toggle_engine()
        # Should attempt to start engine
        self.assertTrue(controller.engine_enabled)

    def test_run_ai_move_simple_ai(self):
        """Test run_ai_move with SimpleAI."""
        controller = GameController(self.mock_root)
        controller.engine_enabled = False
        
        initial_moves = len(controller.board.move_stack)
        controller.run_ai_move()
        
        # Verify AI made a move
        self.assertEqual(len(controller.board.move_stack), initial_moves + 1)

    def test_run_ai_move_with_engine(self):
        """Test run_ai_move with Stockfish engine."""
        controller = GameController(self.mock_root)
        controller.engine_enabled = True
        # Use object.__setattr__ to bypass type checking for mock
        object.__setattr__(controller, 'engine', self.mock_engine)
        
        # Mock engine move
        mock_move = chess.Move.from_uci("e2e4")
        self.mock_engine.play.return_value.move = mock_move
        
        initial_moves = len(controller.board.move_stack)
        controller.run_ai_move()
        
        # Verify engine was called and move made
        self.mock_engine.play.assert_called_once()
        self.assertEqual(len(controller.board.move_stack), initial_moves + 1)

    def test_promotion_dialog(self):
        """Test promotion dialog selection."""
        controller = GameController(self.mock_root)
        
        # Mock dialog window
        with patch('game_controller.tk.Toplevel') as mock_toplevel:
            mock_dialog = MagicMock()
            mock_toplevel.return_value = mock_dialog
            
            # Test queen promotion (default)
            result = controller.ask_promotion(chess.WHITE)
            self.assertEqual(result, chess.QUEEN)

    def test_game_over_detection(self):
        """Test game over detection (checkmate/stalemate)."""
        controller = GameController(self.mock_root)
        
        # Set up checkmate position
        controller.board = chess.Board("k7/8/1K6/8/8/8/8/1R6 b - - 0 1")  # black is checkmated
        
        # Make sure board is in checkmate
        self.assertTrue(controller.board.is_checkmate())


class TestGameControllerIntegration(unittest.TestCase):
    """Integration tests for GameController without full mocking."""

    def test_simple_ai_vs_simple_ai(self):
        """Test two SimpleAI agents can play against each other."""
        board = chess.Board()
        ai = SimpleAI(depth=1)
        
        move_count = 0
        max_moves = 10
        
        while not board.is_game_over() and move_count < max_moves:
            move = ai.choose_move(board)
            self.assertIsNotNone(move)
            if move is not None:
                self.assertIn(move, list(board.legal_moves))
                board.push(move)
            move_count += 1
        
        self.assertGreater(move_count, 0)


if __name__ == '__main__':
    unittest.main()
