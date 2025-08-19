import os
import json
import psycopg2
import requests
from psycopg2.extras import Json
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from collections import defaultdict

# Tai bien moi truong
load_dotenv()

app = Flask(__name__)
# Can co secret key
app.config['SECRET_KEY'] = os.urandom(24)

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = "https://discord.com/api/v10"

# --- HELPER FUNCTIONS FOR DISCORD API ---

def discord_api_request(endpoint):
    # Ham helper de goi discord api
    if not BOT_TOKEN:
        return None
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        res = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        print(f"Loi goi API Discord toi {endpoint}: {e}")
        return None

# --- END HELPER FUNCTIONS ---


def get_db_connection():
    # Ham ket noi db
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Loi ket noi database: {e}")
        return None

def parse_form_data(form):
    # Ham xu ly du lieu tu form phuc tap
    config = defaultdict(dict)
    
    # Cac key don le
    simple_keys = [
        'shop_channel_id', 'leaderboard_thread_id', # Them vao day
        'EMBED_COLOR', 'SELL_REFUND_PERCENTAGE',
        'SHOP_EMBED_THUMBNAIL_URL', 'SHOP_EMBED_IMAGE_URL',
        'EARNING_RATES_IMAGE_URL'
    ]
    for key in simple_keys:
        if form.get(key):
            config[key] = form.get(key)
    
    # Cac key long nhau
    for key, value in form.items():
        if '[' in key and ']' in key:
            parts = key.replace(']', '').split('[')
            d = config
            for part in parts[:-1]:
                if part not in d:
                    d[part] = defaultdict(dict)
                d = d[part]
            d[parts[-1]] = value if value else None

    # xu ly kieu du lieu
    if config.get('shop_channel_id'):
        config['shop_channel_id'] = int(config['shop_channel_id'])
    else:
         config['shop_channel_id'] = None
    if config.get('leaderboard_thread_id'):
        config['leaderboard_thread_id'] = int(config['leaderboard_thread_id'])
    else:
        config['leaderboard_thread_id'] = None

    if 'CURRENCY_RATES' in config and 'default' in config['CURRENCY_RATES']:
        default_rates = config['CURRENCY_RATES']['default']
        if default_rates.get('MESSAGES_PER_COIN'):
            default_rates['MESSAGES_PER_COIN'] = int(default_rates['MESSAGES_PER_COIN'])
        if default_rates.get('REACTIONS_PER_COIN'):
            default_rates['REACTIONS_PER_COIN'] = int(default_rates['REACTIONS_PER_COIN'])

    if 'CUSTOM_ROLE_CONFIG' in config:
        custom_role_conf = config['CUSTOM_ROLE_CONFIG']
        if custom_role_conf.get('MIN_BOOST_COUNT'):
            custom_role_conf['MIN_BOOST_COUNT'] = int(custom_role_conf['MIN_BOOST_COUNT'])
        if custom_role_conf.get('PRICE'):
            custom_role_conf['PRICE'] = int(custom_role_conf['PRICE'])

    if config.get('SELL_REFUND_PERCENTAGE'):
        config['SELL_REFUND_PERCENTAGE'] = float(config['SELL_REFUND_PERCENTAGE'])


    # Ty le coin categories
    cat_ids = request.form.getlist('category_rate_id[]')
    cat_msgs = request.form.getlist('category_rate_messages[]')
    cat_reacts = request.form.getlist('category_rate_reactions[]')
    
    config['CURRENCY_RATES']['categories'] = {}
    for i, cat_id in enumerate(cat_ids):
        if cat_id:
            config['CURRENCY_RATES']['categories'][cat_id] = {
                "MESSAGES_PER_COIN": int(cat_msgs[i]) if cat_msgs[i] else None,
                "REACTIONS_PER_COIN": int(cat_reacts[i]) if cat_reacts[i] else None
            }

    # Ty le coin channels
    chan_ids = request.form.getlist('channel_rate_id[]')
    chan_msgs = request.form.getlist('channel_rate_messages[]')
    chan_reacts = request.form.getlist('channel_rate_reactions[]')

    config['CURRENCY_RATES']['channels'] = {}
    for i, chan_id in enumerate(chan_ids):
        if chan_id:
            config['CURRENCY_RATES']['channels'][chan_id] = {
                "MESSAGES_PER_COIN": int(chan_msgs[i]) if chan_msgs[i] else None,
                "REACTIONS_PER_COIN": int(chan_reacts[i]) if chan_reacts[i] else None
            }

    # QnA
    qna_labels = request.form.getlist('qna_label[]')
    qna_descriptions = request.form.getlist('qna_description[]')
    qna_emojis = request.form.getlist('qna_emoji[]')
    qna_titles = request.form.getlist('qna_answer_title[]')
    qna_descs = request.form.getlist('qna_answer_description[]')
    
    config['QNA_DATA'] = []
    for i, label in enumerate(qna_labels):
        if label:
            config['QNA_DATA'].append({
                "label": label,
                "description": qna_descriptions[i],
                "emoji": qna_emojis[i],
                "answer_title": qna_titles[i],
                "answer_description": qna_descs[i].replace('\r\n', '\\n')
            })

    # Chuyen defaultdict thanh dict bth
    return json.loads(json.dumps(config))


