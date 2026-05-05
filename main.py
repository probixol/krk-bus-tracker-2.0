import csv
import os, requests, zipfile, io, json, datetime, sys
from google.transit import gtfs_realtime_pb2
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QApplication, QWidget, QGridLayout, QLabel
from PyQt6.QtGui import QFontDatabase, QFont

fail_count = 1
online_backup = []
backup = []
trip_map = {}
stops_id = []
now = datetime.datetime.strptime(datetime.datetime.now().strftime("%H:%M:%S"), "%H:%M:%S") # data z retardacja (1900-01-01)
today = datetime.datetime.now().strftime("%Y%m%d")
today_datetime = datetime.datetime.now()
print(f"[DEBUG] Data: {today}")
weekday = datetime.datetime.now().weekday()
print(f"[DEBUG] Weekday: {weekday}")

with open("config.txt", mode="r", encoding="utf-8") as config_file:
    stop_name = config_file.readline().strip()
    direction = config_file.readline().strip()
    kml = config_file.readline().strip()
    ilosc = int(config_file.readline().strip())
    force_update = int(config_file.readline().strip())

app = QApplication(sys.argv)
app.setOverrideCursor(Qt.CursorShape.BlankCursor)
window = QWidget()
window.setFixedSize(1920, 1080)
layout = QGridLayout()
window.setLayout(layout)
window.setStyleSheet("background-color: black;")

font_id = QFontDatabase.addApplicationFont("Helvetica-Bold.ttf")
custom_font = QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 91)

clock = QLabel("")
clock.setFont(custom_font)
clock.setStyleSheet("color: white;")
layout.addWidget(clock, 0, 0)

labels = []
for row in range(ilosc):
    row_labels = []
    for col in range(3):
        label = QLabel("")
        label.setFont(custom_font)
        layout.addWidget(label, row + 1, col)
        row_labels.append(label)
    labels.append(row_labels)
layout.setColumnStretch(1, 10)

skip = 0
if force_update == 0:
    try:
        with open('date.txt', 'r', encoding='utf-8') as f:
            date_config = f.readline().strip()
        if date_config == today:
            skip = 1
            print("[DEBUG] Aktualizacja GTFS byla juz dzis robiona, pomijam. . .")
    except FileNotFoundError:
        with open('date.txt', 'w', encoding='utf-8') as f:
            f.write(today)

if force_update == 1:
    skip = 0
    print("[DEBUG] Force GTFS update wlaczony!")

