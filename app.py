from flask import Flask, render_template, request
from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, risings_and_settings
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def planet_times():
    results = None
    selected_date = None

    # تحديد التوقيت المحلي لعمان (UTC+4)
    oman_time = datetime.utcnow() + timedelta(hours=4)

    # الحصول على التاريخ من المستخدم أو استخدام التاريخ الحالي لتوقيت عمان
    selected_date = request.args.get('date', oman_time.strftime('%Y-%m-%d'))

    try:
        # تحويل التاريخ المدخل إلى كائن datetime
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
    except ValueError:
        # إذا كان التاريخ غير صحيح، قم بإرجاع رسالة خطأ
        return "تنسيق التاريخ غير صحيح. الرجاء إدخال التاريخ بتنسيق YYYY-MM-DD.", 400

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
            
            # تعديل التنسيق لإظهار ص/م
            hour_format = local_time.strftime('%I:%M')
            period = "ص" if local_time.hour < 12 else "م"

            planet_events.append({
                "event": event_type,
                "time_local": f"{hour_format} {period}"  # صيغة الوقت الجديدة
            })
        results.append({"planet": planet_name, "events": planet_events})

    # إعادة النتائج مع التاريخ المختار إلى صفحة HTML
    return render_template('index.html', results=results, selected_date=selected_date)

if __name__ == '__main__':
    app.run(debug=True)
