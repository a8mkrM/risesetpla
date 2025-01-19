from flask import Flask, render_template, request
from skyfield.api import load, Topos, utc
from skyfield.almanac import find_discrete, risings_and_settings
from datetime import datetime, timedelta
import pytz
import matplotlib.pyplot as plt
import numpy as np
import os
import arabic_reshaper
from bidi.algorithm import get_display
from matplotlib import rc

# إعداد الخط لدعم اللغة العربية
rc('font', family='DejaVu Sans')

# إعداد Flask
app = Flask(__name__)
IMAGE_FOLDER = "static/images"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

def reshape_text(text):
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

@app.route('/', methods=['GET', 'POST'])
def planet_times():
    # إعداد توقيت مسقط (UTC+4)
    oman_tz = pytz.timezone('Asia/Muscat')
    utc_tz = pytz.UTC
    oman_time = datetime.now(oman_tz)

    # الحصول على التاريخ والوقت من المستخدم
    selected_date = request.args.get('date', oman_time.strftime('%Y-%m-%d'))
    selected_time = request.args.get('time', oman_time.strftime('%H:%M'))

    try:
        # تحويل الإدخال إلى datetime
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
        selected_time_obj = datetime.strptime(selected_time, '%H:%M').time()
        local_datetime = datetime.combine(selected_date_obj, selected_time_obj)
        local_datetime = oman_tz.localize(local_datetime)
    except ValueError:
        return "تنسيق التاريخ أو الوقت غير صحيح. الرجاء إدخال القيم بتنسيقات صحيحة.", 400

    # تحويل الوقت إلى UTC
    utc_datetime = local_datetime.astimezone(utc_tz)

    # تحميل البيانات الفلكية
    eph = load('de421.bsp')
    ts = load.timescale()

    # قائمة الكواكب
    planets = {
        "عطارد": eph["mercury"],
        "الزهرة": eph["venus"],
        "المريخ": eph["mars"],
        "المشتري": eph["jupiter barycenter"],
        "زحل": eph["saturn barycenter"],
        "أورانوس": eph["uranus barycenter"],
        "نبتون": eph["neptune barycenter"]
    }

    # تحديد الموقع الجغرافي
    # قائمة المواقع والإحداثيات
    locations = {
        "مسقط": ("23.5880 N", "58.3829 E"),
        "صحار": ("24.3429 N", "56.7290 E"),
        "الرستاق": ("23.3909 N", "57.4244 E"),
        "خصب": ("26.1766 N", "56.2406 E"),
        "البريمي": ("24.2500 N", "55.7500 E"),
        "نزوى": ("22.9333 N", "57.5333 E"),
        "ابراء": ("22.6908 N", "58.5339 E"),
        "صور": ("22.5667 N", "59.5289 E"),
        "هيماء": ("19.9500 N", "56.3167 E"),
        "صلالة": ("17.0190 N", "54.0897 E"),
    }

    # الحصول على الموقع من المستخدم
    selected_location = request.args.get('location', 'مسقط')
    latitude, longitude = locations.get(selected_location, locations["مسقط"])
    location = Topos(latitude, longitude)

    # نطاق الوقت (اليوم المدخل)
    start_time = ts.utc(selected_date_obj.year, selected_date_obj.month, selected_date_obj.day)
    end_time = ts.utc(selected_date_obj.year, selected_date_obj.month, selected_date_obj.day + 1)

    results = []

    for name, planet in planets.items():
        # حساب الشروق والغروب
        times, events = find_discrete(
            start_time, end_time, risings_and_settings(eph, planet, location)
        )
        planet_events = []
        for t, event in zip(times, events):
            event_type = "شروق" if event == 1 else "غروب"
            local_time = t.utc_datetime().replace(tzinfo=utc_tz).astimezone(oman_tz)
            hour_format = local_time.strftime('%I:%M')
            period = "ص" if local_time.hour < 12 else "م"
            planet_events.append(f"{event_type}: {hour_format} {period}")

        # حساب الموقع الحالي
        observer = eph['earth'] + location
        astrometric = observer.at(ts.from_datetime(utc_datetime)).observe(planet)
        alt, azm, _ = astrometric.apparent().altaz()

        results.append({
            "planet": name,
            "events": planet_events,
            "current_alt": round(alt.degrees, 2),
            "current_azm": round(azm.degrees, 2)
        })

    # رسم القبة السماوية
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.1, 1.1)
    circle = plt.Circle((0, 0), 1, color='lightblue', fill=True, alpha=0.5)
    ax.add_artist(circle)

    # الاتجاهات الأساسية
    directions = ['شمال', 'شرق', 'جنوب', 'غرب']
    angles = [0, 90, 180, 270]
    for dir_label, angle in zip(directions, angles):
        reshaped_label = reshape_text(dir_label)  # إعادة تشكيل النص
        x = np.cos(np.radians(angle))
        y = np.sin(np.radians(angle))
        ax.text(x * 1.2, y * 1.2, reshaped_label, ha='center', va='center', fontsize=12, fontweight='bold')

    # إضافة زوايا السمت حول الدائرة
    for angle in range(0, 360, 30):  # الزوايا من 0 إلى 360 بفاصل 30 درجة
        x = np.cos(np.radians(angle)) * 1.05  # الموضع الأفقي للنص
        y = np.sin(np.radians(angle)) * 1.05  # الموضع العمودي للنص
        ax.text(x, y, f"{angle}°", ha='center', va='center', fontsize=8, color='black')
    # قائمة الكواكب فوق الأفق
    visible_planets = [result["planet"] for result in results if result["current_alt"] > 0]

    # الكواكب الظاهرة
    for result in results:
        if result["current_alt"] > 0:
            azm = result["current_azm"]
            alt = result["current_alt"]
            planet_name = reshape_text(result["planet"])  # إعادة تشكيل اسم الكوكب
            x = np.cos(np.radians(azm)) * (1 - alt / 90)
            y = np.sin(np.radians(azm)) * (1 - alt / 90)
            
            # رسم دائرة صغيرة للموقع
            ax.plot(x, y, 'o', color='darkblue', markersize=5)
            
            # إضافة اسم الكوكب بجانب الدائرة
            ax.text(x , y+ 0.05, planet_name, ha='left', va='center', fontsize=8, color='black')

    ax.set_aspect('equal')
    ax.axis('off')
  # تنظيف الصور القديمة قبل حفظ الصورة الجديدة
    for file in os.listdir(IMAGE_FOLDER):
        file_path = os.path.join(IMAGE_FOLDER, file)
        if os.path.isfile(file_path) and file.endswith('.png'):
            os.remove(file_path)

    # حفظ الرسم
    image_path = os.path.join(IMAGE_FOLDER, "sky_map.png")
    plt.savefig(image_path, bbox_inches='tight', dpi=150)
    plt.close()

   


    return render_template(
        'index.html',
        results=results,
        selected_date=selected_date,
        selected_time=selected_time,
        selected_location=selected_location,  # تمرير الموقع المختار
        image_path=image_path,
        visible_planets=visible_planets  # تمرير الكواكب المرئية

    )

if __name__ == '__main__':
    app.run(debug=True)
