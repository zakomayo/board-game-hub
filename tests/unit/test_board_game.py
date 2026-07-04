# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from app.agent import search_board_game


def test_search_board_game_exact() -> None:
    """Test searching for a game by its exact name."""
    result = search_board_game("Die Macher")
    assert "Name: Die Macher" in result
    assert "Year released:" in result
    assert "Number of players:" in result
    assert "Rating:" in result
    assert "Weight:" in result
    assert "Mechanics:" in result


def test_search_board_game_case_insensitive() -> None:
    """Test searching for a game case-insensitively."""
    result = search_board_game("die macher")
    assert "Name: Die Macher" in result


def test_search_board_game_partial() -> None:
    """Test searching with a substring query."""
    result = search_board_game("Macher")
    assert "Name: Die Macher" in result


def test_search_board_game_not_found() -> None:
    """Test searching for a game that does not exist."""
    result = search_board_game("NonExistentGame12345")
    assert "Could not find any board game matching" in result


def test_search_board_game_multiple_matches() -> None:
    """Test search behavior when multiple matches are found."""
    # Searching for "monopol" should return multiple matches (e.g. Monopoly, Monopoly Deal, etc.)
    result = search_board_game("monopol")
    assert "Found" in result
    assert "games matching" in result
    assert "Please specify which game you mean" in result
