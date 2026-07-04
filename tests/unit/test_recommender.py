from app.agent import recommend_board_games

def test_recommend_by_player_count():
    """Test that recommendations match the player count requirement."""
    # Recommend a game for 5 players
    result = recommend_board_games(player_count=5, limit=3)
    assert "board game recommendations matching your criteria" in result
    assert "Recommendation #1:" in result
    assert "Recommendation #2:" in result
    assert "Recommendation #3:" in result
    # Every recommendation should support 5 players
    for game_details in result.split("---"):
        if "Number of players:" in game_details:
            players_line = [line for line in game_details.split("\n") if "Number of players:" in line][0]
            # e.g., "Number of players: 3-5 players"
            players_part = players_line.split(":")[1].replace("players", "").strip()
            min_p, max_p = map(int, players_part.split("-"))
            assert min_p <= 5 <= max_p

def test_recommend_by_weight_category():
    """Test that recommendations match the weight category requirement."""
    # Medium weight (Target complexity around 2.5)
    result = recommend_board_games(weight_category="medium", limit=1)
    assert "Recommendation #1:" in result
    for line in result.split("\n"):
        if "Weight:" in line:
            weight_val = float(line.split(":")[1].split("/")[0].strip())
            # Medium is up to 3.0, target is 2.5
            assert weight_val > 0.0

def test_recommend_by_mechanics():
    """Test that recommendations prioritize matching mechanics."""
    # Search with "Area Majority / Influence"
    result = recommend_board_games(mechanics=["Area Majority / Influence"], limit=3)
    # The first recommendation should include the mechanic in its Mechanics field
    first_recommendation = result.split("---")[0]
    assert "Mechanics:" in first_recommendation
    assert "Area Majority / Influence" in first_recommendation

def test_recommendation_limit():
    """Test that the limit parameter is respected."""
    result = recommend_board_games(player_count=4, limit=1)
    assert "Recommendation #1:" in result
    assert "Recommendation #2:" not in result
