from flask import Flask, render_template, request
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

app = Flask(__name__)

# --------------------------
# Utility functions
# --------------------------
def str_to_time(s: str) -> datetime:
    return datetime.strptime(s, "%H:%M")

def time_to_str(t: datetime) -> str:
    return t.strftime("%H:%M")

def minutes_between(t1: datetime, t2: datetime) -> int:
    return int((t2 - t1).total_seconds() // 60)


# --------------------------
# Train data
# --------------------------
trains: Dict[str, Dict] = {
    "20871": {
        "name": "Vande Bharat Express",
        "priority": 1,
        "schedule": [("Howrah", "06:00"), ("Kharagpur", "07:40"), ("Tatanagar", "09:10")]
    },
    "12261": {
        "name": "Howrah–CSMT Duronto",
        "priority": 2,
        "schedule": [("Howrah", "05:45"), ("Kharagpur", "07:20"), ("Tatanagar", "08:48")]
    },
    "12813": {
        "name": "Steel Express",
        "priority": 4,
        "schedule": [("Howrah", "06:35"), ("Kharagpur", "07:55"), ("Tatanagar", "09:00")]
    },
    "12021": {
        "name": "Jan Shatabdi Express",
        "priority": 3,
        "schedule": [("Howrah", "06:15"), ("Kharagpur", "07:50"), ("Tatanagar", "09:47")]
    }
}

# --------------------------
# Core Functions (reuse from your script)
# --------------------------
def get_effective_priority(train: Dict, delay: int) -> int:
    return train["priority"]

def resolve_conflicts(arrivals: List[List], headway: int) -> List[List]:
    arrivals.sort(key=lambda x: x[1])
    i = 1
    while i < len(arrivals):
        prev_tid, prev_t, prev_pr, prev_delay, prev_sched = arrivals[i-1]
        curr_tid, curr_t, curr_pr, curr_delay, curr_sched = arrivals[i]
        gap = minutes_between(prev_t, curr_t)
        if gap < headway:
            if prev_pr < curr_pr:
                winner_idx, loser_idx = i-1, i
                winner_time = arrivals[winner_idx][1]
            elif curr_pr < prev_pr:
                winner_idx, loser_idx = i, i-1
                winner_time = arrivals[winner_idx][1]
            else:
                if prev_sched <= curr_sched:
                    winner_idx, loser_idx = i-1, i
                else:
                    winner_idx, loser_idx = i, i-1
                winner_time = arrivals[winner_idx][1]
            new_loser_time = winner_time + timedelta(minutes=headway)
            if new_loser_time > arrivals[loser_idx][1]:
                arrivals[loser_idx][1] = new_loser_time
                arrivals.sort(key=lambda x: x[1])
                i = 1
                continue
        i += 1
    return arrivals

def reschedule_all(trains: Dict[str, Dict], delays: Dict[str, int], headway: int):
    base_schedules: Dict[str, List[Tuple[str, datetime]]] = {}
    for tid, tr in trains.items():
        delay = delays.get(tid, 0)
        sched = [(station, str_to_time(tstr) + timedelta(minutes=delay)) for station, tstr in tr["schedule"]]
        base_schedules[tid] = sched
    final_schedules = {tid: list(sched) for tid, sched in base_schedules.items()}
    stations = sorted({st for tr in trains.values() for (st, _) in tr["schedule"]})
    for station in stations:
        arrivals = []
        for tid, sched in final_schedules.items():
            for st, t in sched:
                if st == station:
                    orig_time_str = next(ot for s, ot in trains[tid]["schedule"] if s == st)
                    scheduled_dt = str_to_time(orig_time_str)
                    delay_here = minutes_between(scheduled_dt, t)
                    eff_pr = get_effective_priority(trains[tid], delay_here)
                    arrivals.append([tid, t, eff_pr, delay_here, scheduled_dt])
                    break
        if len(arrivals) <= 1:
            continue
        resolved = resolve_conflicts(arrivals, headway)
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
# Web Routes
# --------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    delays = {}
    headway = 10
    final_schedules = None
    if request.method == "POST":
        for tid in trains.keys():
            val = request.form.get(f"delay_{tid}", "0")
            try:
                delays[tid] = int(val)
            except:
                delays[tid] = 0
        try:
            headway = int(request.form.get("headway", "10"))
        except:
            headway = 10
        _, final_schedules = reschedule_all(trains, delays, headway)
    return render_template("index.html", trains=trains, schedules=final_schedules, time_to_str=time_to_str)

if __name__ == "__main__":
    app.run(debug=True)