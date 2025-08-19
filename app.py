import os
import json
import psycopg2
import requests
import math
from psycopg2.extras import Json, RealDictCursor
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from collections import defaultdict

# tai env
load_dotenv()

app = Flask(__name__)
# can co secret key
app.config['SECRET_KEY'] = os.urandom(24)

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = "https://discord.com/api/v10"

# --- HELPER FUNCTIONS FOR DISCORD API ---

# cache
_user_cache = {}

def discord_api_request(endpoint, method='GET', payload=None):
    if not BOT_TOKEN:
        return None
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        if method == 'GET':
            res = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers)
        # them cac method khac neu can
        res.raise_for_status()
        return res.json()
    except requests.RequestException as e:
        print(f"Loi goi API Discord toi {endpoint}: {e}")
        return None

def get_user_info(user_id):
    if user_id in _user_cache:
        return _user_cache[user_id]
    
    user_data = discord_api_request(f"/users/{user_id}")
    if user_data:
        avatar_hash = user_data.get('avatar')
        info = {
            'id': user_id,
            'name': user_data.get('global_name') or user_data.get('username', f'Unknown User {user_id}'),
            'avatar_url': f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png" if avatar_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
        }
        _user_cache[user_id] = info
        return info
    return {
        'id': user_id,
        'name': f'Unknown User {user_id}',
        'avatar_url': "https://cdn.discordapp.com/embed/avatars/0.png"
    }


# --- END HELPER FUNCTIONS ---


def get_db_connection():
    # ham ket noi db
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Loi ket noi database: {e}")
        return None

def parse_form_data(form):
    # ham xu ly data form
    config = defaultdict(dict)
    
    # key don le
    simple_keys = [
        'shop_channel_id', 'leaderboard_thread_id',
        'EMBED_COLOR', 'SELL_REFUND_PERCENTAGE',
        'SHOP_EMBED_THUMBNAIL_URL', 'SHOP_EMBED_IMAGE_URL',
        'EARNING_RATES_IMAGE_URL'
    ]
    for key in simple_keys:
        if form.get(key):
            config[key] = form.get(key)
    
    # key long nhau
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

    # xu ly config booster
    if 'BOOSTER_MULTIPLIER_CONFIG' in config:
        booster_conf = config['BOOSTER_MULTIPLIER_CONFIG']
        booster_conf['ENABLED'] = booster_conf.get('ENABLED') == 'true'
        if booster_conf.get('BASE_MULTIPLIER'):
            booster_conf['BASE_MULTIPLIER'] = float(booster_conf['BASE_MULTIPLIER'])
        if booster_conf.get('PER_BOOST_ADDITION'):
            booster_conf['PER_BOOST_ADDITION'] = float(booster_conf['PER_BOOST_ADDITION'])


    # ty le coin categories
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

    # ty le coin channels
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

    # qna
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
                "answer_description": qna_descs[i]
            })

    # chuyen defaultdict thanh dict bth
    return json.loads(json.dumps(config))