@app.route('/')
def index():
    # Trang chu, hien thi list server
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
        return render_template('index.html', guilds=[])
        
    with conn.cursor() as cur:
        cur.execute("SELECT guild_id FROM guild_configs ORDER BY guild_id;")
        guilds_data = cur.fetchall()
    conn.close()
    
    guilds_details = []
    for row in guilds_data:
        guild_id = row[0]
        guild_info = discord_api_request(f"/guilds/{guild_id}")
        if guild_info:
            icon_hash = guild_info.get('icon')
            icon_url = f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png" if icon_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
            guilds_details.append({
                'id': guild_id,
                'name': guild_info.get('name', f'Unknown Server {guild_id}'),
                'icon_url': icon_url
            })
        else:
            guilds_details.append({
                'id': guild_id,
                'name': f'Server ID: {guild_id} (Không thể lấy thông tin)',
                'icon_url': "https://cdn.discordapp.com/embed/avatars/0.png"
            })
    
    return render_template('index.html', guilds=guilds_details)


@app.route('/edit/<int:guild_id>', methods=['GET', 'POST'])
def edit_config(guild_id):
    # Trang chinh sua config
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Parse all data tu form vao 1 object
        config_data_json = parse_form_data(request.form)

        try:
            with conn.cursor() as cur:
                # Update 1 cot JSONB duy nhat
                cur.execute(
                    """
                    UPDATE guild_configs
                    SET config_data = %s
                    WHERE guild_id = %s;
                    """,
                    (Json(config_data_json), guild_id)
                )
            conn.commit()
            flash(f"Đã cập nhật thành công cấu hình cho Server ID: {guild_id}", "success")
        except Exception as e:
            flash(f"Lỗi khi cập nhật database: {e}", "danger")
        finally:
            conn.close()
        
        return redirect(url_for('index'))

    # Xu ly GET request
    with conn.cursor() as cur:
        # Chi can lay 1 cot config_data
        cur.execute("SELECT config_data FROM guild_configs WHERE guild_id = %s;", (guild_id,))
        db_result = cur.fetchone()
    conn.close()

    if not db_result:
        flash(f"Không tìm thấy cấu hình cho Server ID: {guild_id}", "warning")
        return redirect(url_for('index'))
    
    config = db_result[0] or {}

    # Dam bao cac key chinh luon ton tai de tranh loi
    keys_to_ensure = {
        "MESSAGES": {}, "FOOTER_MESSAGES": {}, 
        "CURRENCY_RATES": {"default": {}, "categories": {}, "channels": {}},
        "CUSTOM_ROLE_CONFIG": {}, "QNA_DATA": []
    }
    for key, default_value in keys_to_ensure.items():
        if key not in config:
            config[key] = default_value
    
    # Xuong dong trong text area
    if "QNA_DATA" in config:
        for item in config["QNA_DATA"]:
            if "answer_description" in item and item["answer_description"]:
                item["answer_description"] = item["answer_description"].replace('\\n', '\n')
    
    # Lay thong tin tu discord api
    guild_details = discord_api_request(f"/guilds/{guild_id}")
    all_channels = discord_api_request(f"/guilds/{guild_id}/channels")
    
    text_channels = []
    category_channels = []
    rateable_channels = []
    all_channels_map = {}
    
    if all_channels:
        # lay kenh text cho dropdown shop
        text_channels = [ch for ch in all_channels if ch['type'] == 0]
        # lay category cho dropdown rate
        category_channels = [ch for ch in all_channels if ch['type'] == 4]
        # lay kenh co the chat de set rate
        rateable_channels = [ch for ch in all_channels if ch['type'] in [0, 5, 15]] # text, news, forum
        # tao map id -> ten
        all_channels_map = {str(ch['id']): ch['name'] for ch in all_channels}


    return render_template(
        'edit_config.html', 
        guild_id=guild_id, 
        config=config, 
        guild=guild_details,
        text_channels=text_channels,
        all_channels_map=all_channels_map,
        category_channels=category_channels, # pass vao template
        rateable_channels=rateable_channels   # pass vao template
    )

if __name__ == '__main__':
    # Chay app
    app.run(debug=True, port=5001)