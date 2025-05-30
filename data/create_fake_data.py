import json
import os

# Base data
data = {
    "identifier": "17",
    "motion": {"text": "The parliment took an example vote"},
    "start_date": "2005-02-22",
    "counts": [
        {"option": "yes", "value": 40},
        {"option": "no", "value": 85},
        {"option": "abstain", "value": 5},
    ],
    "votes": [],
    "sources": [{"url": "https://fakeurl.url/session/bill"}],
}

# Generate "yes" votes
i = 1
vote_options = {"yes": 0, "no": 1, "abstain": 2}
for key, value in vote_options.items():
    for _ in range(0, data["counts"][value]["value"]):
        vote = {"voter": {"name": f"Voter {i}"}, "option": key}
        data["votes"].append(vote)
        i += 1


# Output JSON
script_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(script_dir, "example_vote_event.json")

with open(output_path, "w", encoding="utf-8") as f:
    f.write(json.dumps(data, indent=2))