def gtfs_update():
    global gtfs_number, trip_map, skip
    trip_map = {}
    gtfs_links = open("gtfs_links.txt", "r")
    line = gtfs_links.readline()
    departures = []
    gtfs_number = 0
    count = 0
    stop_count = 0
    location_desc = {}
    os.makedirs("GTFS", exist_ok=True)
    while line:
        local_departures = {}
        gtfs_number = gtfs_number + 1
        if skip == 0:
            print("[DEBUG] Pobieranie GTFS: " + line.strip())
            try:
                request = requests.get(line.strip())
            except:
                print("[ERROR] Brak internetu: " + line.strip())
                print("[ERROR] Pomijam reszte. . .")
                return False
            print("[DEBUG] Zapisywanie GTFS: " + line.strip())
            with open("GTFS/" + str(gtfs_number) + ".zip", mode="wb") as file:
                file.write(request.content)
        with zipfile.ZipFile("GTFS/" + str(gtfs_number) + ".zip", 'r') as zip:
            with zip.open('stops.txt', 'r') as f:
                r_reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))
                for row in r_reader:
                    if row['stop_name'] == stop_name:
                        # tutaj definicja w przyszlosci co jednolici systemy
                        current_stop_id = row['stop_id']
                        if current_stop_id not in local_departures:
                            local_departures[current_stop_id] = []
                            stops_id.append(current_stop_id)
                        local_departures[current_stop_id] = {
                            "stop_id": current_stop_id,
                            "stop_name": row.get('stop_name', '???'),
                            "stop_desc": row.get('stop_desc', 'unknown'),
                            "stop_lat": row.get('stop_lat', '???'),
                            "stop_lon": row.get('stop_lon', '???'),
                            "departures": []
                        }
                        if local_departures[current_stop_id]["stop_desc"] != 'unknown':
                            location_desc.update({row['stop_desc']: (row['stop_lat'], row['stop_lon'])})
                        else:
                            possible_desc = {}
                            for desc in location_desc:
                                # wzor na odleglosc dwoch punktow
                                distance = ((float(location_desc[desc][0]) - float(row['stop_lat'])) ** 2 + (float(location_desc[desc][1]) - float(row['stop_lon'])) ** 2) ** 0.5
                                possible_desc.update({desc: distance})
                            local_departures[current_stop_id]['stop_desc'] = min(possible_desc, key=possible_desc.get)

            stops_set = set(stops_id)
            trips_set = set()
            routes_set = set()
            today_service = set()

            with zip.open('stop_times.txt', 'r') as f:
                r_reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))
                for row in r_reader:
                    count += 1
                    if count % 1000000 == 0:
                        print(f"[DEBUG] Przetworzono już {count} linii. . .")
                    if row['stop_id'] in stops_set:
                        local_departures[row['stop_id']]["departures"].append({
                            "trip_id": row.get('trip_id', '???'),
                            "time": row.get('departure_time', '???')
                        })
                        trips_set.add(row['trip_id'])
                stop_count += 1

            # data setup
            calendar_to_day = {}
            calendar_dates = True
            with zip.open('calendar.txt', 'r') as f:
                r_reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))
                for row in r_reader:
                    calendar = row['monday'] + row['tuesday'] + row['wednesday'] + row['thursday'] + row['friday'] + row['saturday'] + row['sunday']
                    calendar_to_day.setdefault(row['service_id'], []).append({
                        "0": row.get('monday', '0'),
                        "1": row.get('tuesday', '0'),
                        "2": row.get('wednesday', '0'),
                        "3": row.get('thursday', '0'),
                        "4": row.get('friday', '0'),
                        "5": row.get('saturday', '0'),
                        "6": row.get('sunday', '0'),
                        "start_date": row.get('start_date', '0'),
                        "end_date": row.get('end_date', '0')
                    })
                    if calendar != "0000000":
                        calendar_dates = False

            if calendar_dates == True:
                with zip.open('calendar_dates.txt', 'r') as f:
                    r_reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))
                    for row in r_reader:
                        if row['date'] == today:
                            today_service.add(row['service_id'])
                            print(f"[DEBUG] Dzisiejszy serwis: {today_service}")
            # translator
            route_to_short = {}
            with zip.open('routes.txt', 'r') as f:
                r_reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))
                for row in r_reader:
                    route_to_short[row['route_id']] = row['route_short_name']
            # mapowanie tripow do nazwy linii
            with zip.open('trips.txt', 'r') as f:
                r_reader = csv.DictReader(io.TextIOWrapper(f, encoding='utf-8-sig'))
                for row in r_reader:
                    count += 1
                    if count % 1000000 == 0:
                        print(f"[DEBUG] Przetworzono już {count} linii. . .")
                    if row['trip_id'] in trips_set:
                        current_calendar = calendar_to_day[row['service_id']][0]
                        day_value = current_calendar.get(str(weekday))
                        start_date = datetime.datetime.strptime(current_calendar.get('start_date'), "%Y%m%d")
                        end_date = datetime.datetime.strptime(current_calendar.get('end_date'), "%Y%m%d")

                        if day_value == '1' or row['service_id'] in today_service:
                            if start_date <= today_datetime and today_datetime <= end_date:
                                if row['route_id'] in route_to_short:
                                    short_route = route_to_short[row['route_id']]
                                headsign = row['trip_headsign']
                                if len(headsign) > 19: # skracanie i usuwanie kursow tymczasowych
                                    route_words = headsign.split()
                                    while len(" ".join(route_words)) > 19 or route_words[-1].endswith(":"):
                                        route_words.pop()
                                    headsign = " ".join(route_words)
                                trip_map[row['trip_id']] = {
                                    "headsign": headsign,
                                    "route_id": short_route,
                                    "service_id": row['service_id']
                                }
                                routes_set.add(row['route_id'])
                stop_count += 1

            for current_stop_id in list(local_departures):
                valid_local_departures = []
                for current_departure in local_departures[current_stop_id]["departures"]:
                    if current_departure["trip_id"] in trip_map:
                        current_departure["route_id"] = trip_map[current_departure["trip_id"]]["route_id"]
                        current_departure["headsign"] = trip_map[current_departure["trip_id"]]["headsign"]
                        # current_departure["service_id"] = trip_map[current_departure["trip_id"]]["service_id"]
                        valid_local_departures.append(current_departure)

                if len(valid_local_departures) > 0:
                    stop_data = local_departures[current_stop_id].copy()
                    stop_data["departures"] = valid_local_departures
                    departures.append(stop_data)

        line = gtfs_links.readline()

    try:
        with open('custom.json', 'r', encoding='utf-8') as f:
            custom_data = json.load(f)
        for stop_key in custom_data:
            custom_departures = []  # lista, poza petla departure
            for departure in custom_data[stop_key]:
                if weekday in departure["days"]:
                    custom_departures.append({
                        "trip_id": departure["line"],
                        "time": departure["time"],
                        "route_id": departure["line"],
                        "headsign": departure["dest"]
                    })
            departures.append({
                "stop_id": stop_key,
                "stop_name": "CUSTOM",
                "stop_desc": custom_data[stop_key][0]["direction"],
                "stop_lat": "0",
                "stop_lon": "0",
                "departures": custom_departures
            })
    except FileNotFoundError:
        print("[WARNING] Nie znaleziono custom.json")

    gtfs_links.close()

    with open('optimized.json', 'w', encoding='utf-8') as f:
        json.dump(departures, f, indent=4, ensure_ascii=False)
    print("[DEBUG] Dane zopytmalizowane i zapisane!")

