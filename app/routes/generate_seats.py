import math


def generate_seats(vote_counts, groups):
    """
    Generate seat positions and attributes for semicircular parliament chart.

    Args:
        vote_counts: {'yes': int, 'no': int, 'abstain': int, 'others': int}
        groups: {'yes': [names], 'no': [names], 'abstain': [names]}

    Returns:
        List of dicts with keys: x, y, r (radius of dot), color, label
    """
    # To arrange seats in a circular layout, specify the number of seats from
    # inner to outer row so that the total adds up to 130.
    seats_per_row = [14, 17, 20, 23, 26, 30]
    edge_inset = 0.03
    max_total = 130

    # Canvas
    W = 800
    H = 300
    cx = W / 2
    cy = H - 12

    # Calculate totals
    total = sum(vote_counts.values())
    if total == 0:
        return []

    # Scale dot radius based on total: sqrt scale from [0,130] -> [15, 10]
    # Approximation: dot_radius = 15 - (sqrt(total) / sqrt(max_total)) * 5.0
    max_radius = 15
    min_radius = 10
    dot_radius = max_radius - (math.sqrt(total) / math.sqrt(max_total)) * (
        max_radius - min_radius
    )
    dot_radius = max(min_radius, min(max_radius, dot_radius))

    # Scale inner radius: sqrt scale from [0,130] -> [150, 110]
    max_inner = 150
    min_inner = 110
    inner_radius = max_inner - (math.sqrt(total) / math.sqrt(max_total)) * (
        max_inner - min_inner
    )
    inner_radius = max(min_inner, min(max_inner, inner_radius))

    # Scale row gap: sqrt scale from [0,130] -> [40, 25]
    max_gap = 40
    min_gap = 25
    row_gap = max_gap - (math.sqrt(total) / math.sqrt(max_total)) * (max_gap - min_gap)
    row_gap = max(min_gap, min(max_gap, row_gap))

    # Generate seat positions (inner to outer by row)
    seats = []
    for row in range(len(seats_per_row)):
        r = inner_radius + row * row_gap
        seats_this_row = seats_per_row[row]
        # Outer row uses 30 slots for spacing but draws only actual seats
        spacing_seats = 30 if row == len(seats_per_row) - 1 else seats_this_row

        for i in range(spacing_seats):
            # Skip seats beyond the actual count on outer row
            if row == len(seats_per_row) - 1 and i >= seats_this_row:
                continue

            # Compute theta
            if spacing_seats == 1:
                progress = 0.5
            else:
                progress = i / (spacing_seats - 1)

            theta = math.pi * (1 - edge_inset - progress * (1 - edge_inset * 2))
            x = cx + r * math.cos(theta)
            y = cy - r * math.sin(theta)

            seats.append({"x": x, "y": y, "row": row, "theta": theta})

    # Build color slots (gray others are placed last and do not get labels)
    color_order = ["yes", "no", "abstain", "others"]
    color_map = {
        "yes": "#0f8f7c",
        "no": "#cf294a",
        "abstain": "#d29b00",
        "others": "#b8b8b8",
    }
    slots = []
    for key in color_order:
        count = vote_counts.get(key, 0)
        slots.extend([key] * count)

    # Sort seats left-to-right by x coordinate
    indexed_seats = [(i, s) for i, s in enumerate(seats)]
    indexed_seats.sort(key=lambda p: (p[1]["x"], p[1]["y"]))

    # Assign colors and labels
    result = [None] * len(seats)
    queues = {
        "yes": groups.get("yes", [])[:],
        "no": groups.get("no", [])[:],
        "abstain": groups.get("abstain", [])[:],
        "others": [],
    }

    for sorted_idx, (orig_idx, seat) in enumerate(indexed_seats):
        key = slots[sorted_idx]
        color = color_map.get(key, "#ccc")
        label = queues[key].pop(0) if queues.get(key) else ""

        result[orig_idx] = {
            "x": round(seat["x"], 2),
            "y": round(seat["y"], 2),
            "r": round(dot_radius, 2),
            "color": color,
            "label": label,
        }

    return result
