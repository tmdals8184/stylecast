from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import base64
import json
from werkzeug.security import generate_password_hash, check_password_hash

from selenium import webdriver as wb
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import requests
from datetime import datetime
import boto3
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'

USERS_FILE = 'users.json'
MEMO_FILE = 'memos.json'

def detect_faces(photo_path):
    client = boto3.client('rekognition')

    with open(photo_path, "rb") as image:
        response = client.detect_faces(Image={'Bytes': image.read()}, Attributes=['ALL'])

    emotion_colors = "pastel yellow"  # default

    for faceDetail in response['FaceDetails']:
        emotion = faceDetail["Emotions"][0]["Type"]
        positive_colors = ["mint", "pink", "light yellow"]
        negative_colors = ["light beige", "cream", "pastel yellow"]
        anxious_colors = ["sky blue", "soft white", "lavender"]
        intense_colors = ["blue gray", "toned-down red", "coral"]
        gender = faceDetail["Gender"]["Value"]
        if emotion in ["HAPPY", "CALM"]:
            emotion_colors = random.choice(positive_colors)
        elif emotion in ["SAD", "DISGUSTED"]:
            emotion_colors = random.choice(negative_colors)
        elif emotion in ["FEAR", "CONFUSED"]:
            emotion_colors = random.choice(anxious_colors)
        else:
            emotion_colors = random.choice(intense_colors)
    
    return emotion_colors, gender

def get_weather_and_season():
    API_KEY_W = "6b0189c97b93e4ac2c994c084954eb3a"
    city_name = "seoul"
    url_current_weather = f"https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={API_KEY_W}&units=metric"

    response = requests.get(url_current_weather)
    result = response.json()
    weather = result["weather"][0]["main"]

    month = datetime.now().month
    if month in [12, 1, 2]:
        season = "winter"
    elif month in [3, 4, 5]:
        season = "spring"
    elif month in [6, 7, 8]:
        season = "summer"
    else:
        season = "fall"

    return weather, season

def crawl_pinterest(search_text, keyword_folder):
    options = wb.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    driver = wb.Chrome(options=options)

    driver.get("https://www.pinterest.com/login/")
    time.sleep(5)

    wait = WebDriverWait(driver, 5)
    login_id = wait.until(EC.presence_of_element_located((By.ID, "email")))
    login_id.send_keys("tmdals0721@nate.com")

    login_pw = driver.find_element(By.ID, "password")
    login_pw.send_keys("asdf0606")

    login_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
    login_btn.click()
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(5)

    search_box = wait.until(EC.presence_of_element_located((By.NAME, "searchBoxInput")))
    search_box.send_keys(search_text)
    search_box.send_keys(Keys.ENTER)
    time.sleep(5)

    if not os.path.exists(keyword_folder):
        os.makedirs(keyword_folder)

    img_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img.hCL.kVc.L4E.MIw")))
    img_elements = img_elements[:9]
    img_urls = [img.get_attribute("src") for img in img_elements]

    for idx, img_url in enumerate(img_urls, start=1):
        try:
            response = requests.get(img_url)
            img_data = response.content
            img_path = os.path.join(keyword_folder, f"{os.path.basename(keyword_folder)}_{idx}.jpg")
            with open(img_path, "wb") as file:
                file.write(img_data)
            time.sleep(1)
        except Exception as e:
            print(f"{idx}번째 이미지 저장 실패: {e}")
            time.sleep(1)

    driver.quit()

