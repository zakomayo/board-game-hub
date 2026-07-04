from unittest.mock import patch
from app.agent import organize_gaming_session

mock_owned_set = set()
mock_history = []

def mock_load_owned():
    return mock_owned_set

def mock_save_owned(owned_ids):
    global mock_owned_set
    mock_owned_set = owned_ids

def mock_load_history():
    return mock_history

def mock_save_history(history):
    global mock_history
    mock_history = history

@patch('app.agent._load_owned_game_ids', side_effect=mock_load_owned)
@patch('app.agent._save_owned_game_ids', side_effect=mock_save_owned)
@patch('app.agent._load_session_history', side_effect=mock_load_history)
@patch('app.agent._save_session_history', side_effect=mock_save_history)
def test_organizer_flow(mock_save_h, mock_load_h, mock_save_o, mock_load_o):
    global mock_owned_set, mock_history
    mock_owned_set.clear()
    mock_history.clear()
    
    # 1. Empty owned list
    res_empty = organize_gaming_session()
    assert "You don't own any board games yet" in res_empty
    
    # 2. Add some games of different weights to mock owned list
    # BGGId '42' (Tigris & Euphrates): Weight 3.51 (Heavy)
    # BGGId '2' (Dragonmaster): Weight 1.96 (Light)
    # BGGId '3' (Samurai): Weight 2.49 (Medium)
    # BGGId '4' (Tal der Könige): Weight 2.67 (Medium)
    mock_owned_set.update(['42', '2', '3', '4'])
    
    # Run organizer
    schedule = organize_gaming_session(
        table1_category="beginners",
        table2_category="intermediate",
        table3_category="experts"
    )
    
    # Verify schedule structure
    assert "Saturday Gaming Session Schedule" in schedule
    assert "Table 1 (Beginners)" in schedule
    assert "Table 2 (Intermediate)" in schedule
    assert "Table 3 (Experts)" in schedule
    
    # Check Beginners Table (only lightweight games <= 2.0 allowed)
    # BGGId '2' (Dragonmaster, weight 1.96) is the only candidate.
    # Therefore, Table 1 must have scheduled it.
    assert "Dragonmaster" in schedule
    
    # Check Experts Table (typically prioritizes heavy games > 3.0)
    # BGGId '42' (Tigris & Euphrates, weight 3.51) is heavy, so it should go here.
    assert "Tigris & Euphrates" in schedule
    
    # 3. Test history exclusion
    # The first session history should be populated
    assert len(mock_history) == 1
    
    # Clear pool of available games and run again. It should warn/reuse because the pool is too small to avoid repeats.
    schedule_repeat = organize_gaming_session(
        table1_category="beginners",
        table2_category="intermediate",
        table3_category="experts"
    )
    assert "reused" in schedule_repeat


@patch('app.agent._load_owned_game_ids', side_effect=mock_load_owned)
@patch('app.agent._save_owned_game_ids', side_effect=mock_save_owned)
@patch('app.agent._load_session_history', side_effect=mock_load_history)
@patch('app.agent._save_session_history', side_effect=mock_save_history)
def test_organizer_limit_max_three_games(mock_save_h, mock_load_h, mock_save_o, mock_load_o):
    global mock_owned_set, mock_history
    mock_owned_set.clear()
    mock_history.clear()
    
    # Add 6 lightweight games to the owned list
    # BGGIds: '2', '7', '11', '14', '17', '19'
    mock_owned_set.update(['2', '7', '11', '14', '17', '19'])
    
    # Run organizer for beginners (which only allows lightweight games)
    schedule = organize_gaming_session(
        table1_category="beginners",
        table2_category="beginners",
        table3_category="beginners"
    )
    
    # Each table should contain at most 3 games in the text output
    # (e.g. Table 1 output has numbered list like "1. ", "2. ", "3. ", but no "4. ")
    # Let's count how many games were scheduled on Table 1
    table1_section = schedule.split("Table 2")[0]
    assert "1. " in table1_section
    assert "2. " in table1_section
    assert "3. " in table1_section
    assert "4. " not in table1_section

