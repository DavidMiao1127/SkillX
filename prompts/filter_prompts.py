"""Filter prompts for skill quality control."""

# General filter prompt (Stage 1)
GENERAL_FILTER_FUNCTIONAL = """You are a coding expert. Given a predefined skill, evaluate whether its quality is good or bad.

# Evaluation guidelines:
1. **Domain specificity**: Check whether the skill includes domain-specific library names apis, e.g., `apis.spotify.show_playlist_library`.
2. **Over-encapsulation**: Check whether the skill's implementation merely calls a single other skill (i.e., it is just a thin wrapper).
3. **No-Python-libraries**: Check whether additional Python libraries are introduced in the skill.
4. **Reusability**: Check whether there are parameters are specific.
5. **No-Functional style**: Check whether a functional style is being used (e.g., the presence of return).

# Bad Example1:
- No domain-specific library names mentioned
- Additional Python libraries have been introduced
- There are parameters are specific.
- The code is functional style.

```python
import datetime
username = "12345678"
song_ids = set()
for playlist in playlists:
    song_ids.update(playlist.get("song_ids", []))

return song_ids
```

# Bad Example2: Over-encapsulation
```python
apis.supervisor.complete_task(answer=answer)
```

# Good Example
```python
most_liked = None
max_likes = -1
for sid in song_ids:
    song = apis.spotify.show_song(song_id=sid)
    if song["like_count"] > max_likes:
        max_likes = song["like_count"]
        most_liked = song
```

Only return "good" or "bad". Don't return any other words.
"""

GENERAL_FILTER_ATOMIC = """You are a coding expert. Given a predefined skill, evaluate whether its quality is good or bad.

# Evaluation guidelines:
1. **No-Python code style**: Check whether a Python code style and additional Python libraries and are introduced in the skill.
2. **Reusability**: Check whether there are parameters are specific.
3. **No-Functional style**: Check whether a functional style is being used (e.g., the presence of return).

# Bad Example:
- Additional Python libraries have been introduced
- There are parameters are specific.
- The skill is code style.

import datetime
song_name_list = ["12345678"]
for song_name in song_name_list:
    get_song_ids(song_name=song_name)
return song_ids


# Good Example
get_user_details(user_id=user_id)
get_reservation_details(reservation_id=reservation_id)
get_flight_status(flight_number=flight_number, date=date)


Only return "good" or "bad". Don't return any other words.
"""

# Tool filter prompt (Stage 2)
TOOL_FILTER_PROMPT = """You are a tool-invocation expert. Based on the tool specifications, verify whether the provided tool invocations are correct.

## Input
1. **Tool invocation content**: may include one or multiple tool calls.
2. **Tool specifications**: including tool description, parameters, return schema, and other usage notes.

## Judging Guidelines
1. **Parameter validation**: Check whether the invocation parameters comply with the specifications (e.g., missing required parameters, unsupported/nonexistent parameters, wrong types or formats, invalid values, etc.).
2. **Call dependency**: For multiple tool calls, verify that their order does not violate logical dependencies. If there is no dependency between the calls, ignore this check.
3. **Comment–function alignment**: Ensure the logic described in any comments matches what the tool is designed to do.
4. **Output Format**: Provide your reasoning and conclude with either 'correct' or 'fail', wrapped in <answer></answer>.

"""

GENERAL_FILTER_PROMPTS = {
    "default": GENERAL_FILTER_FUNCTIONAL,
    "appworld": GENERAL_FILTER_FUNCTIONAL,
    "bfcl": GENERAL_FILTER_FUNCTIONAL,
    "tau2bench": GENERAL_FILTER_ATOMIC,
    "functional": GENERAL_FILTER_FUNCTIONAL,
    "atomic": GENERAL_FILTER_ATOMIC,
}

TOOL_FILTER_PROMPTS = {
    "default": TOOL_FILTER_PROMPT,
    "appworld": TOOL_FILTER_PROMPT,
    "bfcl": TOOL_FILTER_PROMPT,
    "tau2bench": TOOL_FILTER_PROMPT,
}