@app.route('/')
def index():
    # trang chu
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
        return render_template('index.html', guilds=[])
        
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT guild_id FROM guild_configs ORDER BY guild_id;")
        guilds_data = cur.fetchall()
    conn.close()
    
    guilds_details = []
    for row in guilds_data:
        guild_id = row['guild_id']
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
    # trang chinh sua
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        # parse data
        config_data_json = parse_form_data(request.form)

        try:
            with conn.cursor() as cur:
                # update
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

    # xu ly GET
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT config_data FROM guild_configs WHERE guild_id = %s;", (guild_id,))
        db_result = cur.fetchone()
    conn.close()

    if not db_result:
        flash(f"Không tìm thấy cấu hình cho Server ID: {guild_id}", "warning")
        return redirect(url_for('index'))
    
    config = db_result['config_data'] or {}

    # dam bao key luon ton tai
    keys_to_ensure = {
        "MESSAGES": {}, "FOOTER_MESSAGES": {}, 
        "CURRENCY_RATES": {"default": {}, "categories": {}, "channels": {}},
        "CUSTOM_ROLE_CONFIG": {}, "QNA_DATA": [],
        "BOOSTER_MULTIPLIER_CONFIG": {}
    }
    for key, default_value in keys_to_ensure.items():
        if key not in config:
            config[key] = default_value
    
    # lay thong tin tu discord
    guild_details = discord_api_request(f"/guilds/{guild_id}")
    all_channels = discord_api_request(f"/guilds/{guild_id}/channels")
    
    text_channels = []
    category_channels = []
    rateable_channels = []
    all_channels_map = {}
    
    if all_channels:
        text_channels = [ch for ch in all_channels if ch['type'] == 0]
        category_channels = [ch for ch in all_channels if ch['type'] == 4]
        rateable_channels = [ch for ch in all_channels if ch['type'] in [0, 5, 15]]
        all_channels_map = {str(ch['id']): ch['name'] for ch in all_channels}


    return render_template(
        'edit_config.html', 
        guild_id=guild_id, 
        config=config, 
        guild=guild_details,
        text_channels=text_channels,
        all_channels_map=all_channels_map,
        category_channels=category_channels,
        rateable_channels=rateable_channels
    )

# quan ly member
@app.route('/edit/<int:guild_id>/members')
def members(guild_id):
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
        return redirect(url_for('edit_config', guild_id=guild_id))

    guild_details = discord_api_request(f"/guilds/{guild_id}")
    if not guild_details:
        flash(f"Không thể lấy thông tin server {guild_id}", "danger")
        return redirect(url_for('index'))
    
    # lay member tu discord api
    api_members = discord_api_request(f"/guilds/{guild_id}/members?limit=1000")
    if api_members is None:
        api_members = []
    
    # lay user tu db
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT user_id, balance FROM users WHERE guild_id = %s", (guild_id,))
        db_users_list = cur.fetchall()
    conn.close()
    
    db_users_map = {str(u['user_id']): u for u in db_users_list}

    # xu ly tim kiem
    search_query = request.args.get('search', '').strip().lower()
    if search_query:
        filtered_members = []
        for member in api_members:
            user_info = member.get('user', {})
            display_name = (user_info.get('global_name') or user_info.get('username', '')).lower()
            if search_query in display_name:
                filtered_members.append(member)
        api_members = filtered_members
    
    # gop data
    members_data = []
    for member in api_members:
        user = member.get('user', {})
        user_id_str = user.get('id')
        if not user_id_str or user.get('bot'):
            continue
            
        avatar_hash = user.get('avatar')
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id_str}/{avatar_hash}.png" if avatar_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        db_info = db_users_map.get(user_id_str, {})

        members_data.append({
            'id': user_id_str,
            'name': user.get('global_name') or user.get('username'),
            'discriminator': user.get('discriminator'),
            'avatar_url': avatar_url,
            'balance': db_info.get('balance', 0)
        })

    # xu ly phan trang
    page = request.args.get('page', 1, type=int)
    per_page = 24 # so member moi trang
    total_members = len(members_data)
    total_pages = math.ceil(total_members / per_page)
    offset = (page - 1) * per_page
    paginated_members = members_data[offset : offset + per_page]

    return render_template(
        'members.html', 
        guild=guild_details, 
        members=paginated_members, 
        search_query=search_query,
        page=page,
        total_pages=total_pages
    )

