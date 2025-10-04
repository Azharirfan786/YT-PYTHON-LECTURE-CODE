from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# --------------------------
# Utility functions
# --------------------------

def str_to_time(s: str) -> datetime:
    return datetime.strptime(s, "%H:%M")

def time_to_str(t: datetime) -> str:
    return t.strftime("%H:%M")

def minutes_between(t1: datetime, t2: datetime) -> int:
    """Return difference in minutes (t2 - t1)."""
    return int((t2 - t1).total_seconds() // 60)


# --------------------------
# Train data
# --------------------------

trains: Dict[str, Dict] = {
    "20871": {
        "name": "Vande Bharat Express",
        "priority": 1,   # set 1 = highest for Vande Bharat
        "schedule": [("Howrah", "06:00"),
                     ("Kharagpur", "07:40"),
                     ("Tatanagar", "09:10")]
    },
    "12261": {
        "name": "Howrah–CSMT Duronto",
        "priority": 2,
        "schedule": [("Howrah", "05:45"),
                     ("Kharagpur", "07:20"),
                     ("Tatanagar", "08:48")]
    },
    "12813": {
        "name": "Steel Express",
        "priority": 4,
        "schedule": [("Howrah", "06:35"),
                     ("Kharagpur", "07:55"),
                     ("Tatanagar", "09:00")]
    },
    "12021": {
        "name": "Jan Shatabdi Express",
        "priority": 3,
        "schedule": [("Howrah", "06:15"),
                     ("Kharagpur", "07:50"),
                     ("Tatanagar", "09:47")]
    }
}


# --------------------------
# Effective Priority (STRICT)
# --------------------------

def get_effective_priority(train: Dict, delay: int) -> int:
    """
    Strict priority-only: ignore delay when deciding winner.
    Lower number => higher priority.
    """
    return train["priority"]


# --------------------------
# Conflict Resolver (priority-first)
# --------------------------

def resolve_conflicts(arrivals: List[List], headway: int) -> List[List]:
    """
    arrivals = [
        [tid, arrival_time(datetime), eff_priority(int), delay_mins(int), scheduled_time(datetime)], ...
    ]
    Rule on clash (gap < headway):
      - Winner chosen solely by eff_priority (lower numeric value wins).
      - If eff_priority equal, tie-break using scheduled_time (earlier scheduled wins).
      - Loser pushed to winner_time + headway.
    Returns modified arrivals (arrival_time entries may be updated).
    """
    arrivals.sort(key=lambda x: x[1])
    i = 1
    while i < len(arrivals):
        prev_tid, prev_t, prev_pr, prev_delay, prev_sched = arrivals[i-1]
        curr_tid, curr_t, curr_pr, curr_delay, curr_sched = arrivals[i]

        gap = minutes_between(prev_t, curr_t)

        if gap < headway:
            # choose winner by strict effective priority
            if prev_pr < curr_pr:
                winner_idx, loser_idx = i-1, i
                winner_time = arrivals[winner_idx][1]
            elif curr_pr < prev_pr:
                winner_idx, loser_idx = i, i-1
                winner_time = arrivals[winner_idx][1]
            else:
                # tie on priorities -> scheduled time as final tiebreaker
                if prev_sched <= curr_sched:
                    winner_idx, loser_idx = i-1, i
                    winner_time = arrivals[winner_idx][1]
                else:
                    winner_idx, loser_idx = i, i-1
                    winner_time = arrivals[winner_idx][1]

            new_loser_time = winner_time + timedelta(minutes=headway)

            # only push if it actually increases the loser's time
            if new_loser_time > arrivals[loser_idx][1]:
                arrivals[loser_idx][1] = new_loser_time
                # re-sort and restart scanning to handle cascading pushes
                arrivals.sort(key=lambda x: x[1])
                i = 1
                continue

        i += 1

    return arrivals


# --------------------------
# Reschedule All Trains
# --------------------------

def reschedule_all(trains: Dict[str, Dict], delays: Dict[str, int], headway: int
                  ) -> Tuple[Dict[str, List[Tuple[str, datetime]]], Dict[str, List[Tuple[str, datetime]]]]:
    """
    Build base schedules (original times + input delays) and resolve conflicts station-by-station.
    Returns (base_schedules, final_schedules)
    """
    # Build base schedules (apply input delays)
    base_schedules: Dict[str, List[Tuple[str, datetime]]] = {}
    for tid, tr in trains.items():
        delay = delays.get(tid, 0)
        sched = [(station, str_to_time(tstr) + timedelta(minutes=delay)) for station, tstr in tr["schedule"]]
        base_schedules[tid] = sched

    # copy for resolution
    final_schedules = {tid: list(sched) for tid, sched in base_schedules.items()}

    # deterministic station list
    stations = sorted({st for tr in trains.values() for (st, _) in tr["schedule"]})

    for station in stations:
        arrivals = []
        for tid, sched in final_schedules.items():
            for st, t in sched:
                if st == station:
                    # original scheduled datetime at this station (before applying delays)
                    orig_time_str = next(ot for s, ot in trains[tid]["schedule"] if s == st)
                    scheduled_dt = str_to_time(orig_time_str)
                    delay_here = minutes_between(scheduled_dt, t)
                    eff_pr = get_effective_priority(trains[tid], delay_here)
                    arrivals.append([tid, t, eff_pr, delay_here, scheduled_dt])
                    break

        if len(arrivals) <= 1:
            continue

        # resolve conflicts using strict priority-first rule
        resolved = resolve_conflicts(arrivals, headway)

        # apply resolved times (only push forward as necessary)
        for tid, resolved_time, _, _, _ in resolved:
            idx = next((j for j, (st, _) in enumerate(final_schedules[tid]) if st == station), None)
            if idx is None:
                continue

            base_time = base_schedules[tid][idx][1]
            chosen_time = max(base_time, resolved_time)
            shift_minutes = minutes_between(final_schedules[tid][idx][1], chosen_time)
            if shift_minutes > 0:
                for j in range(idx, len(final_schedules[tid])):
                    st_j, t_j = final_schedules[tid][j]
                    final_schedules[tid][j] = (st_j, t_j + timedelta(minutes=shift_minutes))

    return base_schedules, final_schedules


# --------------------------
# Throughput calculation
# --------------------------

def compute_throughput(all_schedules: Dict[str, List[Tuple[str, datetime]]]):
    if not all_schedules:
        return 0.0, 0, 0.0

    num_trains = len(all_schedules)
    origin_times = [sched[0][1] for sched in all_schedules.values()]
    final_times = [sched[-1][1] for sched in all_schedules.values()]

    earliest_origin = min(origin_times)
    latest_final = max(final_times)

    total_minutes = minutes_between(earliest_origin, latest_final)
    if total_minutes <= 0:
        total_minutes = 1

    span_hours = total_minutes / 60.0
    throughput = num_trains / span_hours

    return throughput, num_trains, span_hours


# --------------------------
# Traffic Signal Simulation
# --------------------------

def simulate_signals_all(trains: Dict[str, Dict], final_schedules: Dict[str, List[Tuple[str, datetime]]]):
    print("\n🚦 Signal Simulation (origin stations)")
    print("=" * 60)
    order = sorted(trains.items(), key=lambda x: str_to_time(x[1]["schedule"][0][1]))
    for tid, tr in order:
        origin_station, orig_time_str = tr["schedule"][0]
        orig_time = str_to_time(orig_time_str)
        resched_time = final_schedules[tid][0][1]
        print(f"\nStation: {origin_station} — Train {tid} ({tr['name']})")
        if resched_time <= orig_time:
            print(f"⏱ {time_to_str(resched_time)} — 🟢 GREEN — Train {tid} departs on time/early")
            continue

        current = orig_time
        while current < resched_time:
            print(f"⏱ {time_to_str(current)} — 🔴 RED — Track not available, Train {tid} waiting")
            current += timedelta(minutes=5)
        print(f"⏱ {time_to_str(resched_time)} — 🟢 GREEN — Signal cleared → Train {tid} departs")


# --------------------------
# Reporting
# --------------------------

def print_corridor(trains: Dict[str, Dict], final_schedules: Dict[str, List[Tuple[str, datetime]]]):
    print("\n📊 Full Corridor Timetable (All Trains)")
    print("=" * 60)
    order = sorted(trains.items(), key=lambda x: str_to_time(x[1]["schedule"][0][1]))
    for tid, tr in order:
        print(f"\n{tr['name']} ({tid}) — Priority {tr['priority']}")
        orig_sched = tr['schedule']
        new_sched = final_schedules[tid]
        for (st_o, t_o), (st_n, t_n) in zip(orig_sched, new_sched):
            delay_here = minutes_between(str_to_time(t_o), t_n)
            print(f"   {st_n:10} ➝ {time_to_str(t_n)}   (Delay +{delay_here}m)")
    print("=" * 60)


# --------------------------
# Main
# --------------------------

def main():
    print("Available trains:")
    for tid, tr in trains.items():
        print(f"  {tid}: {tr['name']} (origin {tr['schedule'][0][1]})  — Priority {tr['priority']}")

    # Input delays
    delays: Dict[str, int] = {}
    while True:
        tid = input("\nEnter train number to delay (or ENTER/stop to finish): ").strip()
        if not tid or tid.lower() == "stop":
            break
        if tid not in trains:
            print("❌ Invalid train number")
            continue
        try:
            val = input(f"Enter delay in minutes for {tid} (0 for none): ").strip()
            delay_min = int(val) if val != "" else 0
        except ValueError:
            print("❌ Invalid integer for delay; please try again.")
            continue
        delays[tid] = delay_min

    try:
        headway = int(input("\nEnter headway in minutes (default 10): ").strip() or "10")
    except ValueError:
        headway = 10

    base_schedules, final_schedules = reschedule_all(trains, delays, headway)

    simulate_signals_all(trains, final_schedules)
    print_corridor(trains, final_schedules)

    base_tp, base_count, base_span = compute_throughput(base_schedules)
    final_tp, final_count, final_span = compute_throughput(final_schedules)

    print("\n🔢 Throughput Summary")
    print("=" * 60)
    print(f"Before scheduling: {base_count} trains over {base_span:.2f} hours → {base_tp:.2f} trains/hour")
    print(f" After scheduling: {final_count} trains over {final_span:.2f} hours → {final_tp:.2f} trains/hour")

    delta = final_tp - base_tp
    pct = (delta / base_tp * 100) if base_tp != 0 else float('inf')
    sign = "+" if delta >= 0 else ""
    print(f"Change in throughput: {sign}{delta:.2f} trains/hour ({sign}{pct:.1f}%)")
    print("=" * 60)


if __name__ == "__main__":
    main()
 