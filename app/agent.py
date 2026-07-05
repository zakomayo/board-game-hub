# ruff: noqa
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

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent, Context
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from dotenv import load_dotenv
load_dotenv()

import os
import google.auth

# Only configure Vertex AI if it's explicitly enabled (defaulting to True if not specified)
if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() == "true":
    try:
        _, project_id = google.auth.default()
    except Exception:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "mock-project-id")
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"



import csv

_games_list = None
_mechanics_map = None  # bgg_id -> list of mechanics
_themes_map = None
_subcategories_map = None
_kaggle_data_path = None


def get_kaggle_data_path() -> str:
    """Gets the path of the Kaggle dataset, downloading it if not already cached."""
    global _kaggle_data_path
    if _kaggle_data_path is not None:
        return _kaggle_data_path
        
    try:
        import kagglehub
        _kaggle_data_path = kagglehub.dataset_download('threnjen/board-games-database-from-boardgamegeek')
    except Exception as e:
        print(f"Error fetching dataset from Kaggle, falling back to local: {e}")
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _kaggle_data_path = os.path.join(base_dir, "data")
        
    return _kaggle_data_path


def load_themes_map() -> dict[str, list[str]]:
    """Loads themes dataset into memory on-demand if not already cached."""
    global _themes_map
    if _themes_map is not None:
        return _themes_map
        
    _themes_map = {}
    filepath = os.path.join(get_kaggle_data_path(), "themes.csv")
        
    if os.path.exists(filepath):
        try:
            with open(filepath, encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                for row in reader:
                    if not row:
                        continue
                    bgg_id = row[0]
                    active_themes = []
                    for i in range(1, len(row)):
                        if i < len(row) and row[i] == '1':
                            # Normalize theme names (e.g. "Theme_Fantasy" -> "fantasy")
                            theme_name = headers[i].replace("Theme_", "").lower().strip()
                            active_themes.append(theme_name)
                    _themes_map[bgg_id] = active_themes
        except Exception as e:
            print(f"Error loading themes: {e}")
            
    return _themes_map


def load_subcategories_map() -> dict[str, list[str]]:
    """Loads subcategories dataset into memory on-demand if not already cached."""
    global _subcategories_map
    if _subcategories_map is not None:
        return _subcategories_map
        
    _subcategories_map = {}
    filepath = os.path.join(get_kaggle_data_path(), "subcategories.csv")
        
    if os.path.exists(filepath):
        try:
            with open(filepath, encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                for row in reader:
                    if not row:
                        continue
                    bgg_id = row[0]
                    active_subs = []
                    for i in range(1, len(row)):
                        if i < len(row) and row[i] == '1':
                            sub_name = headers[i].lower().strip()
                            active_subs.append(sub_name)
                    _subcategories_map[bgg_id] = active_subs
        except Exception as e:
            print(f"Error loading subcategories: {e}")
            
    return _subcategories_map


def load_data():
    """Loads games and mechanics datasets into memory if not already cached."""
    global _games_list, _mechanics_map
    if _games_list is not None:
        return _games_list, _mechanics_map
    
    _games_list = []
    _mechanics_map = {}
    
    data_dir = get_kaggle_data_path()
    games_path = os.path.join(data_dir, "games.csv")
    mechanics_path = os.path.join(data_dir, "mechanics.csv")
    
    try:
        if os.path.exists(mechanics_path):
            with open(mechanics_path, encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                mechanic_names = headers[1:]
                for row in reader:
                    if not row:
                        continue
                    bgg_id = row[0]
                    active_mechanics = []
                    for name, val in zip(mechanic_names, row[1:]):
                        if val == '1':
                            active_mechanics.append(name)
                    _mechanics_map[bgg_id] = active_mechanics
    except Exception as e:
        print(f"Error loading mechanics: {e}")
        
    try:
        if os.path.exists(games_path):
            with open(games_path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    _games_list.append(row)
    except Exception as e:
        print(f"Error loading games: {e}")
        
    return _games_list, _mechanics_map


def _load_owned_game_ids() -> set[str]:
    """Helper to load owned game IDs from data/owned_games.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(base_dir, "data", "owned_games.json")
    if not os.path.exists(filepath):
        filepath = os.path.join("data", "owned_games.json")
    if os.path.exists(filepath):
        try:
            import json
            with open(filepath, encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get("owned_game_ids", []))
        except Exception as e:
            print(f"Error loading owned games: {e}")
    return set()


def _save_owned_game_ids(owned_ids: set[str]):
    """Helper to save owned game IDs to data/owned_games.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(base_dir, "data", "owned_games.json")
    if not os.path.exists(os.path.dirname(filepath)):
        filepath = os.path.join("data", "owned_games.json")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        import json
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump({"owned_game_ids": list(owned_ids)}, f, indent=2)
    except Exception as e:
        print(f"Error saving owned games: {e}")


def _load_session_history() -> list[dict]:
    """Helper to load session history from data/session_history.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(base_dir, "data", "session_history.json")
    if not os.path.exists(filepath):
        filepath = os.path.join("data", "session_history.json")
    if os.path.exists(filepath):
        try:
            import json
            with open(filepath, encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading session history: {e}")
    return []


def _save_session_history(history: list[dict]):
    """Helper to save session history to data/session_history.json."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filepath = os.path.join(base_dir, "data", "session_history.json")
    if not os.path.exists(os.path.dirname(filepath)):
        filepath = os.path.join("data", "session_history.json")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        import json
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error saving session history: {e}")


def match_game(query: str, games_list: list[dict]) -> dict | list[dict] | None:
    """Finds a board game match in the games list by Name or BGGId."""
    query_clean = query.strip().lower()
    if not query_clean:
        return None
        
    # 1. Exact match on Name or BGGId
    exact_matches = [g for g in games_list if g.get("Name", "").strip().lower() == query_clean or g.get("BGGId") == query_clean]
    if len(exact_matches) == 1:
        return exact_matches[0]
        
    # 2. Substring match
    substring_matches = [g for g in games_list if query_clean in g.get("Name", "").strip().lower()]
    if len(substring_matches) == 1:
        return substring_matches[0]
    elif len(substring_matches) > 1:
        return substring_matches
        
    return None


def lookup_bgg_details_optimized(bgg_id: str, filename: str) -> list[str]:
    """Helper to quickly lookup active columns in a BGG CSV dataset by BGGId on-demand."""
    filepath = os.path.join(get_kaggle_data_path(), filename)
    if not os.path.exists(filepath):
        return []
        
    results = []
    try:
        with open(filepath, encoding='utf-8') as f:
            header_line = f.readline()
            headers = next(csv.reader([header_line]))
            
            try:
                bgg_id_idx = headers.index("BGGId")
            except ValueError:
                bgg_id_idx = 0
                
            is_first_col = (bgg_id_idx == 0)
            is_second_to_last = (bgg_id_idx == len(headers) - 2)
            
            for line in f:
                if not line:
                    continue
                
                # Check BGGId using fast splits
                if is_first_col:
                    current_id = line.split(',', 1)[0]
                elif is_second_to_last:
                    parts = line.rsplit(',', 2)
                    if len(parts) >= 2:
                        current_id = parts[1]
                    else:
                        continue
                else:
                    parts = line.strip().split(',')
                    if len(parts) <= bgg_id_idx:
                        continue
                    current_id = parts[bgg_id_idx]
                    
                if current_id == bgg_id:
                    row = line.strip().split(',')
                    for i in range(len(row)):
                        if i == bgg_id_idx:
                            continue
                        if i < len(row) and row[i] == '1':
                            header = headers[i]
                            if not header.startswith("Low-Exp"):
                                results.append(header)
                    break
    except Exception as e:
        print(f"Error querying {filename} for {bgg_id}: {e}")
        
    return results


def search_board_game(name: str) -> str:
    """Searches for a board game by name in the local database and returns its details.

    Args:
        name: The name of the board game to search for.

    Returns:
        A formatted string of the board game details including Name, Year released,
        Number of players who can play, rating, weight, mechanics, and extra details.
    """
    games, mechanics_map = load_data()
    
    query = name.strip().lower()
    
    # Try exact matches first
    exact_matches = [g for g in games if g.get("Name", "").strip().lower() == query]
    
    if exact_matches:
        matches = exact_matches
    else:
        # Fallback to case-insensitive contains match
        matches = [g for g in games if query in g.get("Name", "").strip().lower()]
        
    if not matches:
        return f"Could not find any board game matching '{name}'."
        
    # If multiple matches are found (>5), list top 5 popular ones
    if len(matches) > 5:
        def get_popularity(game):
            try:
                return int(game.get("NumUserRatings", 0))
            except ValueError:
                return 0
        matches_sorted = sorted(matches, key=get_popularity, reverse=True)
        top_matches = matches_sorted[:5]
        match_list = "\n".join(f"- {g.get('Name')} ({g.get('YearPublished')})" for g in top_matches)
        return (
            f"Found {len(matches)} games matching '{name}'. Here are the top 5 matches:\n"
            f"{match_list}\n"
            f"Please specify which game you mean or search with a more precise name."
        )
        
    # Format the details for the matches
    results = []
    for game in matches:
        g_name = game.get("Name")
        year = game.get("YearPublished", "N/A")
        min_players = game.get("MinPlayers", "N/A")
        max_players = game.get("MaxPlayers", "N/A")
        rating = game.get("AvgRating", "N/A")
        weight = game.get("GameWeight", "N/A")
        bgg_id = game.get("BGGId")
        
        # Extra fields from games.csv
        best_players = game.get("BestPlayers", "N/A")
        good_players_raw = game.get("GoodPlayers", "N/A")
        good_players = good_players_raw.replace("[", "").replace("]", "").replace("'", "").replace('"', "").strip()
        if not good_players:
            good_players = "N/A"
        description = game.get("Description", "N/A")
        kickstarted = "Yes" if game.get("Kickstarted") == "1" else "No"
        image_path = game.get("ImagePath", "N/A")
        
        # Mechanics
        mechanics = mechanics_map.get(bgg_id, []) if bgg_id else []
        mechanics_str = ", ".join(mechanics) if mechanics else "None"
        
        # Query on-demand relations from Kaggle CSV files
        designers = lookup_bgg_details_optimized(bgg_id, "designers_reduced.csv") if bgg_id else []
        designers_str = ", ".join(designers) if designers else "None"
        
        themes = lookup_bgg_details_optimized(bgg_id, "themes.csv") if bgg_id else []
        themes_str = ", ".join(themes) if themes else "None"
        
        subcategories = lookup_bgg_details_optimized(bgg_id, "subcategories.csv") if bgg_id else []
        subcategories_str = ", ".join(subcategories) if subcategories else "None"
        
        # Formatting rating and weight
        try:
            rating_formatted = f"{float(rating):.2f}/10"
        except ValueError:
            rating_formatted = f"{rating}/10"
            
        try:
            weight_formatted = f"{float(weight):.2f}/5"
        except ValueError:
            weight_formatted = f"{weight}/5"
            
        details = (
            f"Name: {g_name}\n"
            f"Year released: {year}\n"
            f"Number of players: {min_players}-{max_players} players\n"
            f"Best player count: {best_players}\n"
            f"Recommended player counts: {good_players}\n"
            f"Rating: {rating_formatted}\n"
            f"Weight: {weight_formatted}\n"
            f"Kickstarter: {kickstarted}\n"
            f"Designers: {designers_str}\n"
            f"Mechanics: {mechanics_str}\n"
            f"Themes: {themes_str}\n"
            f"Subcategories: {subcategories_str}\n"
            f"Image Path: {image_path}\n"
            f"Description: {description}"
        )
        results.append(details)
        
    return "\n\n---\n\n".join(results)


def recommend_board_games(
    player_count: int | None = None,
    weight_category: str | None = None,
    mechanics: list[str] | None = None,
    themes: list[str] | None = None,
    subcategories: list[str] | None = None,
    limit: int = 3
) -> str:
    """Recommends board games from the local database based on user requirements.

    Args:
        player_count: Recommended or supported number of players.
        weight_category: Complexity level: 'light', 'medium', or 'heavy'.
        mechanics: List of requested board game mechanics.
        themes: List of requested themes.
        subcategories: List of requested subcategories.
        limit: Number of recommendations to return (default 3).

    Returns:
        A formatted string listing the top recommended games and their details.
    """
    games, mechanics_map = load_data()
    
    # 1. Player Count Filtering
    candidates = []
    for game in games:
        if player_count is not None:
            try:
                min_p = int(game.get("MinPlayers", 0))
                max_p = int(game.get("MaxPlayers", 0))
                if not (min_p <= player_count <= max_p):
                    continue
            except ValueError:
                pass
        candidates.append(game)
        
    if not candidates:
        return "Could not find any games matching your requirements."
        
    # On-demand loading of maps if requested
    themes_map = load_themes_map() if themes else {}
    subs_map = load_subcategories_map() if subcategories else {}
    
    # Normalize query arrays (lowercase and trim)
    mechanics_query = [m.lower().strip() for m in mechanics] if mechanics else []
    themes_query = [t.lower().strip() for t in themes] if themes else []
    subs_query = [s.lower().strip() for s in subcategories] if subcategories else []
    
    # Target weight mapping
    target_weight = None
    if weight_category:
        w_cat = weight_category.lower().strip()
        if w_cat == "light":
            target_weight = 1.5
        elif w_cat == "medium":
            target_weight = 2.5
        elif w_cat == "heavy":
            target_weight = 4.0
            
    # 2. Scoring candidates
    scored_candidates = []
    for game in candidates:
        score = 0.0
        bgg_id = game.get("BGGId")
        
        # A. Weight score
        if target_weight is not None:
            try:
                weight_val = float(game.get("GameWeight", 0.0))
                if weight_val > 0.0:
                    score += 1.0 / (1.0 + abs(weight_val - target_weight))
            except ValueError:
                pass
                
        # B. Mechanics score
        if mechanics_query and bgg_id:
            game_mechanics = [m.lower().strip() for m in mechanics_map.get(bgg_id, [])]
            matches = sum(1 for mq in mechanics_query if mq in game_mechanics)
            if mechanics_query:
                score += 2.0 * (matches / len(mechanics_query))
                
        # C. Themes score
        if themes_query and bgg_id:
            game_themes = themes_map.get(bgg_id, [])
            matches = sum(1 for tq in themes_query if any(tq in gt for gt in game_themes))
            if themes_query:
                score += 1.5 * (matches / len(themes_query))
                
        # D. Subcategories score
        if subs_query and bgg_id:
            game_subs = subs_map.get(bgg_id, [])
            matches = sum(1 for sq in subs_query if any(sq in gs for gs in game_subs))
            if subs_query:
                score += 1.0 * (matches / len(subs_query))
                
        # Get ratings and rank for scoring and tie-breaking
        try:
            bayes_rating = float(game.get("BayesAvgRating", 0.0))
        except ValueError:
            bayes_rating = 0.0
            
        try:
            r_val = int(game.get("Rank:boardgame", 22000))
            if r_val <= 0:
                r_val = 22000
        except ValueError:
            r_val = 22000
            
        # Scale rank: 22000 is worst, 1 is best. Max rank score is 2.0.
        rank_score = ((22000 - r_val) / 22000.0) * 2.0
        if rank_score < 0:
            rank_score = 0.0
            
        # Scale rating: Max rating score is 2.0 (representing 10/10).
        rating_score = (bayes_rating / 10.0) * 2.0
        
        # Add to total score
        score += rank_score + rating_score
        
        try:
            num_ratings = int(game.get("NumUserRatings", 0))
        except ValueError:
            num_ratings = 0
            
        scored_candidates.append((score, bayes_rating, num_ratings, game))
        
    # 3. Sort candidates: Score desc, then BayesAvgRating desc, then NumUserRatings desc
    scored_candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    
    top_matches = scored_candidates[:limit]
    if not top_matches or (player_count is None and not weight_category and not mechanics and not themes and not subcategories):
        top_matches = sorted(scored_candidates, key=lambda x: (x[1], x[2]), reverse=True)[:limit]
        
    results = []
    for idx, (score, bayes_rating, num_ratings, game) in enumerate(top_matches, 1):
        g_name = game.get("Name")
        year = game.get("YearPublished", "N/A")
        min_players = game.get("MinPlayers", "N/A")
        max_players = game.get("MaxPlayers", "N/A")
        rating = game.get("AvgRating", "N/A")
        weight = game.get("GameWeight", "N/A")
        bgg_id = game.get("BGGId")
        description = game.get("Description", "N/A")
        kickstarted = "Yes" if game.get("Kickstarted") == "1" else "No"
        image_path = game.get("ImagePath", "N/A")
        
        # Query on-demand relations
        designers = lookup_bgg_details_optimized(bgg_id, "designers_reduced.csv") if bgg_id else []
        designers_str = ", ".join(designers) if designers else "None"
        
        mechanics_list = mechanics_map.get(bgg_id, []) if bgg_id else []
        mechanics_str = ", ".join(mechanics_list) if mechanics_list else "None"
        
        themes_list = load_themes_map().get(bgg_id, []) if bgg_id else []
        themes_str = ", ".join(t.capitalize() for t in themes_list) if themes_list else "None"
        
        subcategories_list = load_subcategories_map().get(bgg_id, []) if bgg_id else []
        subcategories_str = ", ".join(s.capitalize() for s in subcategories_list) if subcategories_list else "None"
        
        # Formatting rating and weight
        try:
            rating_formatted = f"{float(rating):.2f}/10"
        except ValueError:
            rating_formatted = f"{rating}/10"
            
        try:
            weight_formatted = f"{float(weight):.2f}/5"
        except ValueError:
            weight_formatted = f"{weight}/5"
            
        details = (
            f"Recommendation #{idx}:\n"
            f"Name: {g_name}\n"
            f"Year released: {year}\n"
            f"Number of players: {min_players}-{max_players} players\n"
            f"Rating: {rating_formatted}\n"
            f"Weight: {weight_formatted}\n"
            f"Kickstarter: {kickstarted}\n"
            f"Designers: {designers_str}\n"
            f"Mechanics: {mechanics_str}\n"
            f"Themes: {themes_str}\n"
            f"Subcategories: {subcategories_str}\n"
            f"Image Path: {image_path}\n"
            f"Description: {description}"
        )
        results.append(details)
        
    return f"Here are the top {len(results)} board game recommendations matching your criteria:\n\n" + "\n\n---\n\n".join(results)


def add_owned_games(games: list[str]) -> str:
    """Adds a list of board games to the user's owned games list.

    Args:
        games: List of game names (or BGGIds) to add.

    Returns:
        A summary of the action, including successfully added games, already owned games,
        ambiguous matches, and games not found.
    """
    games_list, _ = load_data()
    owned_ids = _load_owned_game_ids()
    
    added = []
    already_owned = []
    ambiguous = {}
    not_found = []
    
    for game_query in games:
        match = match_game(game_query, games_list)
        if match is None:
            not_found.append(game_query)
        elif isinstance(match, list):
            def get_popularity(g):
                try:
                    return int(g.get("NumUserRatings", 0))
                except ValueError:
                    return 0
            sorted_matches = sorted(match, key=get_popularity, reverse=True)[:5]
            ambiguous[game_query] = sorted_matches
        else:
            bgg_id = match.get("BGGId")
            g_name = match.get("Name")
            if bgg_id in owned_ids:
                already_owned.append(f"{g_name} (ID: {bgg_id})")
            else:
                owned_ids.add(bgg_id)
                added.append(f"{g_name} (ID: {bgg_id})")
                
    if added:
        _save_owned_game_ids(owned_ids)
        
    summary = []
    if added:
        summary.append("Added to your owned list:\n" + "\n".join(f"- {g}" for g in added))
    if already_owned:
        summary.append("Already in your owned list:\n" + "\n".join(f"- {g}" for g in already_owned))
    if not_found:
        summary.append("Could not find these games:\n" + "\n".join(f"- {g}" for g in not_found))
    if ambiguous:
        ambig_lines = []
        for q, matches in ambiguous.items():
            options = ", ".join(f"'{m.get('Name')}' (ID: {m.get('BGGId')})" for m in matches)
            ambig_lines.append(f"- '{q}' matched multiple: {options}")
        summary.append("Ambiguous matches (please clarify which one you mean):\n" + "\n".join(ambig_lines))
        
    return "\n\n".join(summary) if summary else "No games were provided or processed."


def remove_owned_games(games: list[str]) -> str:
    """Removes a list of board games from the user's owned games list.

    Args:
        games: List of game names (or BGGIds) to remove.

    Returns:
        A summary of the games successfully removed or not found.
    """
    games_list, _ = load_data()
    owned_ids = _load_owned_game_ids()
    
    removed = []
    not_owned = []
    not_found = []
    
    for game_query in games:
        match = match_game(game_query, games_list)
        if match is None:
            if game_query in owned_ids:
                owned_ids.remove(game_query)
                removed.append(f"Game ID {game_query}")
            else:
                not_found.append(game_query)
        elif isinstance(match, list):
            matched_owned = [m for m in match if m.get("BGGId") in owned_ids]
            if len(matched_owned) == 1:
                bgg_id = matched_owned[0].get("BGGId")
                g_name = matched_owned[0].get("Name")
                owned_ids.remove(bgg_id)
                removed.append(f"{g_name} (ID: {bgg_id})")
            elif len(matched_owned) > 1:
                options = ", ".join(f"'{m.get('Name')}' (ID: {m.get('BGGId')})" for m in matched_owned)
                not_owned.append(f"'{game_query}' is ambiguous to remove. Multiple matches in owned list: {options}")
            else:
                not_owned.append(game_query)
        else:
            bgg_id = match.get("BGGId")
            g_name = match.get("Name")
            if bgg_id in owned_ids:
                owned_ids.remove(bgg_id)
                removed.append(f"{g_name} (ID: {bgg_id})")
            else:
                not_owned.append(f"{g_name} (ID: {bgg_id})")
                
    if removed:
        _save_owned_game_ids(owned_ids)
        
    summary = []
    if removed:
        summary.append("Removed from your owned list:\n" + "\n".join(f"- {g}" for g in removed))
    if not_owned:
        summary.append("Were not in your owned list:\n" + "\n".join(f"- {g}" for g in not_owned))
    if not_found:
        summary.append("Could not find these games to remove:\n" + "\n".join(f"- {g}" for g in not_found))
        
    return "\n\n".join(summary) if summary else "No games were provided or processed."


def list_owned_games() -> str:
    """Lists all board games currently owned by the user.

    Returns:
        A formatted string listing the owned games and their basic details.
    """
    games_list, mechanics_map = load_data()
    owned_ids = _load_owned_game_ids()
    
    if not owned_ids:
        return "You do not own any board games yet. Add some by prompting or uploading a list!"
        
    owned_games = [g for g in games_list if g.get("BGGId") in owned_ids]
    
    results = []
    for idx, game in enumerate(owned_games, 1):
        g_name = game.get("Name")
        year = game.get("YearPublished", "N/A")
        min_players = game.get("MinPlayers", "N/A")
        max_players = game.get("MaxPlayers", "N/A")
        rating = game.get("AvgRating", "N/A")
        weight = game.get("GameWeight", "N/A")
        bgg_id = game.get("BGGId")
        description = game.get("Description", "N/A")
        
        try:
            rating_formatted = f"{float(rating):.2f}/10"
        except ValueError:
            rating_formatted = f"{rating}/10"
            
        try:
            weight_formatted = f"{float(weight):.2f}/5"
        except ValueError:
            weight_formatted = f"{weight}/5"
            
        designers = lookup_bgg_details_optimized(bgg_id, "designers_reduced.csv") if bgg_id else []
        designers_str = ", ".join(designers) if designers else "None"
        
        mechanics_list = mechanics_map.get(bgg_id, []) if bgg_id else []
        mechanics_str = ", ".join(mechanics_list) if mechanics_list else "None"
        
        themes_list = load_themes_map().get(bgg_id, []) if bgg_id else []
        themes_str = ", ".join(t.capitalize() for t in themes_list) if themes_list else "None"
        
        subcategories_list = load_subcategories_map().get(bgg_id, []) if bgg_id else []
        subcategories_str = ", ".join(s.capitalize() for s in subcategories_list) if subcategories_list else "None"
        
        desc_words = description.split()
        desc_snippet = " ".join(desc_words[:30]) + "..." if len(desc_words) > 30 else description
        
        details = (
            f"{idx}. {g_name} ({year})\n"
            f"   Players: {min_players}-{max_players} | Rating: {rating_formatted} | Weight: {weight_formatted}\n"
            f"   Designers: {designers_str} | Mechanics: {mechanics_str}\n"
            f"   Themes: {themes_str} | Subcategories: {subcategories_str}\n"
            f"   Description: {desc_snippet}"
        )
        results.append(details)
        
    return f"You currently own {len(results)} board games:\n\n" + "\n\n".join(results)


def organize_gaming_session(
    categories: list[str] = ["beginners", "intermediate", "experts"]
) -> str:
    """Organizes a 4-hour gaming session across a flexible number of tables using owned board games.

    Args:
        categories: A list of categories for each table in order (e.g. ['beginners', 'intermediate', 'experts']).
                     Allowed category values are 'beginners', 'intermediate', or 'experts'.

    Returns:
        A formatted string describing the scheduled games for each table.
    """
    games, mechanics_map = load_data()
    owned_ids = _load_owned_game_ids()
    
    if not owned_ids:
        return "You don't own any board games yet! Add some first to organize a session."
        
    owned_games = [g for g in games if g.get("BGGId") in owned_ids]
    
    # 1. Determine last calendar session's games to avoid repeating them
    history = _load_session_history()
    last_session_ids = set()
    if history:
        last_session = history[-1]
        for tbl_games in last_session.get("tables", {}).values():
            for g_id in tbl_games:
                last_session_ids.add(g_id)
                
    # Filter out recently played games if possible
    available_pool = [g for g in owned_games if g.get("BGGId") not in last_session_ids]
    warn_repeat = False
    
    if len(available_pool) < len(categories):
        available_pool = list(owned_games)
        if last_session_ids:
            warn_repeat = True
            
    # Calculate Quality Score for each game to pick best games first
    def get_quality_score(game):
        score = 0.0
        try:
            bayes_rating = float(game.get("BayesAvgRating", 0.0))
        except ValueError:
            bayes_rating = 0.0
            
        try:
            r_val = int(game.get("Rank:boardgame", 22000))
            if r_val <= 0:
                r_val = 22000
        except ValueError:
            r_val = 22000
            
        rank_score = ((22000 - r_val) / 22000.0) * 2.0
        if rank_score < 0:
            rank_score = 0.0
        rating_score = (bayes_rating / 10.0) * 2.0
        return rank_score + rating_score
        
    # Sort pool by quality score descending
    available_pool = sorted(available_pool, key=get_quality_score, reverse=True)
    
    # Table classifications
    tables_setup = []
    for idx, cat in enumerate(categories, 1):
        tables_setup.append({
            "name": f"Table {idx}",
            "category": cat.lower().strip(),
            "games": [],
            "total_time": 0
        })
    
    # Prioritize Expert tables first to get heavy games from the pool
    schedule_order = []
    for t in tables_setup:
        if t["category"] == "experts":
            schedule_order.append((0, t))
        elif t["category"] == "intermediate":
            schedule_order.append((1, t))
        else:
            schedule_order.append((2, t))
            
    schedule_order.sort(key=lambda x: x[0])
    
    for _, table in schedule_order:
        cat = table["category"]
        budget = 240
        
        # Determine allowed games for this category
        allowed_candidates = []
        for g in available_pool:
            try:
                w = float(g.get("GameWeight", 0.0))
            except ValueError:
                w = 0.0
                
            if cat == "beginners":
                if w <= 2.0:
                    allowed_candidates.append(g)
            elif cat == "intermediate":
                if w <= 3.0:
                    allowed_candidates.append(g)
            else: # experts
                allowed_candidates.append(g)
                
        # For experts: definitely try to include at least one heavy game first!
        if cat == "experts":
            heavy_candidates = []
            other_candidates = []
            for g in allowed_candidates:
                try:
                    w = float(g.get("GameWeight", 0.0))
                except ValueError:
                    w = 0.0
                if w > 3.0:
                    heavy_candidates.append(g)
                else:
                    other_candidates.append(g)
            allowed_candidates = heavy_candidates + other_candidates
            
        # Select games to fill 240 minutes budget (limit of max 3 games)
        for game in list(allowed_candidates):
            if table["total_time"] >= budget or len(table["games"]) >= 3:
                break
                
            try:
                playtime = int(game.get("MfgPlaytime", 0))
                if playtime <= 0:
                    playtime = 60
            except ValueError:
                playtime = 60
                
            try:
                weight_val = float(game.get("GameWeight", 0.0))
            except ValueError:
                weight_val = 0.0
                
            teaching_time = 15 if weight_val <= 2.0 else 30
            effective_time = playtime + teaching_time
            
            if table["total_time"] + effective_time <= budget:
                table["games"].append({
                    "game": game,
                    "playtime": playtime,
                    "teaching_time": teaching_time,
                    "effective_time": effective_time,
                    "weight": weight_val
                })
                table["total_time"] += effective_time
                if game in available_pool:
                    available_pool.remove(game)
                    
    # Save newly organized session to history
    new_session_data = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "tables": {
            t["name"]: [g["game"].get("BGGId") for g in t["games"]] for t in tables_setup
        }
    }
    history.append(new_session_data)
    _save_session_history(history)
    
    # Format return output
    output_lines = []
    output_lines.append("### 🗓️ Saturday Gaming Session Schedule (4 Hours / Table)")
    if warn_repeat:
        output_lines.append("> ⚠️ *Note: Due to a limited owned games pool, some games from the last calendar session were reused.*")
        
    for table in tables_setup:
        output_lines.append(f"\n#### 🗂️ {table['name']} ({table['category'].capitalize()})")
        output_lines.append(f"**Total Allocated Time**: {table['total_time']} / 240 mins")
        if not table["games"]:
            output_lines.append("*(No games could be scheduled. Try adding more games matching this category to your owned list!)*")
        else:
            for idx, item in enumerate(table["games"], 1):
                g = item["game"]
                weight_class = "Lightweight" if item["weight"] <= 2.0 else ("Medium" if item["weight"] <= 3.0 else "Heavy")
                output_lines.append(
                    f"{idx}. **{g.get('Name')}** ({g.get('YearPublished')})\n"
                    f"   - Weight: {item['weight']:.2f} ({weight_class})\n"
                    f"   - Time: {item['playtime']} mins play + {item['teaching_time']} mins rules teach = {item['effective_time']} mins"
                )
                
    return "\n".join(output_lines)


def security_checkpoint(callback_context: Context) -> types.Content | None:
    import re
    import json
    import sys
    import datetime

    # 1. Structured JSON audit logging helper
    def log_audit(severity: str, decision: str, route: str, scrubbed_items: list[str], reason: str):
        log_entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "severity": severity,
            "decision": decision,
            "route": route,
            "user_id": callback_context.user_id,
            "scrubbed_items": scrubbed_items,
            "reason": reason
        }
        print(json.dumps(log_entry), file=sys.stderr, flush=True)

    # If there is no user content, just pass
    if not callback_context.user_content or not callback_context.user_content.parts:
        log_audit("INFO", "ALLOW", "DEFAULT", [], "No user content to process")
        return None

    # Retrieve all user text parts
    text_parts = [part for part in callback_context.user_content.parts if part.text]
    full_text = " ".join(part.text for part in text_parts)

    # 2. Prompt Injection Detection
    injection_keywords = [
        "ignore previous instructions",
        "system prompt",
        "jailbreak",
        "ignore the above",
        "bypass safety",
        "you are now a",
        "ignore instruction"
    ]
    detected_injection_keywords = [kw for kw in injection_keywords if kw in full_text.lower()]
    if detected_injection_keywords:
        callback_context.route = "SECURITY_EVENT"
        log_audit(
            severity="CRITICAL",
            decision="BLOCK",
            route="SECURITY_EVENT",
            scrubbed_items=[],
            reason=f"Prompt injection detected. Keywords: {detected_injection_keywords}"
        )
        return types.Content(
            role="model",
            parts=[types.Part.from_text(text="SECURITY_EVENT: Prompt injection attempt detected.")]
        )

    # 3. Domain-Specific Rule (Video Games / Console Filter)
    video_game_keywords = [
        "video game", "xbox", "playstation", "nintendo", 
        "fortnite", "minecraft", "call of duty", "fifa"
    ]
    detected_video_game_keywords = [kw for kw in video_game_keywords if kw in full_text.lower()]
    if detected_video_game_keywords:
        log_audit(
            severity="WARNING",
            decision="BLOCK",
            route="DEFAULT",
            scrubbed_items=[],
            reason=f"Domain policy violation: query contains video game keywords: {detected_video_game_keywords}"
        )
        return types.Content(
            role="model",
            parts=[types.Part.from_text(text="I am a Board Game assistant and cannot help with video games or console queries.")]
        )

    # 4. PII Scrubbing
    email_regex = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    phone_regex = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+?\d{10,13}')
    card_regex = re.compile(r'\b(?:\d[ -]*?){13,16}\b')

    scrubbed_items = []
    
    for part in callback_context.user_content.parts:
        if part.text:
            text = part.text
            
            if email_regex.search(text):
                text = email_regex.sub("[REDACTED_EMAIL]", text)
                if "email" not in scrubbed_items:
                    scrubbed_items.append("email")
                    
            if card_regex.search(text):
                text = card_regex.sub("[REDACTED_CARD]", text)
                if "card" not in scrubbed_items:
                    scrubbed_items.append("card")
                    
            if phone_regex.search(text):
                text = phone_regex.sub("[REDACTED_PHONE]", text)
                if "phone" not in scrubbed_items:
                    scrubbed_items.append("phone")
                    
            part.text = text

    if scrubbed_items:
        log_audit(
            severity="INFO",
            decision="ALLOW",
            route="DEFAULT",
            scrubbed_items=scrubbed_items,
            reason="PII scrubbed successfully"
        )
    else:
        log_audit(
            severity="INFO",
            decision="ALLOW",
            route="DEFAULT",
            scrubbed_items=[],
            reason="Query clean"
        )

    return None


board_game_hub_agent = Agent(
    name="board_game_hub_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="You are the Board Game Hub Gamesmaster, an enthusiastic, knowledgeable, and engaging tabletop sage. Greet users with board gaming references (e.g., 'Welcome to the table!', 'Let\'s roll!', 'Ready to draft a game?'), and use tabletop terminology naturally (e.g., 'meeples', 'deck building', 'victory points'). When a user asks about a board game, use the search_board_game tool to lookup its details and display Name, Year released, Number of players, Best/Recommended player counts, rating, weight, Designers, Mechanics, Themes, Subcategories, and a brief description. Crucially, summarize the provided description into exactly 2-3 readable sentences, as the raw data is lemmatized and lacks punctuation. When a user wants recommendations, ask for their requirements (number of players, weight category, mechanics, themes, etc.) if not provided, and call the recommend_board_games tool. Limit the recommendations to exactly 3 by default, and offer to show more only if the user explicitly asks. When a user wants to manage their owned games list (either by asking directly, or by uploading/attaching a document containing a list of games), extract the list of game names (or read the uploaded file contents to get the names) and use the add_owned_games, remove_owned_games, or list_owned_games tools to manage their list. If they ask whether they own a specific game or if it is on their list/collection, first call list_owned_games to retrieve their collection and then answer directly whether it is in their collection, rather than searching the database for its details. When a user wants to organize a gaming session, extract the player experience levels for all tables from their prompt (e.g. Table 1 category is beginners, Table 2 category is intermediate, etc.) and call the organize_gaming_session tool with the categories list in order. If they do not specify categories or number of tables, ask for clarification or default to beginners, intermediate, and experts for 3 tables.",
    tools=[search_board_game, recommend_board_games, add_owned_games, remove_owned_games, list_owned_games, organize_gaming_session],
    before_agent_callback=security_checkpoint,
)

app = App(
    root_agent=board_game_hub_agent,
    name="app",
)
