#!/bin/bash

# Array of popular anime search terms (anime-focused)
anime_search_terms=(
    "Spirited Away"
    "Your Name"
    "Demon Slayer"
    "Attack on Titan"
    "Fullmetal Alchemist"
    "Studio Ghibli"
    "Pokemon"
    "Dragon Ball Z"
    "Naruto Shippuden"
    "Hunter x Hunter"
    "Mob Psycho 100"
    "Chainsaw Man"
    "Boruto"
    "Weathering with You"
)

# Array of popular manga search terms (manga-focused)
manga_search_terms=(
    "One Piece"
    "Naruto"
    "Berserk"
    "Vagabond"
    "Monster"
    "20th Century Boys"
    "Slam Dunk"
    "My Hero Academia"
    "Jujutsu Kaisen"
    "Tokyo Ghoul"
    "Made in Abyss"
    "Fire Punch"
    "Hell's Paradise"
    "Dandadan"
)

# Randomly choose between anime and manga search (0 = anime, 1 = manga)
operation=$((RANDOM % 2))

if [ $operation -eq 0 ]; then
  # anili_search_anime operation
  random_anime_index=$((RANDOM % ${#anime_search_terms[@]}))
  selected_anime="${anime_search_terms[$random_anime_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "anili_search_anime",
      "tool_args": {
        "term": "'"$selected_anime"'",
        "page": 1,
        "amount": 5
      }
    }'

else
  # anili_search_manga operation
  random_manga_index=$((RANDOM % ${#manga_search_terms[@]}))
  selected_manga="${manga_search_terms[$random_manga_index]}"
  
  curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
    -H 'Content-Type: application/json' \
    -d '{
      "tool_name": "anili_search_manga",
      "tool_args": {
        "term": "'"$selected_manga"'",
        "page": 1,
        "amount": 5
      }
    }'
fi 