def offline():
    print(f"[DEBUG] (ONLINE) stops_id: {stops_id}")
    print(f"[DEBUG] (ONLINE) trip_map size: {len(trip_map)}")
    global departures_now, backup
    departures_now = []
    with open('optimized.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        for stop in data:
            if stop["stop_desc"] == direction or direction == '00':
                for departure in stop["departures"]:
                    try:
                        tempdep = datetime.datetime.strptime(departure["time"], "%H:%M:%S")
                    except ValueError:
                        tempdep = datetime.datetime.strptime(departure["time"], "%H:%M")
                    if tempdep > datetime.datetime.now().replace(year=1900, month=1, day=1):
                        time_diff = tempdep - datetime.datetime.now().replace(year=1900, month=1, day=1)
                        minutes = int(time_diff.total_seconds() // 60)
                        minutes_str = f"{minutes} min" if minutes < 60 else departure["time"][:5]
                        departures_now.append((departure["route_id"], departure["headsign"], minutes_str, departure["time"], departure["trip_id"], 0))
                        departures_now = sorted(departures_now, key=lambda x: x[3])
                        backup = departures_now.copy()

def online():
    global departures_now, backup, online_backup, fail_count
    with open('live_links.txt', 'r', encoding='utf-8') as f:
        for URL in f:
            URL = URL.strip()
            try:
                response = requests.get(URL, timeout=15)
                if response.status_code != 200:
                    print(f"[WARNING] Zly status: {response.status_code}")
                    continue
                feed = gtfs_realtime_pb2.FeedMessage()
                feed.ParseFromString(response.content)
                for entity in feed.entity:
                    if entity.HasField("trip_update"):
                        trip_update = entity.trip_update
                        for stop_update in trip_update.stop_time_update:
                            if stop_update.stop_id in stops_id:
                                trip_id = entity.trip_update.trip.trip_id
                                if trip_id in trip_map:
                                    if stop_update.HasField("departure") and stop_update.departure.HasField("time"):
                                        unix_time = stop_update.departure.time
                                    elif stop_update.HasField("arrival") and stop_update.arrival.HasField("time"):
                                        unix_time = stop_update.arrival.time
                                    else:
                                        continue
                                    departure_dt_obj = datetime.datetime.fromtimestamp(unix_time)
                                    departure_dt = departure_dt_obj.strftime("%H:%M:%S")
                                    time_delta = departure_dt_obj - datetime.datetime.now()
                                    minutes = int(time_delta.total_seconds() // 60)
                                    minutes_str = f"{minutes} min" if minutes > 0 else "0 min"

                                    route = trip_map[trip_id]["route_id"]
                                    headsign = trip_map[trip_id]["headsign"]
                                    print(f"[DEBUG] Linia na żywo: {departure_dt}, {route}, {headsign}, {minutes_str}")

                                    new_departures = []
                                    for d in departures_now:
                                        if d[4] != trip_id:
                                            new_departures.append(d)
                                    departures_now = new_departures
                                    departures_now.append((route, headsign, minutes_str, departure_dt, trip_id, 1))
                                    departures_now = sorted(departures_now, key=lambda x: x[3])
                                    break # to tutaj jest dla wydajnosci podobno ale nie wiem na ile ufac claude wiec jak cos nie bedzie dzialalo to prosze usunac >:D
                fail_count = 0
                online_backup = departures_now.copy()
            except Exception as e:
                print(f"[WARNING] Slaba siec lub brawo Krakow: {e}")
                fail_count += 1
                if fail_count == 1 and online_backup is not None:
                    print("[INFO] Uzywam poprzednich danych online. . .")
                    departures_now = online_backup
                else:
                    print("[INFO] Uzywam danych offline. . .")
                    if backup is not None:
                        departures_now = backup
                    fail_count = 0

            # print(online_backup)
            # print(backup)

def display():
    print("[DEBUG] Display update!")
    clock.setText(datetime.datetime.now().strftime("%H:%M"))
    if len(departures_now) < ilosc:
        ilosc_temp = len(departures_now)
    else:
        ilosc_temp = ilosc
    for row in range(ilosc_temp):
        for col in range(3):
            if departures_now[row][5] == 1:
                labels[row][col].setStyleSheet("color: #32CD32;")
            else:
                labels[row][col].setStyleSheet("color: white;")
            labels[row][col].setText(f"{departures_now[row][col]}")

def midnight_check():
    global today, today_datetime, weekday, skip
    new_today = datetime.datetime.now().strftime("%Y%m%d")
    if new_today != today:
        print("[DEBUG] Nowy dzien, aktualizuje GTFS. . .")
        today = new_today
        today_datetime = datetime.datetime.now()
        weekday = datetime.datetime.now().weekday()
        skip = 0
        with open('date.txt', 'w', encoding='utf-8') as f:  # <- dodaj
            f.write(today)
        gtfs_update()

midnight_timer = QTimer()
midnight_timer.timeout.connect(midnight_check)
midnight_timer.start(600000) # 10 min

def update():
    offline()
    online()
    display()

gtfs_update()

timer = QTimer()
timer.timeout.connect(update)
timer.start(20000) # 20 sec

update()

window.setLayout(layout)
window.show()
app.exec()
