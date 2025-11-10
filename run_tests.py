"""Test runner script to avoid package naming conflicts."""

import sys
import os

# Add the chess directory to path so we can import modules
chess_dir = os.path.join(os.path.dirname(__file__), 'chess')
sys.path.insert(0, chess_dir)

# Now run unittest
import unittest

if __name__ == '__main__':
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.join(chess_dir, 'tests')
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
