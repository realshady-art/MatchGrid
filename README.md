# MatchGrid

MatchGrid is an interactive football tactics board that lets users build lineups, move players across the pitch, and instantly estimate home/draw/away match outcomes from the current tactical setup.

Live demo: https://matchgrid-realshady.vercel.app/

## Product Idea

Football predictions are easier to understand when the model is connected to visible tactical choices. MatchGrid turns prediction into an interactive board: users can drag players into position, compare two lineups, and see how the expected outcome changes as the setup changes.

The product is designed for exploration, tactical storytelling, and lightweight decision support.

## Core Experience

- Drag-and-drop tactical board for home and away teams.
- Searchable player pool with league and player filtering.
- Free-form player positioning on a visual pitch.
- Instant home/draw/away probability output.
- Player cards and visual lineup state for quick comparison.
- Optional referee input for richer match context.

## How It Works

1. Player data is converted into simplified attacking, defensive, and goalkeeper indices.
2. Users select players and place them on the pitch.
3. The board captures both lineup strength and positional context.
4. A prediction layer compares the two sides and produces home/draw/away probabilities.
5. The interface updates immediately as the tactical setup changes.

## Product Effect

MatchGrid makes match prediction more explainable. Instead of showing a static number, it lets users experiment with the lineup and see how tactical changes affect the result profile.

## Tech Stack

- Python
- Flask
- pandas
- JavaScript
- HTML and CSS
- Football data processing

## Local Preview

```bash
git clone https://github.com/JeffreyDeng-spec/MatchGrid.git
cd MatchGrid
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py gui
```

Then open:

```text
http://127.0.0.1:5000
```

## Project Focus

MatchGrid is built around one product principle: make model output visible, interactive, and connected to the choices a football user actually understands.
