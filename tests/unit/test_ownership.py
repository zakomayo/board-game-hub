from unittest.mock import patch
from app.agent import add_owned_games, remove_owned_games, list_owned_games

# Mock set to act as database during tests
mock_owned_set = set()

def mock_load():
    return mock_owned_set

def mock_save(owned_ids):
    global mock_owned_set
    mock_owned_set = owned_ids

@patch('app.agent._load_owned_game_ids', side_effect=mock_load)
@patch('app.agent._save_owned_game_ids', side_effect=mock_save)
def test_ownership_flow(mock_save_fn, mock_load_fn):
    global mock_owned_set
    mock_owned_set.clear()
    
    # 1. Test listing empty list
    empty_res = list_owned_games()
    assert "You do not own any board games yet" in empty_res
    
    # 2. Test adding games
    add_res = add_owned_games(["Die Macher", "Dragonmaster"])
    assert "Added to your owned list" in add_res
    assert "Die Macher" in add_res
    assert "Dragonmaster" in add_res
    
    # 3. Verify they are in the list
    list_res = list_owned_games()
    assert "You currently own 2 board games" in list_res
    assert "Die Macher" in list_res
    assert "Dragonmaster" in list_res
    
    # 4. Test duplicate adding
    add_dup = add_owned_games(["Die Macher"])
    assert "Already in your owned list" in add_dup
    
    # 5. Test ambiguous adding
    add_ambig = add_owned_games(["monopol"])
    assert "Ambiguous matches" in add_ambig
    
    # 6. Test removing games
    remove_res = remove_owned_games(["Die Macher"])
    assert "Removed from your owned list" in remove_res
    assert "Die Macher" in remove_res
    
    # 7. Verify removed from listing
    list_final = list_owned_games()
    assert "You currently own 1 board games" in list_final
    assert "Die Macher" not in list_final
    assert "Dragonmaster" in list_final