@app.route('/edit/<int:guild_id>/member/<int:user_id>', methods=['GET', 'POST'])
def edit_member(guild_id, user_id):
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối database!", "danger")
        return redirect(url_for('members', guild_id=guild_id))

    guild_details = discord_api_request(f"/guilds/{guild_id}")
    if not guild_details:
        flash("Không thể lấy thông tin server", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_balance_str = request.form.get('balance')
        role_name = request.form.get('role_name')
        role_color = request.form.get('role_color')

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT balance FROM users WHERE user_id = %s AND guild_id = %s", (user_id, guild_id))
                user_data = cur.fetchone()
                old_balance = user_data['balance'] if user_data else 0
                
                new_balance = int(new_balance_str)
                amount_changed = new_balance - old_balance
                
                cur.execute("UPDATE users SET balance = %s WHERE user_id = %s AND guild_id = %s", (new_balance, user_id, guild_id))

                # log
                if amount_changed != 0:
                     cur.execute("""
                        INSERT INTO transactions (guild_id, user_id, transaction_type, item_name, amount_changed, new_balance)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """, (guild_id, user_id, 'admin_edit', 'Manual Edit', amount_changed, new_balance))

                # update custom role
                if role_name is not None and role_color is not None:
                    cur.execute("UPDATE custom_roles SET role_name = %s, role_color = %s WHERE user_id = %s AND guild_id = %s",
                                (role_name, role_color, user_id, guild_id))

            conn.commit()
            flash("Cập nhật thông tin thành viên thành công!", "success")
        except Exception as e:
            flash(f"Lỗi khi cập nhật: {e}", "danger")
            conn.rollback()
        finally:
            conn.close()
        return redirect(url_for('members', guild_id=guild_id))

    # GET request
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        query = """
        SELECT u.*, cr.role_id, cr.role_name, cr.role_color
        FROM users u
        LEFT JOIN custom_roles cr ON u.user_id = cr.user_id AND u.guild_id = cr.guild_id
        WHERE u.user_id = %s AND u.guild_id = %s;
        """
        cur.execute(query, (user_id, guild_id))
        user_db_data = cur.fetchone()
        
        # lay ls gd
        cur.execute("SELECT * FROM transactions WHERE guild_id = %s AND user_id = %s ORDER BY timestamp DESC LIMIT 10", (guild_id, user_id))
        transactions = cur.fetchall()

    conn.close()

    if not user_db_data:
        # tao user neu chua co
        with get_db_connection() as c:
            with c.cursor() as cur:
                cur.execute("INSERT INTO users (user_id, guild_id, balance) VALUES (%s, %s, 0) ON CONFLICT DO NOTHING", (user_id, guild_id))
                c.commit()
        return edit_member(guild_id, user_id)

    user_api_data = get_user_info(user_id)
    if not user_api_data:
        flash("Không thể lấy thông tin người dùng từ Discord.", "danger")
        return redirect(url_for('members', guild_id=guild_id))
        
    user_api_data['display_name'] = user_api_data.get('name')

    full_user_data = {**user_db_data, **user_api_data}

    return render_template('edit_member.html', guild=guild_details, user=full_user_data, transactions=transactions)

@app.route('/edit/<int:guild_id>/history')
def history(guild_id):
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối database!", "danger")
        return redirect(url_for('edit_config', guild_id=guild_id))

    guild_details = discord_api_request(f"/guilds/{guild_id}")
    if not guild_details:
        flash("Không thể lấy thông tin server", "danger")
        return redirect(url_for('index'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) as total FROM transactions WHERE guild_id = %s", (guild_id,))
        total_transactions = cur.fetchone()['total']
        
        cur.execute("SELECT * FROM transactions WHERE guild_id = %s ORDER BY timestamp DESC LIMIT %s OFFSET %s", (guild_id, per_page, offset))
        transactions_raw = cur.fetchall()
    conn.close()
    
    transactions = []
    for t in transactions_raw:
        user_info = get_user_info(t['user_id'])
        t['user_info'] = user_info
        transactions.append(t)

    total_pages = math.ceil(total_transactions / per_page)

    return render_template(
        'history.html', 
        guild=guild_details, 
        transactions=transactions,
        page=page,
        total_pages=total_pages
    )


if __name__ == '__main__':
    app.run(debug=True, port=5001)