def save_memo_to_file(date, memo):
    if os.path.exists(MEMO_FILE):
        with open(MEMO_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {}

    data[date] = memo

    with open(MEMO_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_memo_from_file(date):
    if os.path.exists(MEMO_FILE):
        with open(MEMO_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get(date, '')
    return ''


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        users = {'admin': generate_password_hash('1234')}
        save_users(users)
        return users

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    month = datetime.now().month
    if month in [3, 4, 5]:
        season = 'spring'
    elif month in [6, 7, 8]:
        season = 'summer'
    elif month in [9, 10, 11]:
        season = 'fall'
    else:
        season = 'winter'

    return render_template('project.html',
                           username=session['user_id'],
                           season=season)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and check_password_hash(users[username], password):
            session['user_id'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='아이디 또는 비밀번호가 틀렸습니다.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users:
            return render_template('register.html', error='이미 존재하는 아이디입니다.')
        users[username] = generate_password_hash(password)
        save_users(users)
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'user_id' not in session:
        return jsonify({'status': 'fail', 'message': '로그인 필요'})
    user_id = session['user_id']

    if 'file' not in request.files:
        return jsonify({'status': 'fail', 'message': '파일이 없습니다.'})
    
    file = request.files['file']
    date = request.form.get('date')
    photo_type = request.form.get('photo_type', 'face')

    if not date:
        return jsonify({'status': 'fail', 'message': '날짜가 없습니다.'})

    save_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id, date, photo_type)
    os.makedirs(save_folder, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    filename = f"{timestamp}_{file.filename}"
    filepath = os.path.join(save_folder, filename)
    file.save(filepath)

    analysis_data = None

    if photo_type == 'face':
        emotion_colors, gender = detect_faces(filepath)
        weather, season = get_weather_and_season()
        search_text = f"{season} {emotion_colors} outfit for {weather} street style {gender}"
        keyword_folder = os.path.join("pinterest_results", f"{user_id}_{date}")
        os.makedirs(keyword_folder, exist_ok=True)
        
        if not os.listdir(keyword_folder):
            crawl_pinterest(search_text, keyword_folder)

        analysis_data = {
            'emotion_colors': emotion_colors,
            'weather': weather,
            'season': season,
            'search_text': search_text,
            'pinterest_folder': keyword_folder
        }

    photos_grouped = {
        'face': [],
        'real': [],
        'pinterest': []
    }

    # face, real 사진 불러오기
    for category in ['face', 'real']:
        folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id, date, category)
        if os.path.exists(folder):
            for fname in os.listdir(folder):
                fpath = os.path.join(folder, fname)
                if os.path.isfile(fpath):
                    with open(fpath, 'rb') as f:
                        encoded = base64.b64encode(f.read()).decode('utf-8')
                    photos_grouped[category].append({
                        'filename': fname,
                        'data': f'data:image/jpeg;base64,{encoded}',
                        'photo_type': category
                    })

    # pinterest 사진은 별도 경로에서 불러오기
    pinterest_folder = os.path.join("pinterest_results", f"{user_id}_{date}")
    if os.path.exists(pinterest_folder):
        files = sorted(os.listdir(pinterest_folder))
        for fname in files:
            fpath = os.path.join(pinterest_folder, fname)
            if os.path.isfile(fpath):
                with open(fpath, 'rb') as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')
                photos_grouped['pinterest'].append({
                    'filename': fname,
                    'data': f'data:image/jpeg;base64,{encoded}',
                    'photo_type': 'pinterest'
                })

    max_recommendation = 2
    recommendation_left = max_recommendation
    return render_template('photos.html',
                           date=date,
                           photos_grouped=photos_grouped,
                           username=user_id,    
                           analysis=analysis_data,
                           recommendation_left=recommendation_left,
                           crawl_photos_count=sum(len(lst) for lst in photos_grouped.values()))



@app.route('/delete_photo', methods=['POST'])
def delete_photo():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']

    date = request.form.get('date')
    filename = request.form.get('filename')
    photo_type = request.form.get('photo_type', 'face')
    
    if not date or not filename:
        return redirect(url_for('index'))

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], user_id, date, photo_type, filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        os.remove(file_path)

    return redirect(url_for('photos_page', date=date))

@app.route('/save_memo', methods=['POST'])
def save_memo():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    date = request.form['date']
    memo = request.form['memo']
    save_memo_to_file(date, memo)
    return redirect(url_for('photos_page', date=date))

@app.route('/photos_page/<date>')
def photos_page(date):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']

    photos_grouped = {
        'face': [],
        'real': [],
        'pinterest': []
    }
    for category in ['face', 'real']:
        folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id, date, category)
        if os.path.exists(folder):
            for fname in os.listdir(folder):
                fpath = os.path.join(folder, fname)
                if os.path.isfile(fpath):
                    with open(fpath, 'rb') as f:
                        encoded = base64.b64encode(f.read()).decode('utf-8')
                    photos_grouped[category].append({
                        'filename': fname,
                        'data': f"data:image/jpeg;base64,{encoded}",
                        'photo_type': category
                    })

    pinterest_folder = os.path.join("pinterest_results", f"{user_id}_{date}")
    if os.path.exists(pinterest_folder):
        files = sorted(os.listdir(pinterest_folder))
        for fname in files:
            fpath = os.path.join(pinterest_folder, fname)
            if os.path.isfile(fpath):
                with open(fpath, 'rb') as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')
                photos_grouped['pinterest'].append({
                    'filename': fname,
                    'data': f"data:image/jpeg;base64,{encoded}",
                    'photo_type': 'pinterest'
                })

    memo = get_memo_from_file(date)

    return render_template('photos.html',
                           date=date,
                           photos_grouped=photos_grouped,
                           username=user_id,
                           memo=memo)
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)