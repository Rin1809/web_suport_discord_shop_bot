import os
import json
import psycopg2
import requests
import math
import re
import time
from psycopg2.extras import Json, RealDictCursor
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from collections import defaultdict

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = "https://discord.com/api/v10"

# cache
_user_cache = {}
_guild_members_cache = {}
CACHE_DURATION_SECONDS = 300 # 5 phut

def discord_api_request(endpoint, method='GET', payload=None):
    if not BOT_TOKEN:
        return None
    headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
    try:
        if method == 'GET':
            res = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers)
        elif method == 'POST':
            res = requests.post(f"{API_BASE_URL}{endpoint}", headers=headers, json=payload)
        elif method == 'PATCH':
            res = requests.patch(f"{API_BASE_URL}{endpoint}", headers=headers, json=payload)
        
        res.raise_for_status()
        return res.json() if res.status_code != 204 else None
    except requests.RequestException as e:
        print(f"Loi goi API Discord toi {endpoint}: {e}")
        if 'res' in locals() and res is not None:
             print(f"Response body: {res.text}")
        return None

def get_user_info(user_id):
    user_id_str = str(user_id)
    if user_id_str in _user_cache:
        return _user_cache[user_id_str]
    
    user_data = discord_api_request(f"/users/{user_id_str}")
    if user_data:
        avatar_hash = user_data.get('avatar')
        info = {
            'id': user_id_str,
            'name': user_data.get('global_name') or user_data.get('username', f'Unknown User {user_id_str}'),
            'avatar_url': f"https://cdn.discordapp.com/avatars/{user_id_str}/{avatar_hash}.png" if avatar_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
        }
        _user_cache[user_id_str] = info
        return info
    return {
        'id': user_id_str,
        'name': f'Unknown User {user_id_str}',
        'avatar_url': "https://cdn.discordapp.com/embed/avatars/0.png"
    }


def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Loi ket noi database: {e}")
        return None

def parse_form_data(form):
    config = defaultdict(dict)
    
    # cac key don
    simple_keys = [
        'shop_channel_id', 'leaderboard_thread_id', 'ADMIN_LOG_CHANNEL_ID',
        'EMBED_COLOR', 'SELL_REFUND_PERCENTAGE',
        'SHOP_EMBED_THUMBNAIL_URL', 'SHOP_EMBED_IMAGE_URL',
        'EARNING_RATES_IMAGE_URL', 'SHOP_DISPLAY_STYLE'
    ]
    for key in simple_keys:
        if form.get(key):
            config[key] = form.get(key)
    
    # cac key phuc tap
    for key, value in form.items():
        if '[' in key and ']' in key:
            parts = key.replace(']', '').split('[')
            d = config
            for part in parts[:-1]:
                if part not in d:
                    d[part] = defaultdict(dict)
                d = d[part]
            d[parts[-1]] = value if value else None

    # chuyen doi kieu
    if config.get('shop_channel_id'):
        config['shop_channel_id'] = int(config['shop_channel_id'])
    else:
         config['shop_channel_id'] = None

    if config.get('ADMIN_LOG_CHANNEL_ID'):
        config['ADMIN_LOG_CHANNEL_ID'] = int(config['ADMIN_LOG_CHANNEL_ID'])
    else:
        config['ADMIN_LOG_CHANNEL_ID'] = None

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
        if custom_role_conf.get('DEFAULT_PURCHASE_PRICE'):
            custom_role_conf['DEFAULT_PURCHASE_PRICE'] = int(custom_role_conf['DEFAULT_PURCHASE_PRICE'])

    if 'REGULAR_USER_ROLE_CREATION' in config:
        regular_conf = config['REGULAR_USER_ROLE_CREATION']
        regular_conf['ENABLED'] = regular_conf.get('ENABLED') == 'true'
        if regular_conf.get('CREATION_PRICE'):
            regular_conf['CREATION_PRICE'] = int(regular_conf['CREATION_PRICE'])

    if config.get('SELL_REFUND_PERCENTAGE'):
        config['SELL_REFUND_PERCENTAGE'] = float(config['SELL_REFUND_PERCENTAGE'])

    if 'BOOSTER_MULTIPLIER_CONFIG' in config:
        booster_conf = config['BOOSTER_MULTIPLIER_CONFIG']
        booster_conf['ENABLED'] = booster_conf.get('ENABLED') == 'true'
        if booster_conf.get('BASE_MULTIPLIER'):
            booster_conf['BASE_MULTIPLIER'] = float(booster_conf['BASE_MULTIPLIER'])
        if booster_conf.get('PER_BOOST_ADDITION'):
            booster_conf['PER_BOOST_ADDITION'] = float(booster_conf['PER_BOOST_ADDITION'])

    # ty le category
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
    
    # ty le channel
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

    # q&a
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

    return json.loads(json.dumps(config))


