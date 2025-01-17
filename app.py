from flask import Flask, render_template, request
from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, risings_and_settings
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def planet_times():
    results = None
    selected_date = None

    # الحصول على التاريخ من المستخدم أو استخدام التاريخ الحالي
    selected_date = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))

    # تحويل التاريخ المدخل إلى كائن datetime
    selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d')

    # تحميل البيانات الفلكية
    eph = load('de421.bsp')  # ملف ephemeris
    ts = load.timescale()

    # قائمة الكواكب المدعومة
    planets = {
        "عطارد": eph["mercury"],
        "الزهرة": eph["venus"],
        "المريخ": eph["mars"],
        "المشتري": eph["jupiter barycenter"],
        "زحل": eph["saturn barycenter"],
        "أورانوس": eph["uranus barycenter"],
        "نبتون": eph["neptune barycenter"]
    }

    # تحديد الموقع الجغرافي (مسقط، سلطنة عمان)
    location = Topos('23.5880 N', '58.3829 E')

    # نطاق الوقت (اليوم المدخل)
    start_time = ts.utc(selected_date_obj.year, selected_date_obj.month, selected_date_obj.day)
    end_time = ts.utc(selected_date_obj.year, selected_date_obj.month, selected_date_obj.day + 1)

    # حساب الشروق والغروب لكل كوكب
    results = []
    for planet_name, planet in planets.items():
        times, events = find_discrete(
            start_time,
            end_time,
            risings_and_settings(eph, planet, location)
        )

        planet_events = []
        for t, event in zip(times, events):
            event_type = "شروق" if event == 1 else "غروب"
            # تحويل التوقيت إلى توقيت سلطنة عمان (UTC+4)
            local_time = t.utc_datetime() + timedelta(hours=4)
            planet_events.append({
                "event": event_type,
                "time_local": local_time.strftime('%Y-%m-%d %H:%M:%S')
            })
        results.append({"planet": planet_name, "events": planet_events})

    return render_template('index.html', results=results, selected_date=selected_date)

if __name__ == '__main__':
    app.run(debug=True)
