from flask import Flask, render_template, request
from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, risings_and_settings
from datetime import datetime
import pytz
import matplotlib.pyplot as plt
import numpy as np
import os
import arabic_reshaper
from bidi.algorithm import get_display
from matplotlib import rc

app = Flask(__name__)

# مجلد لحفظ خريطة السماء المولَّدة
IMAGE_FOLDER = "static/images"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

def reshape_text(text):
    """إعادة تشكيل النص العربي حتى يُعرض بشكل صحيح في matplotlib."""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

# قاموس المدن في عُمان (يمكنك تعديلها كما تريد)
LOCATIONS = {
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

# قاموس يربط اسم الجُرم السماوي بمسار الصورة
PLANET_IMAGES = {
    "الشمس":    "static/planetimg/sun.png",
    "القمر":    "static/planetimg/moon.png",
    "عطارد":   "static/planetimg/mercury.png",
    "الزهرة":  "static/planetimg/venus.png",
    "المريخ":  "static/planetimg/mars.png",
    "المشتري": "static/planetimg/jupiter.png",
    "زحل":     "static/planetimg/saturn.png",
    "أورانوس": "static/planetimg/uranus.png",
    "نبتون":   "static/planetimg/neptune.png"
}

# لضبط الخط العربي في الرسومات
rc('font', family='DejaVu Sans')

@app.route('/')
def planet_times():
    """
    منطق التطبيق:
    - عند الزيارة الأولى (عدم إرسال lat, lon, location) يتم عرض الصفحة لتحديد الموقع عبر geolocation.
    - عند قبول المستخدم أو اختيار مدينة محددة يتم حساب بيانات الشروق والغروب للأجرام السماوية،
      وحساب ارتفاع وزاوية كل جرم، بالإضافة إلى حساب إضاءة وطور القمر بدقة عالية باستخدام Skyfield.
    """
    # قراءة بارامترات GET
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    selected_location = request.args.get('location')

    # إذا لم يتم تحديد الموقع، نمرر قيم افتراضية لقاموس معلومات القمر
    if not lat and not lon and not selected_location:
        default_moon_info = {
            "illumination": 0,
            "phase_angle": 0,
            "phase_angle_degrees": 0,
            "phase_description": "غير معروف"
        }
        return render_template(
            'index.html',
            lat='',
            lon='',
            selected_location='',
            selected_date='',
            selected_time='',
            results=[],
            visible_planets=[],
            image_path='',
            planet_images=PLANET_IMAGES,
            moon_info=default_moon_info
        )

    # تحديد الموقع
    if lat and lon and selected_location == "موقعي الحالي":
        # استخدام إحداثيات الجهاز
        latitude = f"{lat} N"
        longitude = f"{lon} E"
    elif selected_location in LOCATIONS:
        latitude, longitude = LOCATIONS[selected_location]
    else:
        latitude, longitude = LOCATIONS["مسقط"]
        selected_location = "مسقط"

    # إعداد المنطقة الزمنية
    oman_tz = pytz.timezone('Asia/Muscat')
    utc_tz = pytz.UTC
    now_oman = datetime.now(oman_tz)
    selected_date = request.args.get('date', now_oman.strftime('%Y-%m-%d'))
    selected_time = request.args.get('time', now_oman.strftime('%H:%M'))

    try:
        date_obj = datetime.strptime(selected_date, '%Y-%m-%d')
        time_obj = datetime.strptime(selected_time, '%H:%M').time()
        local_datetime = datetime.combine(date_obj, time_obj)
        local_datetime = oman_tz.localize(local_datetime)
    except ValueError:
        return "تنسيق التاريخ أو الوقت غير صحيح!", 400

    # تحويل الوقت إلى UTC
    utc_datetime = local_datetime.astimezone(utc_tz)

    # تحميل بيانات Skyfield بدقة عالية: محاولة استخدام de430 إذا كانت متوفرة
    try:
        eph = load('de430.bsp')
    except Exception:
        eph = load('de421.bsp')
    ts = load.timescale()

    # تعريف الكواكب (الشمس، القمر، والكواكب الأخرى)
    planets = {
        "الشمس": eph["sun"],
        "القمر": eph["moon"],
        "عطارد": eph["mercury"],
        "الزهرة": eph["venus"],
        "المريخ": eph["mars"],
        "المشتري": eph["jupiter barycenter"],
        "زحل": eph["saturn barycenter"],
        "أورانوس": eph["uranus barycenter"],
        "نبتون": eph["neptune barycenter"]
    }

    # تهيئة الموقع باستخدام Topos
    location = Topos(latitude, longitude)

    from_date = ts.utc(date_obj.year, date_obj.month, date_obj.day)
    to_date = ts.utc(date_obj.year, date_obj.month, date_obj.day + 1)

    # حساب بيانات الشروق والغروب والارتفاع والسمت لكل جرم
    results = []
    for name, planet in planets.items():
        times, events = find_discrete(
            from_date, to_date,
            risings_and_settings(eph, planet, location)
        )

        planet_events = []
        for t_val, e_val in zip(times, events):
            event_type = "شروق" if e_val == 1 else "غروب"
            local_ev_time = t_val.utc_datetime().replace(tzinfo=utc_tz).astimezone(oman_tz)
            hour_format = local_ev_time.strftime('%I:%M')
            period = "ص" if local_ev_time.hour < 12 else "م"
            planet_events.append(f"{event_type}: {hour_format} {period}")

        # حساب الارتفاع والسمت في اللحظة المحددة
        observer = eph['earth'] + location
        astro = observer.at(ts.from_datetime(utc_datetime)).observe(planet)
        alt, azm, _ = astro.apparent().altaz()

        results.append({
            "planet": name,
            "events": planet_events,
            "current_alt": round(alt.degrees, 2),
            "current_azm": round(azm.degrees, 2),
        })

    # حساب إضاءة وطور القمر بدقة عالية باستخدام Skyfield
    t_sky = ts.from_datetime(utc_datetime)
    moon_obj = eph["moon"]
    sun_obj  = eph["sun"]
    earth_obj = eph["earth"]

    moon_pos = moon_obj.at(t_sky).position.au
    sun_pos = sun_obj.at(t_sky).position.au
    earth_pos = earth_obj.at(t_sky).position.au

    vector_moon_sun = sun_pos - moon_pos
    vector_moon_earth = earth_pos - moon_pos

    dot = np.dot(vector_moon_sun, vector_moon_earth)
    norm_ms = np.linalg.norm(vector_moon_sun)
    norm_me = np.linalg.norm(vector_moon_earth)
    cos_phase = np.clip(dot / (norm_ms * norm_me), -1.0, 1.0)
    phase_angle = np.arccos(cos_phase)  # بوحدة الراديان
    illumination = (1 + np.cos(phase_angle)) / 2
    phase_angle_degrees = np.degrees(phase_angle)

    def classify_moon_phase(angle_deg):
        if angle_deg < 10:
            return "بدر"
        elif angle_deg < 45:
            return "هلال متزايد"
        elif angle_deg < 55:
            return "تربيع أول"
        elif angle_deg < 85:
            return "أحدب متزايد"
        elif angle_deg < 95:
            return "بدر"
        elif angle_deg < 125:
            return "أحدب متناقص"
        elif angle_deg < 135:
            return "تربيع أخير"
        elif angle_deg < 170:
            return "هلال متناقص"
        else:
            return "محاق"

    phase_description = classify_moon_phase(phase_angle_degrees)
    moon_info = {
        "illumination": round(illumination, 4),  # دقة عالية (4 منازل عشرية)
        "phase_angle": round(phase_angle, 4),
        "phase_angle_degrees": round(phase_angle_degrees, 2),
        "phase_description": phase_description
    }

   


    # تعريف ألوان الكواكب الخاصة
    planet_colors = {
        "الشمس":    "#FDB813",  # لون برتقالي-أصفر
        "القمر":    "#CCCCCC",  # رمادي فاتح
        "عطارد":   "#B1B1B1",  # رمادي
        "الزهرة":  "#F7D358",  # أصفر فاتح
        "المريخ":  "#FF4500",  # أحمر برتقالي
        "المشتري": "#FFA500",  # برتقالي
        "زحل":     "#D2B48C",  # تان
        "أورانوس": "#7FFFD4",  # أكوامارين
        "نبتون":   "#4169E1"   # أزرق ملكي
    }

    # رسم خريطة السماء
    fig, ax = plt.subplots(figsize=(8, 8))

    # تعيين خلفية الشكل والمحاور
    fig.patch.set_facecolor('#0c0842')
    ax.set_facecolor('#0c0842')

    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.1, 1.1)

    # رسم دائرة السماء
    circle = plt.Circle((0, 0), 1, color='lightblue', fill=True, alpha=0.5)
    ax.add_artist(circle)

    # رسم الاتجاهات (شمال، شرق، جنوب، غرب) باللون الأبيض
    directions = ['شمال', 'شرق', 'جنوب', 'غرب']
    angles = [0, 90, 180, 270]
    for dir_label, angle in zip(directions, angles):
        reshaped_label = reshape_text(dir_label)
        x = np.cos(np.radians(angle))
        y = np.sin(np.radians(angle))
        ax.text(x * 1.2, y * 1.2, reshaped_label,
                ha='center', va='center', fontsize=12, fontweight='bold', color='white')

    # رسم تسميات الزوايا (0°، 30°، ... إلخ) باللون الأبيض
    for angle in range(0, 360, 30):
        x = np.cos(np.radians(angle)) * 1.05
        y = np.sin(np.radians(angle)) * 1.05
        ax.text(x, y, f"{angle}°", ha='center', va='center', fontsize=8, color='white')

    # رسم الكواكب التي تكون فوق الأفق
    for r in results:
        if r["current_alt"] > 0:
            azm = r["current_azm"]
            alt = r["current_alt"]
            planet_name = reshape_text(r["planet"])
            # حساب الموقع
            x = np.cos(np.radians(azm)) * (1 - alt / 90)
            y = np.sin(np.radians(azm)) * (1 - alt / 90)
            # الحصول على لون الكوكب من القاموس، وإذا لم يوجد يتم استخدام الأبيض كافتراضي
            planet_color = planet_colors.get(r["planet"], "white")
            ax.plot(x, y, 'o', color=planet_color, markersize=5)
            ax.text(x, y + 0.05, planet_name, ha='left', va='center', fontsize=8, color='white')

    ax.set_aspect('equal')
    ax.axis('off')

    # تنظيف الصور القديمة في مجلد IMAGE_FOLDER
    for file in os.listdir(IMAGE_FOLDER):
        file_path = os.path.join(IMAGE_FOLDER, file)
        if os.path.isfile(file_path) and file.endswith('.png'):
            os.remove(file_path)

    # حفظ الصورة
    image_path = os.path.join(IMAGE_FOLDER, "sky_map.png")
    plt.savefig(image_path, bbox_inches='tight', dpi=150)
    plt.close()




    # إعادة القالب مع تمرير جميع النتائج، بما في ذلك معلومات القمر بدقة عالية
    return render_template(
        'index.html',
        lat=lat,
        lon=lon,
        selected_location=selected_location,
        selected_date=selected_date,
        selected_time=selected_time,
        results=results,
        image_path=image_path,
        planet_images=PLANET_IMAGES,
        moon_info=moon_info
    )

if __name__ == '__main__':
    app.run(debug=True)