@app.route('/')
def index():
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
    conn = get_db_connection()
    if not conn:
        flash("Không thể kết nối đến cơ sở dữ liệu!", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        config_data_json = parse_form_data(request.form)

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "UPDATE guild_configs SET config_data = %s WHERE guild_id = %s;",
                    (Json(config_data_json), guild_id)
                )
                
                all_roles_raw = discord_api_request(f"/guilds/{guild_id}/roles")
                role_map = {r['name']: r for r in all_roles_raw} if all_roles_raw else {}

                role_names = request.form.getlist('shop_role_name[]')
                role_prices = request.form.getlist('shop_role_price[]')
                role_colors = request.form.getlist('shop_role_color[]')
                
                new_shop_roles_db = []
                for i, role_name in enumerate(role_names):
                    role_name = role_name.strip()
                    if not (role_name and role_prices[i]):
                        continue

                    hex_color = (role_colors[i] or '#99aab5').lstrip('#')
                    try:
                        color_int = int(hex_color, 16)
                    except ValueError:
                        flash(f"Mã màu không hợp lệ cho role '{role_name}'. Dùng màu mặc định.", "warning")
                        color_int = 0
                    
                    existing_role = role_map.get(role_name)
                    role_id = None

                    if existing_role:
                        role_id = existing_role['id']
                        if existing_role['color'] != color_int:
                            payload = {'color': color_int}
                            discord_api_request(f"/guilds/{guild_id}/roles/{role_id}", method='PATCH', payload=payload)
                            flash(f"Đã cập nhật màu cho role '{role_name}'.", "info")
                    else:
                        payload = {'name': role_name, 'color': color_int}
                        created_role = discord_api_request(f"/guilds/{guild_id}/roles", method='POST', payload=payload)
                        if created_role:
                            role_id = created_role['id']
                            flash(f"Đã tạo role mới: '{role_name}'", "success")
                        else:
                            flash(f"Không thể tạo role '{role_name}'. Vui lòng kiểm tra quyền của bot.", "danger")
                            continue
                    
                    if role_id:
                        new_shop_roles_db.append((int(role_id), int(role_prices[i])))
                
                # lay ds role hien tai
                cur.execute("SELECT role_id FROM shop_roles WHERE guild_id = %s", (guild_id,))
                existing_role_ids = {row['role_id'] for row in cur.fetchall()}
                new_role_ids = {role_id for role_id, price in new_shop_roles_db}
                
                # tim role can xoa
                roles_to_delete = existing_role_ids - new_role_ids
                if roles_to_delete:
                    # psycopg2 co the dung list/tuple cho IN
                    cur.execute("DELETE FROM shop_roles WHERE guild_id = %s AND role_id = ANY(%s)", (guild_id, list(roles_to_delete)))

                # cap nhat hoac them moi
                for role_id, price in new_shop_roles_db:
                    cur.execute(
                        "INSERT INTO shop_roles (guild_id, role_id, price) VALUES (%s, %s, %s) ON CONFLICT(role_id) DO UPDATE SET price = EXCLUDED.price",
                        (guild_id, role_id, price)
                    )

            conn.commit()
            flash(f"Đã cập nhật thành công cấu hình cho Server ID: {guild_id}", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Lỗi khi cập nhật database: {e}", "danger")
        finally:
            conn.close()
        
        return redirect(url_for('edit_config', guild_id=guild_id))

    # GET
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT config_data FROM guild_configs WHERE guild_id = %s;", (guild_id,))
        db_result = cur.fetchone()

        cur.execute("SELECT role_id, price FROM shop_roles WHERE guild_id = %s ORDER BY price ASC", (guild_id,))
        shop_roles_db = cur.fetchall()

    conn.close()

    if not db_result:
        flash(f"Không tìm thấy cấu hình cho Server ID: {guild_id}", "warning")
        return redirect(url_for('index'))
    
    config = db_result['config_data'] or {}

    keys_to_ensure = {
        "MESSAGES": {}, "FOOTER_MESSAGES": {}, 
        "CURRENCY_RATES": {"default": {}, "categories": {}, "channels": {}},
        "CUSTOM_ROLE_CONFIG": {}, "QNA_DATA": [],
        "BOOSTER_MULTIPLIER_CONFIG": {},
        "REGULAR_USER_ROLE_CREATION": {}
    }
    for key, default_value in keys_to_ensure.items():
        if key not in config:
            config[key] = default_value
    
    guild_details = discord_api_request(f"/guilds/{guild_id}")
    if guild_details:
        icon_hash = guild_details.get('icon')
        guild_details['icon_url'] = f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png" if icon_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
    
    all_channels = discord_api_request(f"/guilds/{guild_id}/channels")
    all_roles_raw = discord_api_request(f"/guilds/{guild_id}/roles")

    text_channels, category_channels, rateable_channels = [], [], []
    if all_channels:
        text_channels = [ch for ch in all_channels if ch['type'] == 0]
        category_channels = [ch for ch in all_channels if ch['type'] == 4]
        rateable_channels = [ch for ch in all_channels if ch['type'] in [0, 5, 15]]
    
    # map role de lay chi tiet
    role_id_to_details_map = {str(r['id']): {'name': r['name'], 'color': f"#{r['color']:06x}" if r['color'] != 0 else '#000000'} for r in all_roles_raw} if all_roles_raw else {}
    shop_roles_with_details = []
    for r in shop_roles_db:
        details = role_id_to_details_map.get(str(r['role_id']))
        if details:
            shop_roles_with_details.append({
                'name': details['name'],
                'color': details['color'],
                'price': r['price']
            })

    return render_template(
        'edit_config.html', 
        guild_id=guild_id, 
        config=config, 
        guild=guild_details,
        text_channels=text_channels,
        category_channels=category_channels,
        rateable_channels=rateable_channels,
        shop_roles=shop_roles_with_details
    )

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
    
    # su dung cache
    guild_id_str = str(guild_id)
    now = time.time()
    api_members = []
    
    if guild_id_str in _guild_members_cache and (now - _guild_members_cache[guild_id_str]['timestamp'] < CACHE_DURATION_SECONDS):
        api_members = _guild_members_cache[guild_id_str]['data']
    else:
        fetched_members = discord_api_request(f"/guilds/{guild_id}/members?limit=1000")
        if fetched_members is not None:
            api_members = fetched_members
            _guild_members_cache[guild_id_str] = {'data': api_members, 'timestamp': now}
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT user_id, balance FROM users WHERE guild_id = %s", (guild_id,))
        db_users_list = cur.fetchall()
    conn.close()
    
    db_users_map = {str(u['user_id']): u for u in db_users_list}

    search_query = request.args.get('search', '').strip().lower()
    if search_query:
        filtered_members = []
        for member in api_members:
            user_info = member.get('user', {})
            display_name = (user_info.get('global_name') or user_info.get('username', '')).lower()
            if search_query in display_name:
                filtered_members.append(member)
        api_members = filtered_members
    
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

    page = request.args.get('page', 1, type=int)
    per_page = 24 
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
        total_pages=total_pages,
        guild_id=guild_id
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
        fake_boosts_str = request.form.get('fake_boosts', '0')
        role_name = request.form.get('role_name')
        role_color = request.form.get('role_color')

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT balance FROM users WHERE user_id = %s AND guild_id = %s", (user_id, guild_id))
                user_data = cur.fetchone()
                old_balance = user_data['balance'] if user_data else 0
                
                new_balance = int(new_balance_str)
                new_fake_boosts = int(fake_boosts_str) if fake_boosts_str.isdigit() else 0
                amount_changed = new_balance - old_balance
                
                cur.execute("UPDATE users SET balance = %s, fake_boosts = %s WHERE user_id = %s AND guild_id = %s", (new_balance, new_fake_boosts, user_id, guild_id))

                if amount_changed != 0:
                     cur.execute("""
                        INSERT INTO transactions (guild_id, user_id, transaction_type, item_name, amount_changed, new_balance)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """, (guild_id, user_id, 'admin_edit', 'Manual Edit', amount_changed, new_balance))

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

    # GET
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        query = """
        SELECT u.*, cr.role_id, cr.role_name, cr.role_color, cr.role_style, cr.gradient_color_1, cr.gradient_color_2
        FROM users u
        LEFT JOIN custom_roles cr ON u.user_id = cr.user_id AND u.guild_id = cr.guild_id
        WHERE u.user_id = %s AND u.guild_id = %s;
        """
        cur.execute(query, (user_id, guild_id))
        user_db_data = cur.fetchone()
        
        cur.execute("SELECT * FROM transactions WHERE guild_id = %s AND user_id = %s ORDER BY timestamp DESC LIMIT 10", (guild_id, user_id))
        transactions = cur.fetchall()

    conn.close()

    if not user_db_data:
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

    return render_template('edit_member.html', guild=guild_details, user=full_user_data, transactions=transactions, guild_id=guild_id)

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
    
    # lay ds member 1 lan duy nhat
    members_map = {}
    api_members = discord_api_request(f"/guilds/{guild_id}/members?limit=1000")
    if api_members:
        for member_data in api_members:
            user = member_data.get('user', {})
            user_id = user.get('id')
            if user_id:
                avatar_hash = user.get('avatar')
                members_map[int(user_id)] = {
                    'name': user.get('global_name') or user.get('username'),
                    'avatar_url': f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png" if avatar_hash else "https://cdn.discordapp.com/embed/avatars/0.png"
                }

    transactions = []
    for t in transactions_raw:
        user_id = t['user_id']
        # tra cuu map truoc
        if user_id in members_map:
            t['user_info'] = members_map[user_id]
        else:
            # fallback cho user da roi sv
            t['user_info'] = get_user_info(user_id)
        transactions.append(t)

    total_pages = math.ceil(total_transactions / per_page)

    return render_template(
        'history.html', 
        guild=guild_details, 
        transactions=transactions,
        page=page,
        total_pages=total_pages,
        guild_id=guild_id
    )


if __name__ == '__main__':
    app.run('0.0.0.0', debug=True, port=5001)