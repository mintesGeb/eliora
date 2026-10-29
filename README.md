# Eliora

Bible story and song videos for kids on the YouTube channel **Eliora — God is my light**.

- `episodes.json` — episode order and status
- `episodes/<nn-slug>/` — narration, lyrics and parent guide for each episode
- `tools/` — video builder (`build_episode.py`), screenshot stitcher (`stitch.py`)
- Branch `media` — holds only the latest finished video, so the browser can load it into YouTube

## Title art (MANDATORY for every episode)
The plain template title page (text on a flat colour with a picture box) is **banned** - MG called it boring and bad. Every episode needs `title_art.jpg`:
- A 16:9 Krea (or ChatGPT) image in the style of `tests/title/good-samaritan.jpg`: a full-bleed warm story scene with the family (Grandpa Sol, Zara, Eli, Pip) reacting to that story's moment, a carved wooden sign with the song title lettered in big, and a cream ribbon with the story name.
- Title and sign must not cover any character's head or face.
- Warm palette matching the story. Generate it before the build; set `"title_art": "title_art.jpg"` in ep.json.
- `build_v2.py` now refuses to build without it. Do not set ELIORA_ALLOW_TEMPLATE_TITLE.
- Budget ~300 Krea credits; commit the reference to `tests/title/<slug>.jpg`.
