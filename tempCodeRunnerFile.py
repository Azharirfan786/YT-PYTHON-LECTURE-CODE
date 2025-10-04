from datetime import datetime, timedelta

# --------------------------
# Utility functions
# --------------------------

def str_to_time(s: str):
    """Convert HH:MM string into datetime (dummy date)."""
    return datetime.strptime(s, "%H:%M")

def time_to_str(t: datetime):
    """Format datetime back to HH:MM."""
    return t.strftime("%H:%M")

def minutes_between(t1, t2):
    """Return difference in minutes (t2 - t1)."""
    return int((t2 - t1).total_seconds() // 60)


# --------------------------
# Train data
# --------------------------

trains = {
    "20871": {
        "name": "Vande Bharat Express",
        "priority": 1,  # Highest priority
        "schedule": [("Howrah", "06:00"),
                     ("Kharagpur", "07:40"),
                     ("Tatanagar", "09:10")]
    },
    "12261": {
        "name": "Howrah–CSMT Duronto",
        "priority": 4,
        "schedule": [("Howrah", "05:45"),
                     ("Kharagpur", "07:20"),
                     ("Tatanagar", "08:48")]
    },
    "12813": {
        "name": "Steel Express",
        "priority": 3,
        "schedule": [("Howrah", "17:20"),
                     ("Kharagpur", "19:00"),
                     ("Tatanagar", "21:25")]
    },
    "12021": {
        "name": "Jan Shatabdi Express",
        "priority": 2,
        "schedule": [("Howrah", "06:20"),
                     ("Kharagpur", "07:55"),
                     ("Tatanagar", "09:52")]
    }
}


# --------------------------
# Core scheduling logic
# --------------------------

def reschedule(train_id, delay_min, headway, trains):
    """Reschedule a single train with delay and enforce headway."""
    train = trains[train_id]
    new_schedule = []
    total_delay = delay_min

    # Reschedule each station based on delay
    for idx, (station, time_str) in enumerate(train["schedule"]):
        orig_time = str_to_time(time_str)
        new_time = orig_time + timedelta(minutes=total_delay)

        # enforce headway: check against all other trains at this station
        for tid, other in trains.items():
            if tid == train_id:
                continue
            for st, ot_str in other["schedule"]:
                if st == station:
                    ot = str_to_time(ot_str)
                    if new_time >= ot and minutes_between(ot, new_time) < headway:
                        # push forward
                        diff = headway - minutes_between(ot, new_time)
                        new_time += timedelta(minutes=diff)
                        total_delay += diff

        new_schedule.append((station, new_time))

    return new_schedule


# --------------------------
# Reporting
# --------------------------

def print_report(train_id, delay_min, headway, trains, new_schedule):
    train = trains[train_id]
    name, priority = train["name"], train["priority"]

    print("\n📌 Train Rescheduling Report")
    print("="*60)
    print(f"\n🚆 {name} ({train_id}) — Priority {priority}", end=" ")
    if priority == 1:
        print("(High)")
    elif priority == 2:
        print("(Medium)")
    elif priority == 3:
        print("(Normal)")
    else:
        print("(Low)")

    print("-"*60)
    print("Original Timetable:")
    for st, t in train["schedule"]:
        print(f"   {st:10} ➝ {t}")
    orig_dur = minutes_between(str_to_time(train["schedule"][0][1]),
                               str_to_time(train["schedule"][-1][1]))
    print(f"   Total journey: {orig_dur//60}h {orig_dur%60}m")

    print("\nRescheduled Timetable (Delay at origin: {} min):".format(delay_min))
    for (st, ot_str), (_, nt) in zip(train["schedule"], new_schedule):
        delay_here = minutes_between(str_to_time(ot_str), nt)
        print(f"   {st:10} ➝ {time_to_str(nt)}   (Delay +{delay_here}m)")
    new_dur = minutes_between(new_schedule[0][1], new_schedule[-1][1])
    print(f"   Total journey: {new_dur//60}h {new_dur%60}m")
    print(f"   ➝ Net change in journey time: {new_dur - orig_dur} minutes")

    print("\n📝 Notes:")
    print(f"- Headway enforced: {headway} minutes")
    if delay_min == 0:
        print("- Train ran on time, no reschedule required")
    else:
        print("- Delay applied from origin, propagated consistently")


def print_corridor(trains, all_new_schedules):
    print("\n📊 Full Corridor Timetable (All Trains)")
    print("="*60)
    # Sort trains by origin departure
    order = sorted(trains.items(), key=lambda x: str_to_time(x[1]["schedule"][0][1]))
    for tid, tr in order:
        print(f"\n{tr['name']} ({tid}) — Priority {tr['priority']}")
        for (st, t) in all_new_schedules.get(tid, tr["schedule"]):
            t_str = t if isinstance(t, str) else time_to_str(t)
            print(f"   {st:10} ➝ {t_str}")


# --------------------------
# Main program
# --------------------------

def main():
    print("Available trains:")
    for tid, tr in trains.items():
        print(f"  {tid}: {tr['name']} (origin {tr['schedule'][0][1]})  — Priority {tr['priority']}")

    train_id = input("\nEnter train number to delay: ").strip()
    if train_id not in trains:
        print("❌ Invalid train number")
        return

    delay_min = int(input("Enter delay in minutes: ").strip() or "0")
    headway = int(input("Enter headway in minutes (default 5): ").strip() or "5")

    new_schedule = reschedule(train_id, delay_min, headway, trains)
    all_new_schedules = {train_id: new_schedule}

    print_report(train_id, delay_min, headway, trains, new_schedule)
    print_corridor(trains, all_new_schedules)


if __name__ == "__main__":
    main()