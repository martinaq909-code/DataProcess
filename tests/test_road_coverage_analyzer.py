"""Test road coverage analyzer functionality."""

import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.road_coverage_analyzer import RoadCoverageAnalyzer


class TestRoadCoverageAnalyzer(unittest.TestCase):
    """Test RoadCoverageAnalyzer class."""
    
    def test_parse_filename_valid(self):
        """Test parsing valid filenames."""
        # Positive coordinates
        bbox = RoadCoverageAnalyzer.parse_filename("120.123456_30.123456_120.234567_30.234567.png")
        self.assertIsNotNone(bbox)
        self.assertEqual(bbox, (120.123456, 30.123456, 120.234567, 30.234567))
        
        # Negative coordinates
        bbox = RoadCoverageAnalyzer.parse_filename("-120.123456_-30.123456_-120.234567_-30.234567.png")
        self.assertIsNotNone(bbox)
        self.assertEqual(bbox, (-120.123456, -30.123456, -120.234567, -30.234567))
        
        # Without extension
        bbox = RoadCoverageAnalyzer.parse_filename("116.300000_39.800000_116.500000_39.900000")
        self.assertIsNotNone(bbox)
        self.assertEqual(bbox, (116.3, 39.8, 116.5, 39.9))
    
    def test_parse_filename_invalid(self):
        """Test parsing invalid filenames."""
        # Invalid format
        bbox = RoadCoverageAnalyzer.parse_filename("invalid_filename.png")
        self.assertIsNone(bbox)
        
        # Missing coordinates
        bbox = RoadCoverageAnalyzer.parse_filename("120.123456_30.123456.png")
        self.assertIsNone(bbox)
        
        # Non-numeric
        bbox = RoadCoverageAnalyzer.parse_filename("abc_def_ghi_jkl.png")
        self.assertIsNone(bbox)
    
    def test_parse_filename_edge_cases(self):
        """Test edge cases for filename parsing."""
        # Zero coordinates
        bbox = RoadCoverageAnalyzer.parse_filename("0.000000_0.000000_0.100000_0.100000.png")
        self.assertIsNotNone(bbox)
        self.assertEqual(bbox, (0.0, 0.0, 0.1, 0.1))
        
        # Different decimal places
        bbox = RoadCoverageAnalyzer.parse_filename("120.1_30.2_120.3_30.4.png")
        self.assertIsNotNone(bbox)
        self.assertEqual(bbox, (120.1, 30.2, 120.3, 30.4))


if __name__ == '__main__':
    unittest.main()
